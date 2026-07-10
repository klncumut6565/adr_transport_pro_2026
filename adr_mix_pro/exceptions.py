"""
Uygulamaya özel hata (exception) sınıfları.

Tüm özel hatalar ADRError sınıfından türetilir; bu sayede UI tarafında
tek bir except bloğu ile "uygulamaya ait, beklenen" hatalar; çok geniş bir
except Exception ile de "beklenmeyen" hatalar ayrı ayrı yakalanabilir.
"""


class ADRError(Exception):
    """Tüm uygulama hatalarının temel sınıfı."""


class DatabaseError(ADRError):
    """Ürün veritabanı (Excel/CSV) yüklenirken veya okunurken oluşan hatalar."""


class ColumnNotFoundError(DatabaseError):
    """Beklenen bir kolon (UN No, Etiket, Sınıf vb.) veri dosyasında bulunamadı."""


class RecordNotFoundError(DatabaseError):
    """Verilen UN numarası veritabanında bulunamadı."""


class RuleFileError(ADRError):
    """Segregasyon (karışık yükleme) kural dosyası yüklenirken oluşan hatalar."""


class InvalidUNNumberError(ADRError):
    """Girilen UN numarası biçimsel olarak geçersiz (4 haneli sayı değil)."""


class ProjectFileError(ADRError):
    """.adrproj proje dosyası okunurken/yazılırken oluşan hatalar."""


class ExportError(ADRError):
    """Excel veya PDF dışa aktarımı sırasında oluşan hatalar."""
