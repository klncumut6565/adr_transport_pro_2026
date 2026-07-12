"""Kullanıcıya gösterilecek Türkçe hata metinleri.

Masaüstü monolitindeki (adr_transport_pro_2026.py) _turkce_hata_metni
fonksiyonundan verbatim taşındı (Faz 4). Web tarafında da aynı kural
geçerli: kullanıcı arayüzüne (st.error / st.warning) HİÇBİR ham Python
istisna metni sızmamalı — her yerde bu fonksiyon üzerinden gösterilmeli.
"""


def turkce_hata_metni(exc: Exception) -> str:
    """Kullanıcıya gösterilecek hata metnini üretir.

    Python/kütüphane istisnalarının ham metni (str(exc)) genellikle
    İngilizcedir (örn. "list index out of range", "[Errno 2] No such
    file or directory"). Kullanıcıya HER ZAMAN Türkçe bir açıklama
    gösterilmesi için yaygın istisna türleri burada Türkçeye çevrilir;
    tanınmayan durumlarda teknik ayrıntı yerine genel bir Türkçe mesaj
    ve istisna sınıfı adı gösterilir (ham İngilizce metin asla
    kullanıcı arayüzüne sızmaz — ayrıntı yalnızca log dosyasına yazılır).
    """
    if isinstance(exc, FileNotFoundError):
        return f"Dosya bulunamadı: {getattr(exc, 'filename', '') or ''}".strip()
    if isinstance(exc, PermissionError):
        return "Dosyaya erişim izni yok (başka bir programda açık olabilir)."
    if isinstance(exc, IsADirectoryError):
        return "Seçilen konum bir dosya değil, klasör."
    if isinstance(exc, (OSError, IOError)):
        return "Dosya okuma/yazma sırasında bir sistem hatası oluştu."
    if isinstance(exc, ValueError):
        return "Girilen değerlerden biri geçersiz veya beklenen biçimde değil."
    if isinstance(exc, KeyError):
        return "Beklenen bir alan bulunamadı (veri eksik olabilir)."
    if isinstance(exc, IndexError):
        return "Veri listesinde beklenen bir öğe bulunamadı."
    if isinstance(exc, ImportError):
        return "Gerekli bir kütüphane kurulu değil (kurulum sayfasına bakın)."
    try:
        import sqlite3 as _sqlite3
        if isinstance(exc, _sqlite3.Error):
            return "Veritabanı işlemi sırasında bir hata oluştu."
    except ImportError:
        pass
    return f"Beklenmeyen bir hata oluştu ({type(exc).__name__}). Ayrıntı günlük kaydına yazıldı."
