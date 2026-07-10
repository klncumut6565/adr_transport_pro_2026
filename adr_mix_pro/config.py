"""Çalışma zamanı ayarları (config).

Bu modül; varsayılan dosya yollarını, pencere boyutlarını ve en önemlisi,
kullanıcıların farklı isimlerde sütun başlıkları kullanabileceği Excel/CSV
veri dosyaları için "esnek sütun eşleme" tablosunu içerir.

Tasarım notu: Önceki dağınık sürümde bu eşleme ``config.py`` içinde sabit
olarak duruyordu; burada da aynı yaklaşım korunmuştur çünkü gerçek hayatta
kullanılan "ADR A TABLOSU.xlsx" dosyaları kurumdan kuruma farklı sütun adları
kullanabilir (Türkçe/İngilizce, kısaltmalı/açık vb.).
"""

from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------
# Temel yollar
# --------------------------------------------------------------------------

# adr_mix_pro/ paketinin içinde bulunduğumuz için iki üst dizine çıkıp
# proje kökünü buluyoruz: <proje_kökü>/adr_mix_pro/config.py
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
RESOURCES_DIR = PROJECT_ROOT / "resources"

DEFAULT_RULE_FILE = RESOURCES_DIR / "data" / "segregation_rules.csv"
DEFAULT_SAMPLE_DATABASE = RESOURCES_DIR / "data" / "sample_products.csv"
DEFAULT_DARK_STYLE = RESOURCES_DIR / "styles" / "dark.qss"

# Türkçe karakterlerin (ç, ğ, ı, ö, ş, ü) PDF raporlarında doğru
# görüntülenmesi için paketlenen yazı tipleri (bkz. reports/pdf_export.py).
FONT_REGULAR_PATH = RESOURCES_DIR / "fonts" / "DejaVuSans.ttf"
FONT_BOLD_PATH = RESOURCES_DIR / "fonts" / "DejaVuSans-Bold.ttf"

# Kullanıcıya özel ayarların / loglarin tutulacağı dizin (işletim sistemine
# göre ev dizini altında gizli bir klasör).
USER_DATA_DIR = Path.home() / ".adr_mix_pro"
LOG_FILE = USER_DATA_DIR / "app.log"
SETTINGS_FILE = USER_DATA_DIR / "settings.json"


def ensure_user_data_dir() -> Path:
    """Kullanıcıya özel ayar/log dizininin var olduğundan emin olur."""

    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return USER_DATA_DIR


# --------------------------------------------------------------------------
# Pencere / arayüz varsayılanları
# --------------------------------------------------------------------------

WINDOW_TITLE = "ADR Mix Checker Pro"
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 800
SIDEBAR_WIDTH = 188

# --------------------------------------------------------------------------
# Esnek sütun eşleme
# --------------------------------------------------------------------------
# Her mantıksal alan için, veri dosyasında karşılaşılabilecek olası başlık
# varyasyonları (büyük/küçük harf ve boşluk farkları normalize edilerek
# karşılaştırılır; bkz. database.py -> _normalize_header).

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "UN_NO": (
        "UN No.",
        "UN No",
        "UN NO",
        "UN Numarası",
        "UN Number",
        "UN",
    ),
    "NAME": (
        "İsim ve açıklama",
        "Isim ve aciklama",
        "Madde Adı",
        "Madde Adi",
        "Name and Description",
        "Name",
    ),
    "CLASS": (
        "Sınıf",
        "Sinif",
        "Class",
        "Tehlike Sınıfı",
    ),
    "CLASSIFICATION_CODE": (
        "Sınıflandırma kodu",
        "Siniflandirma kodu",
        "Classification code",
    ),
    "LABELS": (
        "Etiketler",
        "Etiket",
        "Labels",
        "Tehlike Etiketleri",
    ),
    "PACKING_GROUP": (
        "Paketleme grubu",
        "Ambalajlama grubu",
        "Packing group",
        "PG",
    ),
    "SPECIAL_PROVISIONS": (
        "Özel hükümler",
        "Ozel hukumler",
        "Special provisions",
    ),
    "TRANSPORT_CATEGORY": (
        "Taşıma kategorisi",
        "Tasima kategorisi",
        "Transport category",
    ),
    "CV_CODES": (
        "Yükleme, boşaltma ve elleçleme",
        "Yükleme,boşaltma ve elleçleme",
        "Yukleme, bosaltma ve ellecleme",
        "Loading, unloading and handling",
    ),
    "TUNNEL_CODE": (
        "Tünel sınırlama kodu",
        "Tunel sinirlama kodu",
        "Tunnel restriction code",
    ),
    "DANGER_NUMBER": (
        "Tehlike numarası",
        "Kemler numarası",
        "Danger number",
        "Hazard identification number",
    ),
}

SUPPORTED_DATA_FILE_FILTER = "Veri Dosyaları (*.xlsx *.xls *.csv)"
SUPPORTED_PROJECT_FILE_FILTER = "ADR Proje Dosyası (*.adrproj)"
