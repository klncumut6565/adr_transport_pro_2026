"""PostgreSQL (Supabase) veritabanı katmanı — Faz 0b.

Tasarım: PgDatabaseManager, DatabaseManager'ın ALT SINIFIDIR; 56 iş
metodunun TAMAMI miras alınır, satırı bile değişmez. SQLite→Pg lehçe
çevirisi TranslatingCursor içinde, yani bağlantının EN ALT katmanında
yapılır — böylece geçit metotlarını (execute_*) kullanan kodlar da,
doğrudan conn.execute/cursor.execute çağıran istatistik metotları da
aynı çeviriden geçer.

Çevrilen lehçe farkları:
  '?'            → '%s'                    (yer tutucu)
  LIKE           → ILIKE                   (sqlite LIKE harf duyarsızdı)
  INSERT OR REPLACE/IGNORE → ON CONFLICT   (upsert)
  strftime('%f', x)        → to_char(x)    (%Y→YYYY, %m→MM, %d→DD)
  julianday(a)-julianday('now') → a::date - CURRENT_DATE (gün farkı)
  date('now','-N months')  → to_char(CURRENT_DATE - INTERVAL ...)

Yapısal kararlar:
  * Her iş tablosuna tenant_id BIGINT NOT NULL DEFAULT 1 (+indeks).
    Plan belgesindeki "company_id" adı, şemadaki mevcut 'companies'
    (gönderen/alıcı/taşımacı) tablosuyla karışmasın diye tenant_id oldu.
    Kiracı filtreleme Faz 1'de kimlik doğrulamayla gelecek.
  * FK'lar Pg şemasına TAŞINMADI: SQLite tarafı PRAGMA foreign_keys
    açmadığı için FK'lar zaten zorlanmıyordu (ör. serbest kalemlerde
    chemical_id=0). Davranış eşitliği esas alındı; Faz 6'daki veri
    migrasyonunda 0→NULL temizliğiyle birlikte geri açılacak.
  * Dosya-kopyalama yedekleri Pg'de anlamsız → devre dışı (Supabase
    tarafında Faz 6'da pg_dump/dışa aktarma rutini kurulacak).
  * Şema elle yazılmadı: geçici bir SQLite veritabanı kurulup monolitin
    init_database + migrasyonlarının ürettiği NİHAİ şema okunur ve
    çevrilir. Monolitte şema değişirse burası otomatik ayak uydurur.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import List, Optional

try:
    import psycopg
    from psycopg.rows import dict_row
    PSYCOPG_AVAILABLE = True
except ImportError:  # pragma: no cover
    PSYCOPG_AVAILABLE = False

from .db import DatabaseManager

TENANT_TABLES = (
    "companies", "drivers", "vehicles", "chemicals",
    "shipments", "shipment_items", "settings",
)

# INSERT OR REPLACE için tablo → benzersiz kısıt kolonları (şemadan doğrulandı)
_UPSERT_KEYS = {
    "settings": "key",                                              # PRIMARY KEY
    "company_products": "trade_name, un_number, classification_code",  # UNIQUE(...)
    "packaging_types": "code",                                      # UNIQUE
}

_STRFTIME_MAP = (("%Y", "YYYY"), ("%m", "MM"), ("%d", "DD"),
                 ("%H", "HH24"), ("%M", "MI"), ("%S", "SS"))


def translate_query(q: str) -> str:
    """Tek bir SQLite sorgusunu Pg lehçesine çevirir (idempotent)."""
    q = q.replace("?", "%s")
    q = re.sub(r"\bLIKE\b", "ILIKE", q, flags=re.IGNORECASE)

    # julianday: gün farkı hesapları. SQLite julianday('') NULL döndürür;
    # Pg ''::date hata verir — NULLIF ile aynı hoşgörü sağlanır.
    q = re.sub(r"julianday\('now'\)", "CURRENT_DATE", q, flags=re.IGNORECASE)
    q = re.sub(r"julianday\(([^)]+)\)", r"(NULLIF(\1, ''))::date", q, flags=re.IGNORECASE)

    # strftime('%Y-%m', kolon) → to_char((kolon)::timestamp, 'YYYY-MM')
    def _sf(m):
        fmt = m.group(1)
        for a, b in _STRFTIME_MAP:
            fmt = fmt.replace(a, b)
        return f"to_char(({m.group(2).strip()})::timestamp, '{fmt}')"
    q = re.sub(r"strftime\('([^']+)'\s*,\s*([^)]+)\)", _sf, q, flags=re.IGNORECASE)

    # date('now', '-6 months') → metin biçiminde tarih (TEXT kolonlarla kıyas için)
    q = re.sub(r"date\('now'\s*,\s*'(-?\d+)\s+(month|day|year)s?'\)",
               r"to_char(CURRENT_DATE + INTERVAL '\1 \2', 'YYYY-MM-DD')",
               q, flags=re.IGNORECASE)
    q = re.sub(r"\bdate\('now'\)", "to_char(CURRENT_DATE, 'YYYY-MM-DD')",
               q, flags=re.IGNORECASE)

    # INSERT OR REPLACE / IGNORE → ON CONFLICT
    m = re.match(r"\s*INSERT\s+OR\s+(REPLACE|IGNORE)\s+INTO\s+(\w+)\s*\(([^)]*)\)",
                 q, re.IGNORECASE)
    if m:
        mode, table, cols = m.group(1).upper(), m.group(2), m.group(3)
        q = re.sub(r"INSERT\s+OR\s+(REPLACE|IGNORE)", "INSERT",
                   q, count=1, flags=re.IGNORECASE)
        key = _UPSERT_KEYS.get(table)
        if mode == "IGNORE" or not key:
            q = q.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
        else:
            keycols = [k.strip() for k in key.split(",")]
            sets = ", ".join(f"{c.strip()} = EXCLUDED.{c.strip()}"
                             for c in cols.split(",")
                             if c.strip() and c.strip() not in keycols)
            q = (q.rstrip().rstrip(";") +
                 f" ON CONFLICT ({', '.join(keycols)}) DO UPDATE SET {sets}")
    return q


if PSYCOPG_AVAILABLE:
    class TranslatingCursor(psycopg.Cursor):
        """execute anında SQLite lehçesini Pg'ye çeviren cursor."""

        def execute(self, query, params=None, **kw):
            if isinstance(query, str):
                query = translate_query(query)
            return super().execute(query, params, **kw)


def _strip_foreign_keys(create_sql: str) -> str:
    """CREATE TABLE gövdesindeki FK tanımlarını üst-düzey virgül
    ayrıştırmasıyla güvenle kaldırır (iç içe parantezlere dayanıklı)."""
    m = re.search(r"\(", create_sql)
    if not m:
        return create_sql
    head = create_sql[:m.start() + 1]
    body_end = create_sql.rfind(")")
    body, tail = create_sql[m.start() + 1:body_end], create_sql[body_end:]

    parts, depth, cur = [], 0, []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur)); cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))

    kept = []
    for p in parts:
        if re.match(r"\s*FOREIGN\s+KEY\b", p, re.IGNORECASE):
            continue
        p = re.sub(r"\bREFERENCES\s+\w+\s*(\([^)]*\))?"
                   r"(\s+ON\s+(DELETE|UPDATE)\s+\w+(\s+\w+)?)*",
                   "", p, flags=re.IGNORECASE)
        kept.append(p)
    return head + ",".join(kept) + tail


def _to_pg(name: str, sql: str) -> str:
    """Tek bir SQLite CREATE TABLE ifadesini Pg lehçesine çevirir."""
    out = sql
    out = re.sub(r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
                 "BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY",
                 out, flags=re.IGNORECASE)
    out = re.sub(r"\bAUTOINCREMENT\b", "", out, flags=re.IGNORECASE)
    out = re.sub(r"\bCOLLATE\s+NOCASE\b", "", out, flags=re.IGNORECASE)
    out = re.sub(r"\bBLOB\b", "BYTEA", out, flags=re.IGNORECASE)
    out = re.sub(r"\bCREATE\s+TABLE\b", "CREATE TABLE IF NOT EXISTS",
                 out, count=1, flags=re.IGNORECASE)
    out = _strip_foreign_keys(out)
    if name in TENANT_TABLES and "tenant_id" not in out:
        last = out.rstrip()
        if last.endswith(")"):
            out = (last[:-1].rstrip().rstrip(",") +
                   ",\n                tenant_id BIGINT NOT NULL DEFAULT 1\n            )")
    return out


def _sqlite_schema_sql():
    """Geçici SQLite veritabanından NİHAİ şemayı (migrasyonlar dahil) okur."""
    with tempfile.TemporaryDirectory() as td:
        db = DatabaseManager(str(Path(td) / "schema_probe.db"))
        rows = db.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL")
        stmts = [(r["name"], r["sql"]) for r in rows]
        db.close()
    return stmts


class PgDatabaseManager(DatabaseManager):
    """DatabaseManager'ın PostgreSQL sürücüsü (genel arayüz birebir aynı)."""

    def __init__(self, dsn: str, tenant_id: int = 1):
        if not PSYCOPG_AVAILABLE:
            raise ImportError("psycopg gerekli: pip install 'psycopg[binary]'")
        self.dsn = dsn
        self.tenant_id = tenant_id
        self.db_path = dsn          # üst sınıfla alan uyumu
        self.connection = None
        self.init_database()

    # ── bağlantı ─────────────────────────────────────────────────────
    def _get_conn(self):
        if self.connection is None or self.connection.closed:
            self.connection = psycopg.connect(
                self.dsn, row_factory=dict_row,
                cursor_factory=TranslatingCursor, autocommit=True)
            # Kiracı kimliği oturum değişkenine yazılır; RLS politikaları
            # tüm sorguları buna göre süzer. İş metotları hiç değişmez.
            with self.connection.cursor() as cur:
                cur.execute("SELECT set_config('app.tenant_id', %s, false)",
                            (str(self.tenant_id),))
        return self.connection

    def set_tenant(self, tenant_id: int):
        """Aktif kiracıyı değiştirir (giriş sonrası çağrılır)."""
        self.tenant_id = tenant_id
        if self.connection and not self.connection.closed:
            with self.connection.cursor() as cur:
                cur.execute("SELECT set_config('app.tenant_id', %s, false)",
                            (str(tenant_id),))

    # ── geçitler (çeviri cursor'da; burada yalnız dönüş farkları) ────
    def execute(self, query: str, params: tuple = ()) -> List[dict]:
        with self._get_conn().cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def execute_one(self, query: str, params: tuple = ()) -> Optional[dict]:
        with self._get_conn().cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()

    def execute_insert(self, query: str, params: tuple = ()) -> int:
        q = query.rstrip().rstrip(";")
        if re.match(r"^\s*INSERT\b", q, re.IGNORECASE) and "RETURNING" not in q.upper():
            q += " RETURNING id"
        with self._get_conn().cursor() as cur:
            cur.execute(q, params)
            if cur.description:
                row = cur.fetchone()
                if row and "id" in row:
                    return row["id"]
        return 0

    def execute_update(self, query: str, params: tuple = ()) -> int:
        with self._get_conn().cursor() as cur:
            cur.execute(query, params)
            return cur.rowcount

    def execute_delete(self, query: str, params: tuple = ()) -> int:
        return self.execute_update(query, params)

    # ── şema ─────────────────────────────────────────────────────────
    def init_database(self):
        conn = self._get_conn()
        with conn.cursor() as cur:
            for name, sql in _sqlite_schema_sql():
                cur.execute(_to_pg(name, sql))
            # MİGRASYON (kendi kendini iyileştirir): eski kurulumlarda
            # chemicals üzerinde UNIQUE(un_number, classification_code,
            # packing_group) kısıtı vardı; CREATE TABLE IF NOT EXISTS mevcut
            # tabloyu DEĞİŞTİRMEDİĞİ için canlı (Supabase) veritabanında
            # kalıyordu ve Tablo A'nın yalnız özel hükümle ayrışan 66 satırını
            # sessizce yutuyordu (UN1133 640C/640D örneği — bkz. webcore/db.py
            # migrasyon notu). Uygulama her açılışta bu kısıtı arar ve düşürür.
            cur.execute("""
                SELECT conname FROM pg_constraint
                WHERE conrelid = 'chemicals'::regclass AND contype = 'u'""")
            for row in cur.fetchall():
                cur.execute(f'ALTER TABLE chemicals DROP CONSTRAINT "{row["conname"]}"')
            for t in TENANT_TABLES:
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{t}_tenant "
                            f"ON {t}(tenant_id)")
                # Yeni satırlar otomatik olarak aktif kiracıya yazılsın
                cur.execute(
                    f"ALTER TABLE {t} ALTER COLUMN tenant_id SET DEFAULT "
                    f"COALESCE(NULLIF(current_setting('app.tenant_id', true), '')::bigint, 1)")
                # Satır Düzeyi Güvenlik: kiracı izolasyonu veritabanında.
                # FORCE şart — tablo sahibi rol (Supabase'de 'postgres')
                # aksi hâlde politikalardan muaf kalır.
                cur.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
                cur.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
                cur.execute(f"DROP POLICY IF EXISTS tenant_izolasyon ON {t}")
                cur.execute(
                    f"CREATE POLICY tenant_izolasyon ON {t} "
                    f"USING (tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), '')::bigint, 1)) "
                    f"WITH CHECK (tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), '')::bigint, 1))")

    # ── Pg'de anlamsız kalan sqlite işlevleri ────────────────────────
    def get_top_senders(self, limit=10, year=None) -> list:
        """Tek satır farkla override: SQLite, GROUP BY s.sender_id ile
        gruplanmamış c.name kolonunu seçmeye izin verir (bare column);
        Pg SQL standardı gereği vermez. Sorgu mantığı birebir aynıdır,
        yalnızca c.name GROUP BY'a eklenmiştir."""
        sql = ("SELECT c.name, COUNT(s.id) AS sevkiyat_sayisi "
               "FROM shipments s JOIN companies c ON c.id=s.sender_id")
        p = []
        if year:
            sql += " WHERE strftime('%Y', s.document_date)=?"
            p.append(str(year))
        sql += " GROUP BY s.sender_id, c.name ORDER BY sevkiyat_sayisi DESC LIMIT ?"
        p.append(limit)
        return [dict(r) for r in self.execute(sql, tuple(p))]

    def get_top_chemicals(self, limit=10, year=None) -> list:
        """get_top_senders ile aynı gerekçe: si.class_code GROUP BY'a eklendi."""
        sql = ("SELECT si.un_number, si.class_code, COUNT(*) AS adet, "
               "SUM(si.net_quantity) AS toplam_net_kg "
               "FROM shipment_items si JOIN shipments s ON s.id=si.shipment_id")
        p = []
        if year:
            sql += " WHERE strftime('%Y', s.document_date)=?"
            p.append(str(year))
        sql += (" GROUP BY si.un_number, si.class_code "
                "ORDER BY toplam_net_kg DESC LIMIT ?")
        p.append(limit)
        return [dict(r) for r in self.execute(sql, tuple(p))]

    def _setup_backup_system(self):
        pass

    def backup_now(self) -> str:
        raise NotImplementedError(
            "Pg tarafında dosya yedeği yok; Faz 6'da pg_dump rutini gelecek. "
            "Supabase panelinden veya pg_dump ile yedek alın.")

    def list_backups(self) -> list:
        return []

    def vacuum(self):
        self._get_conn().execute("VACUUM")
