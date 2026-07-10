"""Veri modelleri (dataclasses).

Önceki dağınık sürümde kayıtlar serbest (loosely-typed) sözlükler (dict)
olarak dolaşıyordu; bu, yazım hatalarının (örn. ``r["isim"]`` vs
``r["name"]``) çalışma zamanına kadar fark edilmemesine yol açıyordu.
Burada tip kontrolü ve okunabilirlik için ``dataclass`` kullanılmıştır.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_GROUP_SUFFIX_RE = re.compile(r"^1\.[1-6]([A-Z])$")


@dataclass(slots=True)
class ProductRecord:
    """Veri dosyasındaki tek bir ürün/madde satırını temsil eder."""

    un_no: str = ""
    name: str = ""
    hazard_class: str = ""
    classification_code: str = ""
    packing_group: str = ""
    labels: list[str] = field(default_factory=list)
    special_provisions: str = ""
    transport_category: str = ""
    cv_codes: str = ""
    tunnel_code: str = ""
    danger_number: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return self.name or "(isim bulunamadı)"

    @property
    def compatibility_group(self) -> str | None:
        """Sınıf 1 (patlayıcı) uyumluluk grubunu (A-S) belirlemeye çalışır.

        Önce etiketlere (örn. "1.4S"), sonra sınıflandırma koduna (örn.
        "1.1D") bakar. Hiçbirinde bulunamazsa None döner. Bu, hem
        ``core/segregation_engine.py``'nin ADR 7.5.2.2 hesaplaması hem de
        arayüzün ürün bilgisi gösterimi tarafından paylaşılan TEK bir
        çıkarım noktasıdır (mükerrer mantık önlenir).
        """

        candidates = list(self.labels) + [self.classification_code]
        for candidate in candidates:
            if not candidate:
                continue
            match = _GROUP_SUFFIX_RE.match(candidate.strip().upper())
            if match:
                return match.group(1)
        return None

    @property
    def is_class1(self) -> bool:
        """Etiketlerden herhangi biri Sınıf 1 (patlayıcı) ise True döner."""

        prefixes = ("1.1", "1.2", "1.3", "1.4", "1.5", "1.6")
        return any(l == "1" or l.startswith(prefixes) for l in self.labels)


@dataclass(slots=True)
class SegregationVerdict:
    """İki etiket arasındaki ham segregasyon kuralı sonucu."""

    label1: str
    label2: str
    status: str
    adr_reference: str
    description: str


@dataclass(slots=True)
class PairCheckResult:
    """İki UN numarası (ürün) arasındaki tam karşılaştırma sonucu."""

    un1: str
    un2: str
    name1: str
    name2: str
    labels1: list[str]
    labels2: list[str]
    status: str
    adr_reference: str
    reason: str
    risk_score: int = 0
    matched_label1: str = ""
    matched_label2: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def is_forbidden(self) -> bool:
        from .constants import STATUS_FORBIDDEN

        return self.status == STATUS_FORBIDDEN

    @property
    def pair_label(self) -> str:
        return f"{self.un1} ↔ {self.un2}"
