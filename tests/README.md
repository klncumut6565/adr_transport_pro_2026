# Test Paketi — Karışık Yükleme Entegrasyonu

Çalıştırma (proje kökünden):

    pip install pytest
    python -m pytest tests/ -v

## Dosyalar
- `test_regression.py` — Geliştirmede gerçekten yakalanan 5 hatayı sabitleyen
  testler (UN öneki, sessiz sıfır dolgusu, Sınıf 7 etiketleri, adaptör
  çökmesi, CV28 açıklaması) + mevzuat çekirdeği (Sınıf 1, 1.4S istisnası).
- `test_invariants.py` — Motorun her koşulda koruması gereken değişmezler:
  simetri, kural dosyası bütünlüğü, risk skoru sınırları, 100 kalem /
  4950 ikili ölçek testi, Türkçe/Unicode gidiş-dönüş.

## Kritik kural
`resources/data/segregation_rules.csv` dosyasını kendi doğrulanmış
sürümünüzle DEĞİŞTİRDİĞİNİZDE bu testleri mutlaka çalıştırın:
`TestRuleFileIntegrity` sınıfı; kural boşluklarını, çelişkili satırları ve
"Sınıf 1 asla sınıf-dışıyla OK olamaz" mevzuat değişmezini otomatik denetler.
Yeni bir hata bulunduğunda buraya test ekleyin — hiçbir testi silmeyin.
