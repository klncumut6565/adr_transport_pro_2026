"""Yardım diyaloğu."""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout

_HELP_HTML = """
<h2>ADR Mix Checker Pro - Kullanım Kılavuzu</h2>

<h3>1. Veri Dosyasını Yükleyin</h3>
<p>Dosya &gt; Veritabanı Yükle menüsünden, ürünlerinizin UN numarası, sınıf,
etiket ve diğer bilgilerini içeren bir Excel (.xlsx) veya CSV dosyası
seçin. Sütun başlıkları Türkçe veya İngilizce olabilir; uygulama yaygın
varyasyonları otomatik tanır.</p>

<h3>2. Kontrol Edilecek Ürünleri Ekleyin</h3>
<p>"Karışık Yükleme Kontrolü" sekmesinde, UN numarasını doğrudan yazıp
Ekle'ye basabilir veya "Veritabanında Ara" ile arama yapıp birden fazla
ürün seçebilirsiniz.</p>

<h3>3. Kontrolü Çalıştırın</h3>
<p>"Kontrol Et" butonuna bastığınızda, eklediğiniz tüm ürünlerin
ikili (her çift) kombinasyonu ADR 7.5.2.1 segregasyon tablosuna göre
değerlendirilir. Sonuç tablosunda bir satıra tıkladığınızda (çift tıklama
gerekmez), sağdaki ayrıntı panelinde o ikilinin açıklaması ve tavsiyeleri
anında güncellenir; tablo gezilirken panel sürekli canlı olarak değişir.
Sonuç durumları:</p>
<ul>
  <li><b>Uygun</b> — birlikte taşınabilir.</li>
  <li><b>Karışık yükleme yasak</b> — aynı araçta taşınamaz.</li>
  <li><b>Kural tanımlı değil</b> — tabloda bu etiket çifti için bir kural
      yok; manuel olarak ADR metnini kontrol etmeniz gerekir.</li>
  <li><b>Sınıf 1 - uyumluluk grubu kontrolü gerekir</b> — patlayıcı madde
      tespit edildi, bu modülün kapsamı dışında.</li>
  <li><b>Gıda/yem ile ayrım gerekir</b> — birlikte taşınabilir ancak
      aralarında fiziksel ayrım/mesafe gereklidir (CV28).</li>
</ul>

<h3>4. Raporlayın</h3>
<p>Sonuçları Excel veya PDF olarak dışa aktarabilir, ya da projeyi
(.adrproj) kaydedip daha sonra tekrar açabilirsiniz.</p>

<h3>Önemli Not</h3>
<p>Bu araç, karar destek amaçlıdır ve nihai hukuki/operasyonel sorumluluğu
ortadan kaldırmaz. Segregasyon tablosu
(<code>resources/data/segregation_rules.csv</code>) düzenlenebilir bir
dosyadır; eksik veya hatalı bulduğunuz kombinasyonları güncel ADR metnini
doğrulayarak ekleyebilirsiniz.</p>
"""


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yardım")
        self.setMinimumSize(640, 560)

        layout = QVBoxLayout(self)

        browser = QTextBrowser()
        browser.setHtml(_HELP_HTML)
        layout.addWidget(browser)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
