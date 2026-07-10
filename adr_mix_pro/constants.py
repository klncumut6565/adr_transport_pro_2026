"""Sabitler (constants).

Bu modülde yalnızca uygulama genelinde değişmeyen, sabit değerler tutulur.
Çalışma zamanı ayarları (dosya yolları, sütun eşleme tabloları vb.) için
``config.py`` modülüne bakınız.
"""

from . import __app_name__, __version__

APP_NAME = __app_name__
APP_VERSION = __version__
AUTHOR = "ADR Mix Checker Pro"

# Kontrol sonucu durum kodları
STATUS_OK = "OK"
STATUS_FORBIDDEN = "NO"
STATUS_UNKNOWN = "UNKNOWN"          # Kuralı tanımlı değil -> manuel kontrol gerekir
STATUS_EXPLOSIVE_SPECIAL = "EXPLOSIVE_SPECIAL"   # Sınıf 1 - 7.5.2.2 kapsamı
STATUS_FOOD_CAUTION = "FOOD_CAUTION"             # CV28 - 7.5.4 gıda ayrımı

STATUS_LABELS = {
    STATUS_OK: "Uygun",
    STATUS_FORBIDDEN: "Karışık yükleme yasak",
    STATUS_UNKNOWN: "Kural tanımlı değil (manuel kontrol gerekir)",
    STATUS_EXPLOSIVE_SPECIAL: "Sınıf 1 - uyumluluk grubu kontrolü gerekir (7.5.2.2)",
    STATUS_FOOD_CAUTION: "Gıda/yem ile ayrım gerekir (7.5.4 - CV28)",
}

# Dosya uzantıları
EXT_EXCEL = (".xlsx", ".xls")
EXT_CSV = (".csv",)
EXT_PROJECT = ".adrproj"

# ADR referansları (uygulama içinde gösterim amaçlı)
ADR_REF_MIXED_LOADING = "ADR 7.5.2.1"
ADR_REF_EXPLOSIVES = "ADR 7.5.2.2"
ADR_REF_FOODSTUFFS = "ADR 7.5.4 (CV28)"
ADR_REF_TUNNEL = "ADR 8.6 / Sütun (15)"

REPORT_TITLE = "ADR KARIŞIK YÜKLEME UYGUNLUK RAPORU"

MAX_UN_ITEMS = 1000  # Tek seferde karşılaştırılabilecek azami kalem sayısı (performans/güvenlik sınırı)
