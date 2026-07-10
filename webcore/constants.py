"""Uygulama sabitleri (monolitten satırı satırına)."""

# =============================================================================

APP_NAME = "ADR Transport Pro 2026"
APP_VERSION = "4.1.0"
APP_ORGANIZATION = "ADRSoft"

ADR_VERSION = "2025"
MAX_1136_POINTS = 1000

TUNNEL_HIERARCHY = {
    "A": 1,
    "B": 2,
    "C": 3,
    "D": 4,
    "E": 5,
}

TC_POINTS = {"0": 0, "1": 50, "2": 3, "3": 1, "4": 0}

CLASS_COLORS = {
    "1":   ("#FF0000", "#FFFFFF"),
    "2.1": ("#FF0000", "#FFFFFF"),
    "2.2": ("#00AA00", "#FFFFFF"),
    "2.3": ("#FFFFFF", "#000000"),
    "3":   ("#FF0000", "#FFFFFF"),
    "4.1": ("#FF0000", "#FFFFFF"),
    "4.2": ("#FF0000", "#FFFFFF"),
    "4.3": ("#0000FF", "#FFFFFF"),
    "5.1": ("#FFCC00", "#000000"),
    "5.2": ("#FFCC00", "#000000"),
    "6.1": ("#FFFFFF", "#000000"),
    "6.2": ("#FFFFFF", "#000000"),
    "7":   ("#FF00FF", "#FFFFFF"),
    "8":   ("#000000", "#FFFFFF"),
    "9":   ("#CCCCCC", "#000000"),
    "LQ":  ("#00FF00", "#000000"),
    "EQ":  ("#00FFFF", "#000000"),
}

INCOMPATIBILITY_MATRIX = {
    "Asitler":              ["Bazlar", "Siyanurler", "Yanici Maddeler", "Yukseltgenler"],
    "Bazlar":               ["Asitler", "Siyanurler", "Yanici Maddeler"],
    "Yukseltgenler":        ["Yanici Maddeler", "Asitler", "Organik Peroksitler"],
    "Yanici Maddeler":      ["Yukseltgenler", "Asitler", "Bazlar", "Organik Peroksitler"],
    "Organik Peroksitler":  ["Yanici Maddeler", "Yukseltgenler", "Asitler"],
    "Siyanurler":           ["Asitler", "Bazlar"],
    "2.3 Sinifi Zehirli Gazlar": ["Asitler", "Bazlar", "Yanici Maddeler"],
    "4.3 Sinifi Su ile Tepki Veren": ["Asitler", "Su ile Tepki Veren"],
    "Su ile Tepki Veren":   ["4.3 Sinifi Su ile Tepki Veren", "Asitler"],
}
# ── Güvenlik Sabitleri ────────────────────────────────────────────────────────
# BU DEĞERLERİ SADECE SEN BİLİRSİN — ASLA PAYLAŞMA
_LICENSE_SALT   = b"ADR_PRO_2026_GIZLI_SALT_DEGISTIR"   # 32+ karakter olsun
_HMAC_SECRET    = b"ADR_HMAC_IMZA_GIZLI_ANAHTARI_2026"
MAX_FAILED_LOGINS = 5          # Bu kadar hatalı girişten sonra hesap kilitlenir
SESSION_TIMEOUT_MIN = 480      # 8 saat sonra oturum kapanır
# =============================================================================
# ENUMLAR
# =============================================================================
