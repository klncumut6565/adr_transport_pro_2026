"""ADR 7.5.2.2 - Sınıf 1 (patlayıcı) Uyumluluk Grubu Tablosu.

Bu modül, kullanıcının paylaştığı resmi ADR 7.5.2.2 tablosunun GÖRSELİNDEN
(fotoğraf/ekran görüntüsü) doğrudan okunarak çıkarılmıştır. Önceki sürümde
bu tablo düz metne dönüştürülmüş (flattened) bir kopyadan çıkarılmıştı ve
bu sırada A↔S hücresi yanlış okunmuştu (satır kayması). Tablonun gerçek
görseli incelendiğinde A↔S çiftinin HER İKİ yönde de "boş" (izin yok)
olduğu, herhangi bir çelişki BULUNMADIĞI doğrulanmıştır.

Harfler:
  X   -> Karışık yüklemeye izin verilir.
  a   -> İzin verilir, ANCAK etkili fiziksel ayırma (ayrı bölme veya özel
         muhafaza) şarttır (uyumluluk grubu B ile D arası, infilak
         aktarımı riskine karşı).
  b   -> Sadece alt grup 1.6 N nesneleri kendi aralarında, ilave infilak
         riski taşımadıkları test/karşılaştırmalarla kanıtlanmışsa
         birlikte taşınabilir; aksi halde alt grup 1.1 kabul edilir.
  bc  -> N grubu nesneleri C/D/E grubu maddeleriyle birlikte
         taşındığında, yukarıdaki "b" koşuluna ek olarak, N grubunun D
         grubu özelliklerini taşıdığı kabul edilir (not c).
  d   -> L grubu maddeleri SADECE aynı L grubuna dahil tiplerle
         birlikte yüklenebilir (genel "L ile L" izni değil, tip bazlı
         sınırlama).
  (boş)-> Karışık yüklemeye izin verilmez.
"""

from __future__ import annotations

from dataclasses import dataclass

GROUPS = ("A", "B", "C", "D", "E", "F", "G", "H", "J", "L", "N", "S")

# Satır sırası ve her satırın 12 sütuna (A..S) karşılık gelen değeri.
# None = izin yok (boş hücre). "X" = izin var. Diğerleri dipnot kodu.
_TABLE: dict[str, dict[str, str | None]] = {
    "A": {"A": "X", "B": None, "C": None, "D": None, "E": None, "F": None,
          "G": None, "H": None, "J": None, "L": None, "N": None, "S": None},
    "B": {"A": None, "B": "X", "C": None, "D": "a", "E": None, "F": None,
          "G": None, "H": None, "J": None, "L": None, "N": None, "S": "X"},
    "C": {"A": None, "B": None, "C": "X", "D": "X", "E": "X", "F": None,
          "G": "X", "H": None, "J": None, "L": None, "N": "bc", "S": "X"},
    "D": {"A": None, "B": "a", "C": "X", "D": "X", "E": "X", "F": None,
          "G": "X", "H": None, "J": None, "L": None, "N": "bc", "S": "X"},
    "E": {"A": None, "B": None, "C": "X", "D": "X", "E": "X", "F": None,
          "G": "X", "H": None, "J": None, "L": None, "N": "bc", "S": "X"},
    "F": {"A": None, "B": None, "C": None, "D": None, "E": None, "F": "X",
          "G": None, "H": None, "J": None, "L": None, "N": None, "S": "X"},
    "G": {"A": None, "B": None, "C": "X", "D": "X", "E": "X", "F": None,
          "G": "X", "H": None, "J": None, "L": None, "N": None, "S": "X"},
    "H": {"A": None, "B": None, "C": None, "D": None, "E": None, "F": None,
          "G": None, "H": "X", "J": None, "L": None, "N": None, "S": "X"},
    "J": {"A": None, "B": None, "C": None, "D": None, "E": None, "F": None,
          "G": None, "H": None, "J": "X", "L": None, "N": None, "S": "X"},
    "L": {"A": None, "B": None, "C": None, "D": None, "E": None, "F": None,
          "G": None, "H": None, "J": None, "L": "d", "N": None, "S": None},
    "N": {"A": None, "B": None, "C": "bc", "D": "bc", "E": "bc", "F": None,
          "G": None, "H": None, "J": None, "L": None, "N": "b", "S": "X"},
    "S": {"A": None, "B": "X", "C": "X", "D": "X", "E": "X", "F": "X",
          "G": "X", "H": "X", "J": "X", "L": None, "N": "X", "S": "X"},
}

_FOOTNOTE_TEXT = {
    "a": (
        "Uyumluluk grubu B nesneleri ile D maddeleri/nesneleri, infilak "
        "aktarımı riskine karşı etkili biçimde ayrılmaları (ayrı bölme "
        "veya özel muhafaza, yetkili makam onayına tabi) koşuluyla "
        "birlikte yüklenebilir (ADR 7.5.2.2 not a)."
    ),
    "b": (
        "Alt grup 1.6 N nesneleri, ancak ilave infilak riski taşımadıkları "
        "test/karşılaştırmalarla kanıtlanmışsa birbirleriyle birlikte "
        "taşınabilir; aksi halde alt grup 1.1 olarak kabul edilmelidir "
        "(ADR 7.5.2.2 not b)."
    ),
    "bc": (
        "Alt grup 1.6 N nesneleri, ancak ilave infilak riski taşımadıkları "
        "kanıtlanmışsa (not b) ve bu durumda C/D/E grubu madde/nesneleriyle "
        "birlikte taşındıklarında D grubunun özelliklerini taşıdığı kabul "
        "edilerek (not c) birlikte yüklenebilir (ADR 7.5.2.2 not b ve c)."
    ),
    "d": (
        "L grubu maddeleri/nesneleri SADECE aynı L grubuna dahil madde/"
        "nesne tipleriyle birlikte yüklenebilir (ADR 7.5.2.2 not d)."
    ),
}


@dataclass(slots=True)
class CompatibilityVerdict:
    group1: str
    group2: str
    permitted: bool  # True/False (artık hiçbir çift "bilinmiyor" değil)
    conditional: bool
    note: str


def lookup_compatibility(group1: str, group2: str) -> CompatibilityVerdict | None:
    """İki uyumluluk grubu (A-S) arasındaki ADR 7.5.2.2 sonucunu döndürür.

    Gruplardan biri tanınmıyorsa None döner (çağıran taraf bunu "veri
    eksik, manuel kontrol gerekir" olarak ele almalıdır).
    """

    g1, g2 = group1.upper().strip(), group2.upper().strip()
    if g1 not in GROUPS or g2 not in GROUPS:
        return None

    cell = _TABLE[g1].get(g2)

    if cell is None:
        return CompatibilityVerdict(
            g1, g2, permitted=False, conditional=False,
            note=f"Uyumluluk grubu {g1} ile {g2} arasında karışık yükleme yasaktır (ADR 7.5.2.2).",
        )

    if cell == "X":
        return CompatibilityVerdict(
            g1, g2, permitted=True, conditional=False,
            note=f"Uyumluluk grubu {g1} ile {g2} arasında karışık yüklemeye izin verilir (ADR 7.5.2.2).",
        )

    # a / b / bc / d -> koşullu izin
    return CompatibilityVerdict(
        g1, g2, permitted=True, conditional=True, note=_FOOTNOTE_TEXT.get(cell, ""),
    )
