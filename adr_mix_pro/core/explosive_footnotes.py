"""ADR 7.5.2.1 Tablosu dipnotları (a, b, c, d) - Sınıf 1 ↔ diğer sınıflar.

DİKKAT: Bu modüldeki a/b/c/d harfleri, ``compatibility_groups.py``
içindeki ADR 7.5.2.2 dipnotlarıyla AYNI HARFLERİ kullanır ama TAMAMEN
FARKLI kurallardır (7.5.2.1 dipnotları Sınıf 1 ile DİĞER sınıflar
arasındaki istisnalar; 7.5.2.2 dipnotları Sınıf 1'in KENDİ İÇİNDEKİ
uyumluluk grupları arasındaki istisnalardır). İsim çakışmasını önlemek
için burada ``FOOTNOTE_2101_*`` öneki kullanılmıştır.

Kaynak: Kullanıcının paylaştığı resmi ADR 7.5.2.1 metni.
"""

from __future__ import annotations

from dataclasses import dataclass

# Not b: UN 2990, 3072, 3268 (Sınıf 9 hayat kurtarıcı araçlar) - Sınıf 1 ile
# karışık yüklemeye izin verilir.
FOOTNOTE_B_LIFESAVING_UN = frozenset({"2990", "3072", "3268"})

# Not c: UN 0503 (alt grup 1.4, uyumluluk grubu G, emniyet cihazı) ile
# UN 3268 (Sınıf 9, elektrikle başlatılan emniyet cihazı) arasında.
FOOTNOTE_C_PAIR = (frozenset({"0503"}), frozenset({"3268"}))

# Not d: tahripli patlayıcılar + amonyum nitrat türevleri ile alkali metal /
# alkalin toprak metal nitratları arasında (hepsi Sınıf 1 tahripli patlayıcı
# gibi muamele görmesi koşuluyla).
FOOTNOTE_D_EXPLOSIVE_SIDE_UN = frozenset({"1942", "2067", "3375"})
FOOTNOTE_D_NITRATE_SIDE_UN = frozenset(
    {
        "1451", "2722", "1486", "1477", "1498",  # alkali metal nitratları
        "1446", "2464", "1454", "1474", "1507",  # alkalin toprak metal nitratları
    }
)
# UN 0083 de bu istisnaya dahildir, ANCAK "patlayıcı, tahripli, tip C"
# hariçtir. Bu modülde "tip" verisi modellenmediğinden, UN 0083 bu
# istisnaya OTOMATİK dahil edilmez; tespit edilirse açıklamada bu nüans
# kullanıcıya hatırlatılır.
FOOTNOTE_D_UN0083 = "0083"


@dataclass(slots=True)
class FootnoteVerdict:
    code: str  # "a" | "b" | "c" | "d"
    note: str


def check_footnote_a(group1: str | None, group2: str | None) -> FootnoteVerdict | None:
    """Not a: Uyumluluk grubu S olan Sınıf 1 maddeleri, Sınıf 1 DIŞINDAKİ
    her sınıfla karışık yüklenebilir."""

    if group1 == "S" or group2 == "S":
        return FootnoteVerdict(
            code="a",
            note=(
                "Not a: Uyumluluk grubu S olan Sınıf 1 madde/nesneleri, "
                "Sınıf 1 dışındaki maddelerle karışık yüklenebilir "
                "(ADR 7.5.2.1 not a)."
            ),
        )
    return None


def check_footnote_b(un1: str, un2: str, has_class9_label: bool) -> FootnoteVerdict | None:
    """Not b: UN 2990/3072/3268 (Sınıf 9 hayat kurtarıcı araç) - Sınıf 1."""

    if not has_class9_label:
        return None
    if un1 in FOOTNOTE_B_LIFESAVING_UN or un2 in FOOTNOTE_B_LIFESAVING_UN:
        return FootnoteVerdict(
            code="b",
            note=(
                "Not b: Sınıf 9 hayat kurtarıcı araç (UN 2990, 3072 veya "
                "3268) ile Sınıf 1 arasında karışık yüklemeye izin "
                "verilmiştir (ADR 7.5.2.1 not b)."
            ),
        )
    return None


def check_footnote_c(un1: str, un2: str) -> FootnoteVerdict | None:
    """Not c: UN 0503 (1.4G emniyet cihazı) ↔ UN 3268 (Sınıf 9 emniyet cihazı)."""

    pair = frozenset({un1, un2})
    if {un1} == set(FOOTNOTE_C_PAIR[0]) and {un2} == set(FOOTNOTE_C_PAIR[1]):
        match = True
    elif {un2} == set(FOOTNOTE_C_PAIR[0]) and {un1} == set(FOOTNOTE_C_PAIR[1]):
        match = True
    else:
        match = False

    if match:
        return FootnoteVerdict(
            code="c",
            note=(
                "Not c: Alt grup 1.4, uyumluluk grubu G piroteknik emniyet "
                "cihazı (UN 0503) ile Sınıf 9 elektrikle başlatılan emniyet "
                "cihazı (UN 3268) arasında karışık yüklemeye izin "
                "verilmiştir (ADR 7.5.2.1 not c)."
            ),
        )
    return None


def check_footnote_d(explosive_un: str, other_un: str) -> FootnoteVerdict | None:
    """Not d: Tahripli patlayıcılar/amonyum nitrat ↔ alkali (toprak) metal nitratları.

    ``explosive_un``, çağıran taraf tarafından ZATEN Sınıf 1 etiketli
    olduğu doğrulanmış kaydın UN numarasıdır (bkz. segregation_engine.py).
    UN 0083 ("patlayıcı, tahripli, tip C"), metindeki "tip C hariç"
    ifadesi nedeniyle bu istisnadan HARİÇ TUTULUR.
    """

    if explosive_un == FOOTNOTE_D_UN0083:
        return None

    nitrate_or_ammonium_side = FOOTNOTE_D_NITRATE_SIDE_UN | FOOTNOTE_D_EXPLOSIVE_SIDE_UN
    if other_un in nitrate_or_ammonium_side:
        return FootnoteVerdict(
            code="d",
            note=(
                "Not d: Tahripli patlayıcılar / amonyum nitrat türevleri "
                "ile alkali metal veya alkalin toprak metal nitratları "
                "arasında, TÜMÜNÜN levha takma, ayırma, istifleme ve "
                "izin verilen azami yük amaçları bakımından Sınıf 1 "
                "tahripli patlayıcı olarak muamele görmesi koşuluyla "
                "karışık yüklemeye izin verilmiştir (ADR 7.5.2.1 not d)."
            ),
        )

    # explosive_un'un kendisi UN 1942/2067/3375 olabilir (bu maddeler
    # normalde "5.1" etiketli olduğundan, çağıran tarafta "explosive_un"
    # rolünde DEĞİL "other_un" rolünde gelmesi beklenir; ancak veri
    # tutarsızlığına karşı burada da kontrol edilir).
    if explosive_un in FOOTNOTE_D_EXPLOSIVE_SIDE_UN and other_un in FOOTNOTE_D_NITRATE_SIDE_UN:
        return FootnoteVerdict(
            code="d",
            note=(
                "Not d: Amonyum nitrat türevi ile alkali metal veya "
                "alkalin toprak metal nitratları arasında, Sınıf 1 "
                "tahripli patlayıcı olarak muamele görmesi koşuluyla "
                "karışık yüklemeye izin verilmiştir (ADR 7.5.2.1 not d)."
            ),
        )

    return None
