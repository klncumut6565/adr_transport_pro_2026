"""Genel yardımcı (utility) fonksiyonlar."""

from __future__ import annotations

import re


def normalize_label(label: object) -> str:
    """Tek bir tehlike etiketini karşılaştırmaya uygun biçime getirir.

    Örnekler: " 6.1 " -> "6.1", "6,1" -> "6.1", "1.4S" -> "1.4S"
    """

    if label is None:
        return ""

    text = str(label).strip()
    if text == "" or text.lower() == "nan":
        return ""

    # Avrupa biçimli ondalık ayraç (virgül) -> nokta. Ancak "1,4S" gibi
    # alt bölüm + uyumluluk grubu gösterimlerinde virgül kullanılmadığından
    # bu dönüşüm güvenlidir.
    text = text.replace(",", ".")
    text = text.replace(" ", "")
    return text.upper() if any(c.isalpha() for c in text) else text


def split_labels(label_text: object) -> list[str]:
    """Bir hücredeki birden fazla etiketi (örn. "3\\n+6.1" veya "1+8") ayırır.

    ÖNEMLİ: Virgül burada bir AYRAÇ olarak kullanılmaz; gerçek ADR A
    Tablosu dışa aktarımlarında virgül SADECE Türkçe ondalık noktası
    anlamındadır (örn. "1,4" = Bölüm 1.4, "6,1" = Sınıf 6.1). Birden
    fazla GERÇEK etiket her zaman "\\n+" (satır sonu + artı) ile
    ayrılır (örn. "1\\n+6.1\\n+8" = etiket 1, 6.1 VE 8). Virgülü de bir
    ayraç sayarsak "1,4" gibi tek bir bölüm numarası yanlışlıkla "1" ve
    "4" diye iki ayrı (ve anlamsız) etikete bölünür - bu, gerçek bir
    ADR A Tablosu ile test edilirken tespit edilmiş bir hataydı.
    """

    if label_text is None:
        return []

    text = str(label_text)
    if text.strip() == "" or text.strip().lower() == "nan":
        return []

    text = text.replace("\n", "+").replace("/", "+")
    parts = re.split(r"\+", text)

    result: list[str] = []
    for part in parts:
        normalized = normalize_label(part)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def unique_preserve_order(items: list) -> list:
    seen: set = set()
    result = []
    for item in items:
        key = str(item).strip()
        if key and key not in seen:
            seen.add(key)
            result.append(key)
    return result


def sorted_pair_key(a: str, b: str) -> tuple[str, str]:
    """İki etiketi, kural tablosunda tutarlı arama yapabilmek için sıralar."""

    return tuple(sorted((a, b)))  # type: ignore[return-value]
