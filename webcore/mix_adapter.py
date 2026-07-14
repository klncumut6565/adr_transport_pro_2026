"""adr_mix_pro entegrasyonu — GERÇEK Karışık Yükleme motoru.

DÜZELTME (Umut'un tespiti): web tarafında hem "Karışık Yükleme Kontrolü"
sayfası hem ADR Kontrol Merkezi paneli, `webcore.engines.ADREngine.
check_compatibility` adında BASİTLEŞTİRİLMİŞ bir kontrol kullanıyordu —
yalnızca segregation_group + sabit bir INCOMPATIBILITY_MATRIX sözlüğüne
dayanan kaba bir yaklaşımdı. Oysa masaüstü, "ADR Mix Checker Pro v2.4.1"
kökenli, 71 birim testli, çok daha kapsamlı GERÇEK bir motor kullanıyor:
`adr_mix_pro` paketi (segregasyon kural motoru + Sınıf 1 patlayıcı
dipnotları a/b/c/d + CV28 gıda ayrımı kuralları + tünel kısıtı notları +
risk puanlama). Bu paket repoda zaten duruyor (adr_mix_pro/), Qt'ye hiç
bağımlı değil — yalnızca web'e HİÇ BAĞLANMAMIŞTI.

Bu modül, masaüstünün `AnaDbChemicalAdapter` sınıfının (adr_transport_
pro_2026.py) BİREBİR web karşılığıdır: adr_mix_pro'nun beklediği
ProductDatabase arayüzünü (try_get_record/all_records/search), dosya
tabanlı bir Excel yerine webcore'un PostgreSQL chemicals tablosuna
bağlar. SQL sorguları masaüstünden birebir alındı — webcore.pg'nin
TranslatingCursor'ı `?`→`%s` ve `LIKE`→`ILIKE` çevirisini otomatik
yaptığı için sorgu metinleri değişmeden çalışır.

Aynı UN numarasının Tablo A'da birden fazla varyasyonu olabileceği için
(ör. UN1950 → 12 satır, sınıflandırma kodu/PG'ye göre ayrışır), adaptör
kayıtları ÖNCEDEN toptan yüklemez: her UN, register_variant() ile HANGİ
varyasyonun kullanılacağı açıkça belirtildikten sonra belleğe alınır —
yanlış/rastgele bir varyasyonun sessizce kullanılması böylece engellenir
(masaüstündeki tasarım kararı, aynen korundu).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from adr_mix_pro.core.checker import MixChecker
from adr_mix_pro.core.rule_engine import SegregationRuleEngine
from adr_mix_pro.models import ProductRecord
from adr_mix_pro.validators import normalize_un

_KURAL_DOSYASI = (Path(__file__).resolve().parent.parent
                  / "resources" / "data" / "segregation_rules.csv")


class PgChemicalAdapter:
    """Masaüstündeki AnaDbChemicalAdapter'ın PostgreSQL karşılığı."""

    def __init__(self, db):
        self.db = db
        self._records_by_un: Dict[str, ProductRecord] = {}

    @staticmethod
    def _extract_cv_codes(special_provisions: str) -> str:
        if not special_provisions:
            return ""
        codes = re.findall(r"CV\d+", special_provisions, re.IGNORECASE)
        return " ".join(sorted(set(c.upper() for c in codes)))

    def _row_to_record(self, row: dict) -> ProductRecord:
        labels_raw = row.get("hazard_labels") or ""
        labels = [l.strip() for l in labels_raw.replace(",", " ").split() if l.strip()]
        if not labels and row.get("class_code"):
            labels = [str(row["class_code"]).strip()]
        return ProductRecord(
            un_no=row["un_number"],
            name=row.get("proper_shipping_name_tr") or row.get("proper_shipping_name_en") or "",
            hazard_class=row.get("class_code") or "",
            classification_code=row.get("classification_code") or "",
            packing_group=row.get("packing_group") or "",
            labels=labels,
            special_provisions=row.get("special_provisions") or "",
            transport_category=row.get("transport_category") or "",
            cv_codes=self._extract_cv_codes(row.get("special_provisions") or ""),
            tunnel_code=row.get("tunnel_code") or "",
            raw=dict(row),
        )

    def get_variants(self, un: str) -> List[dict]:
        """Verilen UN için TÜM Tablo A varyasyonlarını (composite anahtar)
        döndürür; birden fazla olabilir (ör. UN1950 -> 12 satır)."""
        un = normalize_un(un)
        rows = self.db.execute(
            "SELECT * FROM chemicals WHERE un_number=? "
            "ORDER BY classification_code, packing_group",
            (un,))
        return rows or []

    def register_variant(self, un: str, classification_code: str = "",
                         packing_group: str = "") -> Optional[ProductRecord]:
        """Kullanıcının (veya sevkiyat kaleminin) seçtiği TAM varyasyonu
        belleğe alır; bundan sonra try_get_record(un) bu kaydı döndürür."""
        un = normalize_un(un)
        row = self.db.execute_one(
            "SELECT * FROM chemicals WHERE un_number=? AND classification_code=? "
            "AND packing_group=?",
            (un, classification_code or "", packing_group or ""))
        if not row:
            rows = self.get_variants(un)
            row = rows[0] if rows else None
        if row:
            rec = self._row_to_record(row)
            self._records_by_un[un] = rec
            return rec
        return None

    def register_unknown(self, un: str) -> None:
        """Veritabanında bulunamayan UN için boş/etiketsiz kayıt — checker
        bunu UNKNOWN olarak işaretler, çökme olmaz."""
        un = normalize_un(un)
        self._records_by_un[un] = ProductRecord(un_no=un, name="", labels=[])

    # --- adr_mix_pro ProductDatabase arayüzü -----------------------------
    def try_get_record(self, un: str) -> Optional[ProductRecord]:
        return self._records_by_un.get(normalize_un(un))

    def all_records(self) -> List[ProductRecord]:
        return list(self._records_by_un.values())

    def search(self, query: str, limit: int = 200) -> List[ProductRecord]:
        q = query.strip()
        if not q:
            return []
        if q.isdigit():
            rows = self.db.execute(
                "SELECT * FROM chemicals WHERE un_number=? LIMIT ?",
                (q.zfill(4), limit))
        else:
            rows = self.db.execute(
                "SELECT * FROM chemicals WHERE proper_shipping_name_tr LIKE ? "
                "OR proper_shipping_name_en LIKE ? LIMIT ?",
                (f"%{q}%", f"%{q}%", limit))
        return [self._row_to_record(r) for r in (rows or [])]


def gercek_mix_checker(db) -> Optional[MixChecker]:
    """Verilen webcore veritabanı bağlantısı için, masaüstüyle AYNI
    (dosyadan yüklenen, 71 testli) kural motoruna bağlı bir MixChecker
    örneği kurar. Kural dosyası bulunamazsa None döner (çağıran,
    eski/basit kontrolüne düşebilir — ama repoda bu dosya zaten var)."""
    try:
        rule_engine = SegregationRuleEngine(_KURAL_DOSYASI)
    except Exception:
        return None
    adapter = PgChemicalAdapter(db)
    return MixChecker(adapter, rule_engine), adapter
