"""Tavsiye (öneri) motoru.

ÖNEMLİ - ŞEFFAFLIK NOTU: Önceki dağınık sürümde bu modül "AI Suggestion
Engine" (yapay zekâ öneri motoru) olarak adlandırılmıştı; ancak içerik
tamamen durum/sınıf bazlı sabit if/elif kurallarından oluşuyordu, herhangi
bir makine öğrenmesi veya büyük dil modeli kullanılmıyordu. "Ticari" bir
üründe yapay zekâ kullanılmadığı halde "AI" etiketi kullanmak yanıltıcı
olacağından bu modül burada doğru biçimde "kural tabanlı tavsiye motoru"
olarak adlandırılmıştır. İleride gerçek bir LLM entegrasyonu eklenmek
istenirse bu modül o işlevin yerini tutacak şekilde genişletilebilir.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..constants import (
    STATUS_EXPLOSIVE_SPECIAL,
    STATUS_FOOD_CAUTION,
    STATUS_FORBIDDEN,
    STATUS_OK,
    STATUS_UNKNOWN,
)


@dataclass(slots=True)
class Advisory:
    summary: str
    actions: list[str] = field(default_factory=list)


def build_advisory(status: str) -> Advisory:
    if status == STATUS_FORBIDDEN:
        return Advisory(
            summary="Bu iki kalem aynı araç/konteynerde birlikte taşınamaz.",
            actions=[
                "Ayrı araç veya ayrı konteyner kullanın.",
                "Aynı aracı kullanmak zorunluysa, sevkiyatları zaman içinde ayırın.",
                "ADR Tablo 7.5.2.1'de izin verilen alternatif bir kombinasyon olup olmadığını kontrol edin.",
            ],
        )

    if status == STATUS_EXPLOSIVE_SPECIAL:
        return Advisory(
            summary="Sınıf 1 (patlayıcı) madde tespit edildi; bu modülün kapsamı dışında ek kontrol gerekir.",
            actions=[
                "İlgili maddelerin uyumluluk gruplarını (Compatibility Group) belirleyin.",
                "ADR 7.5.2.2 uyumluluk grubu tablosuna göre karşılaştırın.",
                "Gerekirse bir Tehlikeli Madde Güvenlik Danışmanına (TMGD/DGSA) başvurun.",
            ],
        )

    if status == STATUS_UNKNOWN:
        return Advisory(
            summary="Bu etiket çifti için tabloda tanımlı bir kural bulunamadı.",
            actions=[
                "Güncel ADR Tablo 7.5.2.1'i manuel olarak kontrol edin.",
                "Doğrulandıktan sonra sonucu 'segregation_rules.csv' dosyasına ekleyerek bir sonraki sefer otomatik tanınmasını sağlayın.",
            ],
        )

    if status == STATUS_FOOD_CAUTION:
        return Advisory(
            summary="Gıda/yem ayrımı için tedbir gerekiyor (CV28).",
            actions=[
                "Paketler arasına en az paket yüksekliğinde bir bölme koyun.",
                "Veya en az 0,8 metre fiziksel mesafe bırakın.",
                "Veya ek ambalaj/örtü ile maddeyi izole edin.",
            ],
        )

    return Advisory(
        summary="Standart ADR kontrolüne göre birlikte taşıma uygundur.",
        actions=["Ek bir tedbire gerek yoktur; standart yükleme kurallarına uyun."],
    )
