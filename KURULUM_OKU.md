# ADR Transport Pro 2026 — Masaüstü Kurulumu

## 1. Python bağımlılıklarını kur
```
pip install -r requirements-desktop.txt
```
(PyQt6 bu listede eksikti, eklendi — daha önce ayrıca elle kurulmuş
olabilir; kurulu değilse uygulama hiç açılmaz.)

## 2. Çalıştır
```
python adr_transport_pro_2026.py
```
İlk açılışta `ADR_A_TABLOSU.xlsx` (bu pakette dahil) otomatik olarak
içe aktarılır.

## Bu pakette neler var
- `adr_transport_pro_2026.py` — ana uygulama (13.358 satır)
- `adr_mix_pro/` — Karışık Yükleme motoru (segregasyon kural motoru,
  Sınıf 1 patlayıcı dipnotları, CV28 gıda ayrımı, tünel kısıtları)
- `resources/` — segregasyon kuralları (CSV) + PDF fontları
- `ADR_A_TABLOSU.xlsx` — resmi ADR Tablo A verisi (2939+ kayıt)
- `admin_sifre_sifirla.py`, `adr_csv_importer.py` — yardımcı araçlar

## Son değişiklik (bu paket)
generate_adr_report() içindeki eski, basitleştirilmiş (gerçek ADR
referansı olmayan) uyumsuzluk kontrolü kaldırıldı; hem canlı panel hem
yazdırılan Taşıma Evrakı belgesi artık GERÇEK Karışık Yükleme motorunu
(AnaDbChemicalAdapter + MixChecker) kullanıyor — gerçek ADR referansları
(ör. "ADR 7.5.2.1") ile.
