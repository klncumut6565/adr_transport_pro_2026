"""İki ürün kaydı arasında etiket bazlı segregasyon (ayrım) kontrolü.

Bir üründe birden fazla etiket olabilir (örn. ana tehlike + yan tehlike,
"3+6.1" gibi). Bu motor, iki ürünün TÜM etiket kombinasyonlarını
``SegregationRuleEngine`` üzerinden kontrol eder ve en olumsuz sonucu
döndürür.

SINIF 1 (PATLAYICI) MANTIĞI (v2.3 - ADR 7.5.2.1 NOT 2 + 7.5.2.2 + dipnotlar):

ADR 7.5.2.1'in tablo başlangıcındaki "NOT 2" metni, bu motorun mimarisinin
doğrudan kaynağıdır:

    "Yalnız Sınıf 1'e ait nesne veya maddeler içeren ve Model No. 1, 1.4,
    1.5 ve 1.6'ya uygun ETİKET taşıyan ambalajlarda, bu ambalajlar için
    istenen diğer tehlike etiketlerine bakılmaksızın, 7.5.2.2 uyarınca
    karışık yüklemeye izin verilir. 7.5.2.1'deki Tablo, SADECE, söz konusu
    ambalajlar, DİĞER SINIFLARDAN madde veya nesneler içeren ambalajlarla
    birlikte yüklendiğinde geçerlidir."

Bu, iki ayrı veri alanının KARIŞTIRILMAMASINI gerektirir:
  - "Model No." / ETİKET (örn. "1.4")  -> ADR Bölüm 5.2 tehlike etiketi
    model numarası; Tablo A'nın "Etiketler" sütunu. ``ProductRecord.labels``
    alanından okunur. Bir kalemin Sınıf 1 olup olmadığını ve 7.5.2.1
    tablosunda hangi SATIRA denk geldiğini belirlemek için kullanılır.
  - SINIFLANDIRMA KODU (örn. "1.4S") -> Tablo A'nın 3b sütunu; bölüm
    numarası + uyumluluk grubu harfi. ``ProductRecord.classification_code``
    (ve dolaylı olarak ``ProductRecord.compatibility_group``) alanından
    okunur. ADR 7.5.2.2 uyumluluk grubu tablosu ve 7.5.2.1'in "a" dipnotu
    (uyumluluk grubu S istisnası) İÇİN kullanılır — asla "etiket" alanıyla
    karıştırılmaz, çünkü gerçek dünya verilerinde Etiketler sütunu HİÇBİR
    ZAMAN uyumluluk grubu harfini taşımaz (sadece Sınıflandırma kodu
    sütunu taşır).

Bu motor şu sırayla çalışır:
  1) İki taraf da Sınıf 1 ise (``record.labels`` üzerinden tespit edilir)
     -> NOT 2 gereği, hangi DİĞER etiketleri taşıdıklarına bakılmaksızın
     doğrudan ``compatibility_groups.py`` (ADR 7.5.2.2) kullanılır. Her
     iki tarafın uyumluluk grubu (``record.compatibility_group``, yani
     sınıflandırma kodundan) belirlenebiliyorsa KESİN bir sonuç üretilir.
  2) Sadece bir taraf Sınıf 1 ise -> NOT 2 gereği, BU durumda 7.5.2.1
     Tablosu (ve dipnotları a/b/c/d, bkz. ``explosive_footnotes.py``)
     devreye girer: uyumluluk grubu S istisnası (not a), UN 2990/3072/
     3268 hayat kurtarıcı araç istisnası (not b), UN 0503↔3268 istisnası
     (not c), UN 1942/2067/3375 ↔ alkali (toprak) metal nitratları
     istisnası (not d). ÖNEMLİ: Not d, gerçek tabloda SADECE "Etiket
     No. 1" satırında (Alt Grup 1.1/1.2/1.3 - "tahripli patlayıcılar")
     bir adaydır; 1.4/1.5/1.6 satırlarında HİÇ yer almaz (kullanıcı
     tarafından gerçek tablo görseliyle doğrulanmıştır). Bu yüzden not d,
     sadece kayıt "Etiket No. 1" satırına denk geliyorsa denenir (bkz.
     ``_is_mass_explosive_row``); 1.4/1.5/1.6 için UN numarası eşleşse
     bile hiç denenmez - bu, gerçek tablo yapısını birebir yansıtır.
  3) KRİTİK (v2.4'te düzeltildi): 7.5.2.1 tablosunda Sınıf 1 ↔ diğer sınıf
     kesişen HİÇBİR hücrede şartsız "X" yoktur — her hücre ya boştur (hiç
     istisna yok) ya da bir dipnotla sınırlıdır. Bu yüzden, dipnotlardan
     hiçbiri eşleşmediğinde sonuç varsayılan olarak "STATUS_FORBIDDEN"dır
     (örn. UN 0027 [1.1D] ile UN 3077 [Sınıf 9] — hiçbir dipnot UN
     3077'yi kapsamadığından kesin yasaktır). TEK İSTİSNA: patlayıcı
     tarafın uyumluluk grubu belirlenemiyorsa (None), "a" dipnotu (sadece
     grup S) kesin olarak elenemediğinden sonuç "EXPLOSIVE_SPECIAL"
     (manuel kontrol gerekir) kalır — bu, veri eksikliğinden kaynaklanan
     GERÇEK bir belirsizliktir, "tembel" bir varsayılan değildir.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..constants import (
    STATUS_EXPLOSIVE_SPECIAL,
    STATUS_FORBIDDEN,
    STATUS_OK,
    STATUS_UNKNOWN,
)
from ..models import ProductRecord, SegregationVerdict
from . import compatibility_groups as cg
from . import explosive_footnotes as fn
from .rule_engine import SegregationRuleEngine

_EXPLOSIVE_LABEL_PREFIXES = ("1.1", "1.2", "1.3", "1.4", "1.5", "1.6")


def _is_explosive_label(label: str) -> bool:
    """Bir etiketin Sınıf 1 (patlayıcı) olup olmadığını kontrol eder.

    Yalnızca tam eşleşme ("1", "1.4") değil, uyumluluk grubu harfi eklenmiş
    biçimleri de (örn. "1.4S", "1.4G", "1.1A") yakalamak için önek (prefix)
    kontrolü yapılır.
    """

    if label == "1":
        return True
    return label.startswith(_EXPLOSIVE_LABEL_PREFIXES)


def _has_class9_label(record: ProductRecord) -> bool:
    return "9" in record.labels or record.hazard_class.strip() == "9"


# ADR Bölüm 5.2'de Sınıf 1 için sadece 4 etiket modeli vardır: 1, 1.4,
# 1.5, 1.6. Alt Gruplar 1.1, 1.2 ve 1.3 KENDİ etiketlerine sahip
# DEĞİLDİR; hepsi "Etiket No. 1" altında taşınır (bkz. Tablo A "Etiketler"
# sütunu, sadece bu 4 değeri alır). 7.5.2.1 tablosunda "Not d" SADECE bu
# "Etiket No. 1" satırında görünür (örn. 5.1 sütununda); 1.4/1.5/1.6
# satırlarında HİÇ aday bile değildir. Bu nedenle "Not d" sadece gerçek
# kayıtta etiket "1" (veya - veri kalitesi için tolerans amaçlı - "1.1",
# "1.2", "1.3" şeklinde görülürse) denenir; "1.4", "1.5", "1.6" için HİÇ
# denenmez (UN numarası eşleşmese de denemek, gerçek tablo yapısını
# yanlış yansıtır).
_MASS_EXPLOSIVE_PREFIXES = ("1.1", "1.2", "1.3")


def _is_mass_explosive_row(record: ProductRecord) -> bool:
    """Kaydın ADR 7.5.2.1 tablosunda 'Etiket No. 1' satırına (Alt Grup
    1.1/1.2/1.3) denk gelip gelmediğini kontrol eder. 1.4/1.5/1.6 için
    False döner (onlar kendi ayrı satırlarına denk gelir)."""

    return any(
        l == "1" or l.startswith(_MASS_EXPLOSIVE_PREFIXES) for l in record.labels
    )


# Sonuç önceliği: sayı küçük olan, daha "ciddi"/öncelikli kabul edilir.
_STATUS_PRIORITY = {
    STATUS_FORBIDDEN: 0,
    STATUS_EXPLOSIVE_SPECIAL: 1,
    STATUS_UNKNOWN: 2,
    STATUS_OK: 3,
}


@dataclass(slots=True)
class SegregationCheckOutcome:
    status: str
    adr_reference: str
    description: str
    matched_label1: str
    matched_label2: str


class SegregationEngine:
    def __init__(self, rule_engine: SegregationRuleEngine):
        self.rule_engine = rule_engine

    def check_pair(
        self, record1: ProductRecord, record2: ProductRecord
    ) -> SegregationCheckOutcome:
        labels1 = [l for l in (record1.labels or [record1.hazard_class]) if l]
        labels2 = [l for l in (record2.labels or [record2.hazard_class]) if l]

        if not labels1 or not labels2:
            return SegregationCheckOutcome(
                status=STATUS_UNKNOWN,
                adr_reference="7.5.2.1",
                description="Etiket bilgisi eksik; karşılaştırma yapılamadı.",
                matched_label1=",".join(labels1),
                matched_label2=",".join(labels2),
            )

        explosive1 = any(_is_explosive_label(l) for l in labels1)
        explosive2 = any(_is_explosive_label(l) for l in labels2)

        if explosive1 or explosive2:
            return self._check_explosive_interaction(
                record1, record2, explosive1, explosive2
            )

        best: SegregationCheckOutcome | None = None

        for l1 in labels1:
            for l2 in labels2:
                outcome = self._check_ordinary_label_pair(l1, l2)
                if best is None or _STATUS_PRIORITY[outcome.status] < _STATUS_PRIORITY[best.status]:
                    best = outcome
                if best is not None and best.status == STATUS_FORBIDDEN:
                    return best

        assert best is not None
        return best

    # ------------------------------------------------------------------
    # Sınıf 1 (patlayıcı) etkileşimleri
    # ------------------------------------------------------------------
    def _check_explosive_interaction(
        self,
        record1: ProductRecord,
        record2: ProductRecord,
        explosive1: bool,
        explosive2: bool,
    ) -> SegregationCheckOutcome:
        un1, un2 = record1.un_no, record2.un_no

        if explosive1 and explosive2:
            return self._check_class1_vs_class1(record1, record2)

        # Tam olarak bir taraf Sınıf 1: 7.5.2.1 dipnotlarını dene.
        explosive_record = record1 if explosive1 else record2
        other_record = record2 if explosive1 else record1
        group = explosive_record.compatibility_group

        footnote_a = fn.check_footnote_a(group, None)
        if footnote_a:
            return SegregationCheckOutcome(
                status=STATUS_EXPLOSIVE_SPECIAL,
                adr_reference="7.5.2.1",
                description=footnote_a.note,
                matched_label1=un1,
                matched_label2=un2,
            )

        footnote_b = fn.check_footnote_b(un1, un2, _has_class9_label(record1) or _has_class9_label(record2))
        if footnote_b:
            return SegregationCheckOutcome(
                status=STATUS_EXPLOSIVE_SPECIAL,
                adr_reference="7.5.2.1",
                description=footnote_b.note,
                matched_label1=un1,
                matched_label2=un2,
            )

        footnote_c = fn.check_footnote_c(un1, un2)
        if footnote_c:
            return SegregationCheckOutcome(
                status=STATUS_EXPLOSIVE_SPECIAL,
                adr_reference="7.5.2.1",
                description=footnote_c.note,
                matched_label1=un1,
                matched_label2=un2,
            )

        # Not d, gerçek tabloda SADECE "Etiket No. 1" satırında (Alt Grup
        # 1.1/1.2/1.3) bir aday olarak görünür; 1.4/1.5/1.6 satırlarında
        # bu dipnot HİÇ yer almaz. Bu yüzden önce satır uygunluğu
        # kontrol edilir; UN numarası eşleşmese de olsa, 1.4/1.5/1.6 için
        # bu dipnot hiç denenmemelidir (kullanıcı tarafından gerçek
        # tablo görseliyle doğrulanmıştır: 1.4 × Sınıf 9 kesişiminde
        # sadece a/b/c dipnotları vardır, d hiç aday değildir).
        footnote_d = None
        if _is_mass_explosive_row(explosive_record):
            footnote_d = fn.check_footnote_d(explosive_record.un_no, other_record.un_no)
        if footnote_d:
            return SegregationCheckOutcome(
                status=STATUS_EXPLOSIVE_SPECIAL,
                adr_reference="7.5.2.1",
                description=footnote_d.note,
                matched_label1=un1,
                matched_label2=un2,
            )

        # Hiçbir dipnot eşleşmedi. KRİTİK NOKTA (gerçek veriyle test edilip
        # düzeltilmiştir): ADR 7.5.2.1 tablosunda Sınıf 1 ↔ diğer sınıf
        # kesişen HER hücre ya BOŞTUR (hiç istisna yok) ya da bir dipnotla
        # SINIRLIDIR (sadece o dipnotun şartı karşılanırsa izin var). Hiçbir
        # hücrede şartsız "X" yoktur. Bu yüzden dipnotlardan hiçbiri
        # eşleşmediğinde sonuç "belki" değil, "HAYIR"dır — TEK İSTİSNA: "a"
        # dipnotunu (sadece uyumluluk grubu S) kesin olarak ELEYEMEDİYSEK
        # (yani grup bilinmiyorsa), o zaman gerçekten "bilmiyorum" demeliyiz.
        if group is None:
            return SegregationCheckOutcome(
                status=STATUS_EXPLOSIVE_SPECIAL,
                adr_reference="7.5.2.1",
                description=(
                    f"UN {explosive_record.un_no} için uyumluluk grubu "
                    "belirlenemediğinden, 'a' dipnotu (yalnızca uyumluluk "
                    "grubu S istisnası) kesin olarak elenemiyor. Sınıflandırma "
                    "kodunu (örn. '1.4S') kontrol edip veritabanına ekleyin; "
                    "aksi halde manuel doğrulama gerekir."
                ),
                matched_label1=un1,
                matched_label2=un2,
            )

        return SegregationCheckOutcome(
            status=STATUS_FORBIDDEN,
            adr_reference="7.5.2.1",
            description=(
                f"Sınıf 1 (uyumluluk grubu {group}) ile "
                f"'{other_record.hazard_class or ','.join(other_record.labels)}' "
                "arasında ADR 7.5.2.1 dipnotlarından (a/b/c/d) hiçbiri "
                "karşılanmıyor; bu tabloda istisnasız hücreler boş "
                "bırakıldığından (asla şartsız 'X' yoktur) karışık "
                "yükleme YASAKTIR."
            ),
            matched_label1=un1,
            matched_label2=un2,
        )

    def _check_class1_vs_class1(
        self, record1: ProductRecord, record2: ProductRecord
    ) -> SegregationCheckOutcome:
        group1 = record1.compatibility_group
        group2 = record2.compatibility_group

        if group1 is None or group2 is None:
            missing = record1.un_no if group1 is None else record2.un_no
            return SegregationCheckOutcome(
                status=STATUS_EXPLOSIVE_SPECIAL,
                adr_reference="7.5.2.2",
                description=(
                    f"İki taraf da Sınıf 1 ancak UN {missing} için uyumluluk "
                    "grubu (örn. '1.4S' biçiminde) belirlenemedi; ADR "
                    "7.5.2.2 tablosuna göre manuel kontrol gerekir."
                ),
                matched_label1=record1.un_no,
                matched_label2=record2.un_no,
            )

        verdict = cg.lookup_compatibility(group1, group2)
        if verdict is None:
            return SegregationCheckOutcome(
                status=STATUS_EXPLOSIVE_SPECIAL,
                adr_reference="7.5.2.2",
                description=(
                    f"Tanınmayan uyumluluk grubu ('{group1}' / '{group2}'); "
                    "ADR 7.5.2.2 tablosuna göre manuel kontrol gerekir."
                ),
                matched_label1=record1.un_no,
                matched_label2=record2.un_no,
            )

        if verdict.permitted is False:
            return SegregationCheckOutcome(
                status=STATUS_FORBIDDEN,
                adr_reference="7.5.2.2",
                description=verdict.note,
                matched_label1=record1.un_no,
                matched_label2=record2.un_no,
            )

        # permitted (koşullu olsun ya da olmasın) -> hâlâ patlayıcı, hâlâ
        # dikkat gerektirir; net kütle/araç onayı (7.5.5.2) bu motorun
        # kapsamında olmadığından "EXPLOSIVE_SPECIAL" olarak işaretlenir,
        # ama artık somut ve olumlu bir bilgiyle.
        note = verdict.note
        if not verdict.conditional:
            note += " (Not: taşıma ünitesi başına net patlayıcı kütle sınırı [ADR 7.5.5.2] bu modülde hesaplanmaz.)"
        return SegregationCheckOutcome(
            status=STATUS_EXPLOSIVE_SPECIAL,
            adr_reference="7.5.2.2",
            description=note,
            matched_label1=record1.un_no,
            matched_label2=record2.un_no,
        )

    # ------------------------------------------------------------------
    # Sınıf 1 içermeyen, sıradan etiket çiftleri
    # ------------------------------------------------------------------
    def _check_ordinary_label_pair(self, label1: str, label2: str) -> SegregationCheckOutcome:
        verdict: SegregationVerdict = self.rule_engine.check(label1, label2)
        return SegregationCheckOutcome(
            status=verdict.status,
            adr_reference=verdict.adr_reference,
            description=verdict.description,
            matched_label1=label1,
            matched_label2=label2,
        )
