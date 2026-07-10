import io, logging, os, re, sqlite3, sys, time, argparse
from pathlib import Path
from typing import Optional

try:
    import pandas as pd
except ImportError:
    sys.exit("HATA: pandas yüklü değil  →  pip install pandas")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("adr_importer")

# ══════════════════════════════════════════════════════════════════════════════
# BÖLÜM 1 — YOL YARDIMCILARI
# ══════════════════════════════════════════════════════════════════════════════

def get_db_path() -> str:
    """
    Windows Türkçe kullanıcı adı güvenli DB yolu.
    %APPDATA% her zaman ASCII-safe'dir; Path.home() Türkçe karakterde bozulabilir.
    """
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", os.path.expandvars("%USERPROFILE%")))
    else:
        base = Path.home()
    folder = base / ".adr_transport_pro"
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder / "adr_database.db")


def find_csv_auto(hint_dir: str = None) -> Optional[str]:
    """
    Birden fazla olası isimle CSV'yi otomatik bulur.
    Not: Klasörde hem 'ADR_A_TABLOSU.csv' hem 'ADR A TABLOSU.csv' olabilir —
         ikisini de dener.
    """
    names = [
        "ADR_A_TABLOSU.csv",
        "ADR A TABLOSU.csv",
        "adr_a_tablosu.csv",
        "adr a tablosu.csv",
    ]
    dirs = []
    if hint_dir:
        dirs.append(Path(hint_dir))
    dirs.append(Path(__file__).resolve().parent)
    dirs.append(Path.cwd())
    if os.name == "nt":
        dirs.append(Path(os.path.expandvars("%USERPROFILE%")) / "Desktop")

    for d in dirs:
        for name in names:
            p = d / name
            if p.is_file():
                return str(p)
    return None


# ══════════════════════════════════════════════════════════════════════════════
# BÖLÜM 2 — CSV PARSE
# ══════════════════════════════════════════════════════════════════════════════

# ADR_A_TABLOSU.csv kolon indeksleri (0-tabanlı)
_C = dict(
    un_no=0, isim_tr=1, sinif=2, sinif_kodu=3, paket_grubu=4,
    etiketler=5, ozel_hukumler=6, lq=7, eq=8, paket_tal=9,
    tank_kodu=14, tasima_kat=17, tasima_ozel=18,
    cv_kodlari=20, s_kodlari=21, isim_temiz=24,
)
_DATA_START = 4


def _clean(val) -> str:
    if val is None:
        return ""
    try:
        import math
        if isinstance(val, float) and math.isnan(val):
            return ""
    except Exception:
        pass
    s = str(val).replace("\n", " ").replace("\r", "").strip()
    return re.sub(r" {2,}", " ", s)


def _un(val) -> str:
    digits = re.sub(r"\D", "", _clean(val))
    return digits.zfill(4) if digits else ""


def _lq(val) -> int:
    s = _clean(val).upper()
    return 0 if s in ("", "0", "NAN") else 1


def _eq(val) -> int:
    s = _clean(val).upper()
    return 0 if s in ("", "E0", "NAN") else 1


def _tc(val) -> str:
    s = _clean(val)
    m = re.search(r"(\d+)", s)
    return m.group(1) if m else s


def _tunnel(tasima_raw: str) -> str:
    m = re.search(r"\(([A-E][^\)]*)\)", tasima_raw)
    return m.group(1) if m else ""


def _row_to_record(row: pd.Series) -> Optional[dict]:
    def col(key):
        idx = _C.get(key, -1)
        return _clean(row.iloc[idx]) if 0 <= idx < len(row) else ""

    un = _un(col("un_no"))
    if not un:
        return None

    isim = col("isim_temiz") or col("isim_tr")
    if not isim:
        return None

    tasima_raw = col("tasima_kat")
    ozel = " | ".join(filter(None, [
        col("ozel_hukumler"), col("cv_kodlari"),
        col("s_kodlari"),     col("tasima_ozel"),
    ]))

    return {
        "un_number":               un,
        "proper_shipping_name_tr": isim,
        "proper_shipping_name_en": "",
        "class_code":              col("sinif"),
        "packing_group":           col("paket_grubu"),
        "tunnel_code":             _tunnel(tasima_raw),
        "transport_category":      _tc(tasima_raw),
        "segregation_group":       "",
        "special_provisions":      ozel,
        "lq_allowed":              _lq(col("lq")),
        "eq_allowed":              _eq(col("eq")),
        "limited_quantity":        _clean(col("lq")),        # ham 7a: "1 L", "5 kg", "0"
        "excepted_quantity":       _clean(col("eq")).upper(), # ham 7b: E0..E5
        "hazard_labels":           col("etiketler"),
    }


def parse_csv(csv_path: str) -> list:
    log.info(f"CSV okunuyor: {csv_path}")
    with open(csv_path, encoding="utf-8-sig") as f:
        content = f.read()

    df = pd.read_csv(
        io.StringIO(content), sep=";", header=None,
        on_bad_lines="skip", dtype=str, keep_default_na=False,
    ).iloc[_DATA_START:].reset_index(drop=True)

    records, errors = [], []
    for i in range(len(df)):
        try:
            rec = _row_to_record(df.iloc[i])
            if rec:
                records.append(rec)
        except Exception as e:
            errors.append((i, str(e)))

    log.info(f"Parse: {len(records)} kayıt, {len(errors)} hata")
    return records


# ══════════════════════════════════════════════════════════════════════════════
# BÖLÜM 3 — VERİTABANI
#
# TEMEL DEĞİŞİKLİK: UN numarası + paketleme grubu birlikte UNIQUE key
# Neden: UN 1133 PG-I, UN 1133 PG-II, UN 1133 PG-III üç farklı kayıttır.
# INSERT OR REPLACE ile artık hiç kayıp olmaz (2939 → 2939).
# ══════════════════════════════════════════════════════════════════════════════

_DDL = """
CREATE TABLE IF NOT EXISTS chemicals (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    un_number               TEXT NOT NULL,
    proper_shipping_name_tr TEXT,
    proper_shipping_name_en TEXT,
    class_code              TEXT,
    packing_group           TEXT,
    tunnel_code             TEXT,
    transport_category      TEXT,
    segregation_group       TEXT,
    special_provisions      TEXT,
    lq_allowed              INTEGER DEFAULT 0,
    eq_allowed              INTEGER DEFAULT 0,
    limited_quantity        TEXT DEFAULT '',
    excepted_quantity       TEXT DEFAULT '',
    hazard_labels           TEXT,
    UNIQUE(un_number, packing_group)
)
"""

# Ana programın orijinal şeması (UNIQUE yalnızca un_number) varsa —
# bunu güvenle migrate et:
_MIGRATE_ADD_UNIQUE = """
CREATE TABLE IF NOT EXISTS chemicals_new (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    un_number               TEXT NOT NULL,
    proper_shipping_name_tr TEXT,
    proper_shipping_name_en TEXT,
    class_code              TEXT,
    packing_group           TEXT,
    tunnel_code             TEXT,
    transport_category      TEXT,
    segregation_group       TEXT,
    special_provisions      TEXT,
    lq_allowed              INTEGER DEFAULT 0,
    eq_allowed              INTEGER DEFAULT 0,
    limited_quantity        TEXT DEFAULT '',
    excepted_quantity       TEXT DEFAULT '',
    hazard_labels           TEXT,
    UNIQUE(un_number, packing_group)
)
"""

_INSERT = """
INSERT OR REPLACE INTO chemicals (
    un_number, proper_shipping_name_tr, proper_shipping_name_en,
    class_code, packing_group, tunnel_code, transport_category,
    segregation_group, special_provisions, lq_allowed, eq_allowed,
    limited_quantity, excepted_quantity, hazard_labels
) VALUES (
    :un_number, :proper_shipping_name_tr, :proper_shipping_name_en,
    :class_code, :packing_group, :tunnel_code, :transport_category,
    :segregation_group, :special_provisions, :lq_allowed, :eq_allowed,
    :limited_quantity, :excepted_quantity, :hazard_labels
)
"""


def _open(db_path: str, retries: int = 5) -> sqlite3.Connection:
    """WAL kilit durumu için retry ile bağlan."""
    for attempt in range(1, retries + 1):
        try:
            conn = sqlite3.connect(db_path, timeout=15)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=10000")
            return conn
        except sqlite3.OperationalError as e:
            if attempt == retries:
                raise
            log.warning(f"DB kilit, bekleniyor ({attempt}/{retries})...")
            time.sleep(1.5)


def _schema_has_composite_unique(conn: sqlite3.Connection) -> bool:
    """Mevcut şemada (un_number, packing_group) UNIQUE var mı?"""
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='chemicals'"
    ).fetchone()
    if not sql:
        return False
    return "packing_group" in (sql[0] or "").lower() and "unique" in (sql[0] or "").lower()


def ensure_schema(db_path: str):
    """
    DB yoksa oluştur. Eski şema (UNIQUE yalnızca un_number) varsa migrate et.
    Tablo migrate edilirken mevcut veriler korunur.
    """
    conn = _open(db_path)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='chemicals'"
    ).fetchone()

    if not cur:
        # Yeni kurulum
        conn.execute(_DDL)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ch_un   ON chemicals(un_number)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ch_name ON chemicals(proper_shipping_name_tr)")
        conn.commit()
        log.info("Yeni şema oluşturuldu ✓")
    elif not _schema_has_composite_unique(conn):
        # Eski şema: migrate et (veri kaybı yok)
        log.info("Eski şema tespit edildi → migrate ediliyor (veri korunur)...")
        conn.execute(_MIGRATE_ADD_UNIQUE)
        old_cols = {r[1] for r in conn.execute("PRAGMA table_info(chemicals)")}
        lq_col = "limited_quantity" if "limited_quantity" in old_cols else "''"
        eq_col = "excepted_quantity" if "excepted_quantity" in old_cols else "''"
        conn.execute(f"""
            INSERT OR IGNORE INTO chemicals_new
            SELECT id, un_number, proper_shipping_name_tr, proper_shipping_name_en,
                   class_code, packing_group, tunnel_code, transport_category,
                   segregation_group, special_provisions, lq_allowed, eq_allowed,
                   {lq_col}, {eq_col}, hazard_labels
            FROM chemicals
        """)
        conn.execute("DROP TABLE chemicals")
        conn.execute("ALTER TABLE chemicals_new RENAME TO chemicals")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ch_un   ON chemicals(un_number)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ch_name ON chemicals(proper_shipping_name_tr)")
        conn.commit()
        log.info("Migrate tamamlandı ✓")
    else:
        log.info("Şema güncel ✓")

    conn.close()


def get_count(db_path: str) -> int:
    try:
        conn = _open(db_path)
        n = conn.execute("SELECT COUNT(*) FROM chemicals").fetchone()[0]
        conn.close()
        return n
    except Exception:
        return -1


def write_records(db_path: str, records: list, clear_first: bool = False) -> tuple:
    conn = _open(db_path)
    existing = {
        (r[0], r[1]) for r in conn.execute(
            "SELECT un_number, COALESCE(packing_group,'') FROM chemicals"
        )
    }

    if clear_first:
        conn.execute("DELETE FROM chemicals")
        conn.commit()
        existing = set()
        log.warning("Mevcut kayıtlar silindi")

    updated  = sum(1 for r in records
                   if (r["un_number"], r["packing_group"]) in existing)
    new_cnt  = len(records) - updated

    conn.executemany(_INSERT, records)
    conn.commit()
    conn.close()
    return new_cnt, updated


# ══════════════════════════════════════════════════════════════════════════════
# BÖLÜM 4 — ANA PROGRAMA ENTEGRASYON
# ══════════════════════════════════════════════════════════════════════════════

def auto_import_if_needed(db_manager, csv_path: str = None,
                          min_count: int = 100, force: bool = False) -> int:
    """
    Ana programa tek satır entegrasyon.

    Kullanım — adr_transport_pro_2026.py → load_demo_data() fonksiyonu sonuna:

        import adr_csv_importer
        adr_csv_importer.auto_import_if_needed(db)

    db_manager : Ana programın DatabaseManager örneği
    csv_path   : None → otomatik arama
    min_count  : Bu sayıdan az kayıt varsa import tetiklenir
    force      : True → her seferinde import yap
    """
    db_path = db_manager.db_path

    # Mevcut kayıt sayısını sor
    try:
        current = db_manager.execute(
            "SELECT COUNT(*) as c FROM chemicals"
        )[0]["c"]
    except Exception:
        current = 0

    if not force and current >= min_count:
        log.info(f"Kimyasal DB hazır ({current} kayıt). Import atlandı.")
        return 0

    # CSV bul
    if csv_path is None:
        csv_path = find_csv_auto(hint_dir=os.path.dirname(db_path))
    if csv_path is None:
        log.warning(
            "ADR_A_TABLOSU.csv bulunamadı — kimyasal DB yüklenemedi.\n"
            "  → CSV dosyasını program klasörüne kopyalayın."
        )
        return 0

    log.info(f"Kimyasal DB yükleniyor: {csv_path}")

    # Ana programın bağlantısını serbest bırak (WAL kilit önlemi)
    try:
        if getattr(db_manager, "connection", None):
            db_manager.connection.commit()
            db_manager.connection.close()
            db_manager.connection = None
    except Exception:
        pass

    ensure_schema(db_path)
    records = parse_csv(csv_path)
    if not records:
        log.warning("CSV'den kayıt çıkarılamadı.")
        return 0

    new_cnt, updated = write_records(db_path, records)
    log.info(f"✅ {new_cnt} yeni + {updated} güncellendi = {len(records)} toplam")
    return new_cnt


# ══════════════════════════════════════════════════════════════════════════════
# BÖLÜM 5 — CLI
# ══════════════════════════════════════════════════════════════════════════════

def _sample(records, n=5):
    print("\n── İlk 5 Örnek Kayıt ──────────────────────────────────────────────────")
    for r in records[:n]:
        print(
            f"  UN{r['un_number']} | Sınıf:{r['class_code']:5s} | PG:{r['packing_group']:4s} | "
            f"TC:{r['transport_category']:2s} | Tünel:{r['tunnel_code']:8s} | "
            f"LQ:{r['lq_allowed']} EQ:{r['eq_allowed']} | "
            f"{r['proper_shipping_name_tr'][:50]}"
        )
    print()


def _summary(new_cnt, updated, errors):
    print("── Aktarım Özeti ───────────────────────────────────────────────────────")
    print(f"  Yeni eklenen  : {new_cnt:>6}")
    print(f"  Güncellenen   : {updated:>6}")
    print(f"  Parse hatası  : {errors:>6}")
    print(f"  TOPLAM        : {new_cnt+updated:>6}")
    print("────────────────────────────────────────────────────────────────────────\n")


def main():
    p = argparse.ArgumentParser(
        description="ADR_A_TABLOSU.csv → adr_database.db aktarıcı",
        epilog="Örnek: python adr_csv_importer.py --csv \"C:\\...\\ADR_A_TABLOSU.csv\""
    )
    p.add_argument("--csv",         default=None,         help="CSV dosya yolu")
    p.add_argument("--db",          default=None,         help="SQLite DB yolu")
    p.add_argument("--dry-run",     action="store_true",  help="DB'ye yazmadan test")
    p.add_argument("--clear-first", action="store_true",  help="Önce mevcut kayıtları sil")
    p.add_argument("--info",        action="store_true",  help="DB durumunu göster")
    p.add_argument("--verbose",     action="store_true",  help="Detaylı log")
    args = p.parse_args()

    if args.verbose:
        log.setLevel(logging.DEBUG)

    db_path = args.db or get_db_path()
    log.info(f"DB yolu: {db_path}")

    # CSV bul
    csv_path = args.csv or find_csv_auto()
    if csv_path:
        log.info(f"CSV: {csv_path}")
    else:
        if not args.info:
            log.error(
                "ADR_A_TABLOSU.csv bulunamadı!\n"
                "  → CSV'yi script ile aynı klasöre koyun VEYA\n"
                '  → python adr_csv_importer.py --csv "C:\\tam\\yol\\ADR_A_TABLOSU.csv"'
            )
            sys.exit(1)

    # Şema güvencesi
    ensure_schema(db_path)

    # --info modu
    if args.info:
        count = get_count(db_path)
        print(f"\n  DB      : {db_path}")
        print(f"  CSV     : {csv_path or '(bulunamadı)'}")
        print(f"  Kimyasal: {count} kayıt\n")
        return

    # Parse
    records = parse_csv(csv_path)
    if not records:
        log.error("CSV'den geçerli kayıt çıkarılamadı.")
        sys.exit(1)

    _sample(records)

    if args.dry_run:
        log.info(f"[DRY-RUN] {len(records)} kayıt hazır — DB'ye yazılmadı.")
        _summary(len(records), 0, 0)
        return

    log.info("DB'ye yazılıyor...")
    new_cnt, updated = write_records(db_path, records, clear_first=args.clear_first)
    _summary(new_cnt, updated, 0)
    log.info("✅  Aktarım tamamlandı.")
    log.info("   Şimdi adr_transport_pro_2026.py'yi açabilirsiniz.")


if __name__ == "__main__":
    main()


def import_csv_to_db(csv_path: str, db_path: str) -> int:
    """
    Ana programdan (ADRTransportPro) çağrılmak için köprü fonksiyon.
    CSV dosyasını parse edip DB'ye yazar, işlenen kayıt sayısını döner.
    """
    ensure_schema(db_path)
    records = parse_csv(csv_path)
    if not records:
        return 0
    new_cnt, updated = write_records(db_path, records, clear_first=False)
    return new_cnt + updated
