"""Girdi doğrulama yardımcıları."""

from __future__ import annotations

import re

from .constants import EXT_CSV, EXT_EXCEL

_UN_PATTERN = re.compile(r"^\d{4}$")


def is_valid_un(value: object) -> bool:
    """UN numarasının 4 haneli bir sayı olup olmadığını kontrol eder.

    ADR'de UN numaraları her zaman 4 hanelidir (örn. "1090"). Baştaki/sondaki
    boşluklar tolere edilir; harf içeren veya 4 haneden farklı uzunluktaki
    değerler geçersiz sayılır.
    """

    text = str(value).strip()
    return bool(_UN_PATTERN.fullmatch(text))


def normalize_un(value: object) -> str:
    """UN numarasını karşılaştırmaya uygun, normalize edilmiş biçime getirir."""

    text = str(value).strip()
    # "UN1830", "un 1830" gibi onekli girisleri kabul et.
    if text[:2].upper() == "UN":
        text = text[2:].strip()
    # Excel bazen "1090" yerine "1090.0" gibi float olarak okuyabilir.
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(4) if text.isdigit() else text


def is_supported_data_file(filename: str) -> bool:
    lower = filename.lower()
    return lower.endswith(EXT_EXCEL) or lower.endswith(EXT_CSV)


def has_minimum_items(items: list, minimum: int = 2) -> bool:
    return len(items) >= minimum
