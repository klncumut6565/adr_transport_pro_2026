# ADR Transport Pro 2026 — Karışık Yükleme Entegrasyonu

## Ne yapıldı
- `adr_mix_pro/` paketi (Karışık Yükleme programının motoru + sonuç bileşenleri) proje köküne kopyalandı.
- Yeni `mix_integration.py` eklendi:
  - **TransportChemicalDatabase**: Ürünler artık ana uygulamanın kendi `adr_database.json` dosyasından okunuyor (ikinci veritabanı yok).
  - **MixCheckPage**: Sol menüye eklenen "Karisik Yukleme" sayfası. UN listesi, kontrol, sonuç tablosu + detay paneli, Excel raporu.
- `main.py` yamalandı: sol gezinme menüsüne "Karisik Yukleme" (sayfa 9) eklendi.
- "Aktif Sevkiyattan Aktar" düğmesi, Taşıma Evrakı sayfasındaki kalemlerin UN numaralarını tek tıkla kontrole taşır. Asıl entegrasyon değeri budur: evrak hazırlarken yükleme uyumluluğu aynı akışta denetlenir.

## ÖNEMLİ — Kural dosyası
Orijinal `adr_mix_pro.rar` arşivinde `resources/` klasörü (segregation_rules.csv, fontlar) YOKTU.
- Buraya ADR 7.5.2.1 mantığına göre üretilmiş **varsayılan** bir `resources/data/segregation_rules.csv` konuldu (190 kural: Sınıf 1 yasakları, 1.4S istisnası, diğer sınıflar arası izin; gıda ayrımı CV28 ve Sınıf 1 uyumluluk grupları motor tarafından ayrıca hesaplanıyor).
- Kendi makinenizdeki orijinal `resources/` klasörünüz varsa onu bu projenin köküne kopyalayın; otomatik olarak o kullanılır.
- Mevzuat verisi olduğu için üretim kullanımından önce kural dosyasını mutlaka doğrulayın.

## PDF raporu
DejaVu fontları `resources/fonts/` altına paketlendi; Türkçe karakterler PDF'te doğru görüntülenir ve sayfadaki "PDF Raporu" düğmesi aktiftir.

## Testler
`tests/` klasöründe 210 testlik pytest paketi (genel gözden geçirme + tüm kontroller yeşil) (karışık yükleme + ana motor 1.1.3.6/tünel/muafiyet) vardır (`python -m pytest tests/ -v`). Regresyon + değişmezlik + depolama/rapor testlerini içerir; kural CSV'sini kendi sürümünüzle değiştirince mutlaka çalıştırın. Ayrıntı: `tests/README.md`.

## Çalıştırma
    pip install PyQt6 reportlab openpyxl rapidfuzz
    python main.py

## Ana motor (main.py) — düzeltilen kritik hatalar (v4.0.1)
1. **1.1.3.6 puanı** artık maddenin GERÇEK taşıma kategorisini kullanıyor (eski kod her şeyi x3 sayıyordu; kategori 1 maddelerde plaka zorunluluğu gizleniyordu). Bilinmeyen kategori güvenli tarafta x50 sayılır ve uyarılır.
2. **Kategori 0**: miktar ne olursa olsun muafiyet yok, plaka zorunlu.
3. **Muafiyet tipi**: 0-1000 puan aralığı artık doğru şekilde "ADR 1.1.3.6 Muafiyeti" gösterilir.
4. **Bileşik tünel kodları** ("D/E", "(C/D)") artık tanınır; en kısıtlayıcı harf esas alınır.
5. **Sürücü sertifika tarihi** bozuksa sessiz geçilmez, kritik hata üretilir.
6. **Kalıcılık**: shipment_items tablosuna tunnel_code / segregation_group / transport_category sütunları eklendi; mevcut adr.db ilk açılışta otomatik migrasyonla yükseltilir (veri kaybı olmaz).

## LQ / EQ profesyonelleştirme (v4.0.2)
Sorun: Excel'de LQ "1 L", EQ "E2" biçimindeyken iç kayıt miktardan bağımsız evet/hayır tutuyordu.
Çözüm — evet/hayır artık VERİ değil, limitlerden TÜRETİLEN bilgi:
- `chemicals` tablosuna `limited_quantity` (7a metni) ve `excepted_quantity` (E-kodu) sütunları eklendi (otomatik migrasyon).
- Excel/CSV içe aktarıcı ham "1 L" / "E2" değerlerini artık saklıyor (0/1'e indirgeme kaldırıldı).
- `import_chemicals_from_adr_json()` ile adr_database.json'daki limitler mevcut kayıtlara işlenebilir (üç veri kaynağı birleşti).
- Motor: `parse_lq_limit` ("1 L", "5 kg", "500 ml", "0,5 L"...), `eq_limits` (ADR 3.5.1.2: E0-E5 iç/dış g-ml), maddeye özgü `check_lq/eq_eligibility` (sınıf tablosu kaldırıldı), hacim-kütle birim uyuşmazlığı uyarısı.
- Kalem ekleme limitleri kaleme kopyalar; düzenleme diyaloğu 7a/7b değerini kutucuk yanında gösterir, E0/7a=0 maddelerde işaretlemeyi kilitler.
- ADR raporu, LQ/EQ işaretli kalemde iç-ambalaj-başı miktar limiti aşarsa "muafiyet GEÇERSİZ" kritik hatası üretir.

## Doğrulama katmanı (v4.0.3)
- Gönderici/alıcı hiç seçilmemişken evrak "geçerli" sayılıyordu (None kontrolü tersti) — düzeltildi.
- SRC5 / araç muayene / ADR uygunluk tarihlerinde sessiz except:pass kaldırıldı; bozuk tarih açık hata, boş muayene tarihi uyarı üretir.
- validate_quantity artık "nan"/"inf" girdilerini reddediyor.
- Plaka doğrulama: boşluksuz yazım kabul, il kodu 01-81 denetimi.
- E-posta doğrulama: ardışık nokta ve bozuk alan adları reddediliyor.

## Esnek tarih ayrıştırma (v4.0.4)
Tüm belge bitiş tarihi kontrolleri (sürücü ADR sertifikası, SRC5, araç muayene, ADR uygunluk) artık 2027-12-31, 31.12.2027, 31/12/2027 ve 31-12-2027 biçimlerini anlar; GG.AA.YYYY Türk yorumu esastır. Hiçbir biçime uymayan tarih sessizce geçilmez, açık hata üretir.

## Onay aşaması (v4.0.5)
Tespit: "Doğrula" düğmesi yalnızca mesaj kutusu gösteriyordu; DocumentStatus.VALIDATED hiç kullanılmıyor, is_validated/validation_errors hiç yazılmıyor, kaydet statüyü hep Taslak'a eziyordu.
Düzeltme: Doğrulama artık evrakı kaydedip sonucu kalıcılaştırıyor — geçerse status=Onaylandi + is_validated=1, geçmezse Taslak + hata metni validation_errors alanına. Onaylı evrak yeniden kaydedilirse onay otomatik düşer (içerik değişmiş olabilir). Durum etiketi renk kodlu: Onaylandı yeşil, Taslak sarı, Doğrulama hatalı kırmızı, İptal kırmızı, Yazdırıldı mavi.

## Antetli PDF + Karekod (v4.0.6)
- Firma kartına logo alanı eklendi (firma ekleme formunda "Logo: Seç..." ile PNG/JPG seçilir; companies tablosuna logo_path sütunu, otomatik migrasyon).
- PDF çıktısında gönderici firmanın logosu her sayfanın ortasında %8 opaklıkta antetli kağıt filigranı olarak çizilir; logo dosyası silinmişse PDF antetsiz ama sorunsuz üretilir.
- Onaylanmamış evrak PDF'ine 45 derece çapraz kırmızı "TASLAK" filigranı basılır; ONAYLANDI statüsündeki evrak temiz çıkar.
- Karekod (eski adr_transport_pro_2026.py'den yeni uygulamaya taşındı): evrak no + tarih + UN listesi içeren doğrulama karekodu PDF sonuna eklenir. Gereksinim: pip install qrcode Pillow (requirements.txt güncellendi; kütüphane yoksa PDF karekodsuz üretilir, çökmez).

## Excel çıktısı ve yazdırma (v4.0.7)
- Excel evrakı artık PDF ile aynı bilgi setini içerir: ADR kontrol özeti (1.1.3.6 puanı, turuncu plaka, yazılı talimat, tünel kısıtı, muafiyet), sürücü/araç, evrak durumu, kalem satırlarında tünel kodu ve LQ/EQ işaretleri, kritik uyarılar bloğu.
- Onaylanmamış evrakın Excel'inde kırmızı "TASLAK - Onaylanmamış evrak" uyarı satırı bulunur.
- Yazdırma artık ekrandaki zengin evrak önizlemesini birebir basar (eski düz-metin painter kaldırıldı) — ekranda görülen ile kağıda çıkan artık aynıdır.

## Gerçek Excel içe aktarım (v4.0.8)
Yüklenen dosyalar: ADR_A_TABLOSU.xlsx (2939 UN, resmi Tablo A) + ASUTEK firma envanteri (493 kimyasal).

Eklenen metotlar:
- import_table_a_excel(): Çok satırlı başlık yapısını (4 satır başlık, veri 5.satırdan) doğru okur; sütun 7a LQ metni ve 7b EQ kodu, taşıma kategorisi+tünel kodu, özel hükümler aktarılır.
- import_company_inventory_excel(): Başlık satırını "UN NUMARASI" hücresi arayarak dinamik bulur (üst bilgi/birleştirilmiş hücre sorununu çözer); çok sayfalı çalışma kitabı desteklenir. Envanterde EQ kodu yoksa aynı UN Tablo A'da varsa oradan tamamlar (üç veri kaynağı öncelik kuralı).
- _upsert_chemical(): insert/update ayrımı doğru; ikinci import 0 yeni kayıt döner (idempotans).
- count_chemicals(): Sayaç metodu eklendi.

Test sonuçları (gerçek veri): 2347 Tablo A kaydı aktarıldı. UN1203 LQ=1L EQ=E2 kat=2 tünel=D/E doğrulandı. LQ motor 0.9L→OK / 1.5L→YASAK doğru çalışıyor. Tekrar import 0 yeni kayıt → idempotans sağlandı.

## Gerçek veri — varyasyon mimarisi (v4.0.9)

Sorun: Aynı UN numarası birden fazla ADR Tablo A satırına karşılık geliyordu (UN1950 AEROSOL = 12 farklı sınıflandırma kodu). Eski sistem UN numarasını birincil anahtar sayıp 11 varyasyonu siliyordu. Kullanıcı UN1950 seçtiğinde 12 seçenek görmeli ve uygun olanı seçmeli.

Mimari değişiklik:
- chemicals tablosu: PRIMARY KEY hâlâ id, UNIQUE kısıtı UN+classification_code+packing_group (bileşik — üç alana birden).
- Tablo A importu: 2873 benzersiz varyasyon aktarıldı (2939 satırın 53 tekrarı UN+Kod+PG ayırt edilerek elenmiş, 13 satır boş/başlık).
- search_chemicals: 4 haneli sayısal sorgu tam UN eşlemesi yapar, TÜM varyasyonları döndürür. Rapidfuzz yalnızca metin aramalarında çalışır (UN aramasında yabancı sonuç eklemez).
- company_products ayrı tablo: Aynı ADR karşılığını paylaşan ticari ürünler (farklı ticari adlar, aynı UN+PG) ayrı kayıtlarda tutulur; sevkiyata her biri ayrıca eklenebilir.
- Tüm importlar idempotent: ikinci çağrı 0 yeni kayıt döndürür.

## Genel gözden geçirme bulguları (v4.1.0)
1. Kalan 6 adet bare except/pass tespit edildi; bunlar: yedek dosya sırasında dosya hatası (güvenli görmezden gel), UI tarih etiketleri (ham metin göster), evrak yükleme tarihi (bugüne dön), örnek veri yükleme (sessiz atla). Bunlar loglanmadan yutuluyordu; bazılarına logging.warning eklendi.
2. TASLAK uyarı şeridi HTML önizlemesinde yoktu — sadece PDF'te vardı. Artık önizlemede de onaylanmamış evraklarda sarı/turuncu şerit görünüyor, ONAYLANDI'da kayboluyor (11 görsel denetimle doğrulandı).
3. get_document_info() evrak durumunu döndürmüyordu — status alanı eklendi.
4. Rapidfuzz UN tam eşlemede (4 haneli sayısal sorgu) yabancı sonuç ekliyordu — yalnızca metin aramalarında çalışıyor.
Sonuç: Motor, veritabanı, doğrulama, onay akışı, PDF, Excel, önizleme ve gerçek Excel içe aktarım — tümü çapraz doğrulandı.

## ANA PROGRAMA TAŞIMA (v4.2 — adr_transport_pro_2026.py)

ÖNEMLİ: Kullanıcının tespitiyle asıl ana programın adr_transport_pro_2026.py (11.703 satır; login, lisans, güvenlik, tüm yönetim sayfaları dahil) olduğu netleşti. main.py eksik bir kopyaydı. Tüm kritik düzeltmeler ana programa 17 yama halinde taşındı ve 20 motor testiyle doğrulandı:

1. 1136: Kategori 0 → plaka zorunlu; bilinmeyen kategori → hesaptan atlamak yerine x50 güvenli taraf + açık uyarı.
2. Tünel: Bileşik kodlar (D/E, (C/D)) çözümleniyor.
3. LQ/EQ: Sınıf tabloları kaldırıldı; madde bazlı 7a metni + E-kodu (E0–E5, ADR 3.5.1.2), birim ailesi uyarısı. parse_lq_limit/eq_limits/is_lq_allowed/is_eq_allowed eklendi.
4. Esnek tarih (parse_date_flexible): sürücü ADR sertifikası, SRC5, araç muayene, T9 — 4 kontrol de TR formatlarını anlıyor; bozuk tarih artık uyarı değil HATA.
5. Firmasız evrak: None kontrolü düzeltildi.
6. Bileşik anahtar: chemicals UNIQUE(UN+SınıfKodu+PG); eski UNIQUE(un_number) veritabanları ilk açılışta otomatik tablo-yeniden-inşa migrasyonuyla yükseltilir (veri korunur — testli).
7. company_products tablosu + search_company_products; companies.logo_path.
8. Gerçek Excel içe aktarıcılar (Tablo A 2873 varyasyon + ASUTEK envanteri) main.py'den birebir taşındı; idempotans doğrulandı.
9. Onay yaşam döngüsü: set_shipment_validation + _validate_shipment artık kaydedip statüyü kalıcılaştırıyor.
10. Arama: 4 haneli sorgu UN tam eşleşme; rapidfuzz yalnızca metin aramada.

HENÜZ TAŞINMAYANLAR (bir sonraki tur): PDF antet logosu + TASLAK filigranı + QR (_pdf_page_background/_make_qr_image), önizleme TASLAK şeridi, Excel ADR özeti, firma formunda logo seçici, onaylı evrak yeniden kaydedilince onay düşürme. Ana programın kendi PDF/önizleme kodu farklı yapıda olduğundan dikkatli uyarlama gerekir.

## ANA PROGRAM — Antetli Kağıt Filigranı + TASLAK Damgası (v4.3)

Kullanıcının orijinal isteği: "taşıma evrakı hangi firma oluşturuyorsa, o
firmanın logosu antetli kağıt gibi arka planda görünsün."

### Önemli mimari düzeltme (bu turda netleşti)
Ana programın PDF/yazdırma sistemi main.py'dekinden TAMAMEN FARKLI:
main.py ReportLab canvas kullanıyordu, ana program ise HTML + QTextDocument
+ QPrinter kullanıyor (_build_print_html() -> doc.print(printer)).
main.py'deki reportlab tabanlı antet/filigran kodu buraya DOĞRUDAN
taşınamazdı; sıfırdan, bu mimariye uygun şekilde inşa edildi.

Ayrıca ana programda logo tasarımı da main.py'den farklı ve DAHA DOĞRU:
tek bir firma-geneli logo (Settings sayfasında doc_company_logo_b64 ayarı,
zaten mevcuttu) kullanılıyor çünkü bu yazılım tek bir firmanın (yazılımı
kullanan firmanın) evrak oluşturduğu bir araç; sender/receiver her
sevkiyatta değişen taraflar. main.py'deki per-company Company.logo_path
yaklaşımı bu kullanım şekline uymuyordu; ana programın mevcut modeli
korundu, sadece eksik olan "arka plan filigranı" davranışı eklendi.

### Yakalanan kritik render hatası
İlk yamada filigran HİÇBİR YERDE görünmüyordu. Kanıt: watermark açık/kapalı
iki PDF render'ının piksel farkı yalnızca sayfanın üst-sol köşesindeki
KÜÇÜK, ÖNCEDEN VAR OLAN logo simgesiyle sınırlıydı (y:29-144 / 1755
piksellik sayfada) — yani yeni filigran kodu etkisizdi.

Kök neden: Belgenin global <style> bloğundaki
"table { border-collapse: collapse; width: 100%; }" kuralı, Qt'nin zengin
metin motorunda background-image özelliğini TAMAMEN bastırıyor (izole
testle doğrulandı: aynı yapı border-collapse:collapse ile background-image
göstermiyor, border-collapse:separate ile gösteriyor). Bu, Qt'nin HTML alt
kümesinin bilinmeyen/belgesiz bir sınırlaması.

Düzeltme: Filigran sarmalayıcı tabloya inline style="border-collapse:separate"
eklendi (CSS özgüllüğü: inline > eleman-seçici, global kuralı ezer).
Sonrasında fark neredeyse tüm sayfaya yayıldı (y:29-1220, x:28-1210 /
1755x1240 sayfada).

### Uygulanan özellikler
1. _build_letterhead_watermark_b64(): Pillow ile tek bir PNG üretir:
   - Firma logosu (varsa), sayfa ortasında %8 opaklıkta soluk filigran.
   - Onaylanmamış evrakta (TASLAK/DOĞRULAMA HATALI) 30 derece eğik kırmızı
     "TASLAK" yazısı aynı görüntüye bindirilir.
   - Ne logo ne TASLAK gerekmiyorsa (onaylı + logosuz) boş döner, gereksiz
     işlem yapılmaz.
2. _build_print_html(): is_approved durumunu lbl_status metninden hesaplar,
   filigranı üretir, tüm gövde içeriğini border-collapse:separate özellikli
   bir sarmalayıcı <table width="100%"> içine alır.
3. Karekod: Ana programda ZATEN vardı (generate_qr_html, firma kartviziti/
   vCard formatında, Ayarlar sayfasından açılıp kapatılabiliyor) — taşımaya
   gerek yoktu, main.py'deki QR daha az gelişmiş bir tekrarıydı.

### Testler
tests/test_letterhead_ana_program.py — 10 test (1 opsiyonel bağımlılık
nedeniyle atlanabilir): HTML'de filigran varlığı, border-collapse override
doğrulaması, logosuz+onaylı durumda yan etki olmaması, taslak/onaylı
filigranların farklılığı, PIL üretici fonksiyonun bozuk girdilerde
çökmemesi, VE en kritik olanı — gerçek PDF render'ının piksel-diff
karşılaştırmasıyla filigranın sayfanın genelinde (sadece köşede değil)
görünür olduğunun doğrulanması.

Toplam test sayısı: 214 (2 opsiyonel atlama).

## main.py İPTALİ ve TAM TEMİZLİK (v4.5)

Kullanıcının net direktifi: "main.py iptal edilecek, tüm düzeltmeler adr_transport_pro_2026.py üzerinde yapılacak." Bu turda tam olarak uygulandı:

### 1. Karışık Yükleme ana programa taşındı
- `AnaDbChemicalAdapter`: main.py'nin JSON tabanlı adaptörü yerine, ana programın SQL veritabanını (composite anahtar UN+SınıfKodu+PG) kullanır.
- `VariantPickerDialog`: Aynı UN'nin birden fazla Tablo A varyasyonu varsa (örn. UN1950 = 12 kod), kullanıcı hangi varyasyonun taşınacağını AÇIKÇA seçer — kullanıcının kendi belirttiği tasarım gereksinimi.
- `MixLoadCheckPage`: Sol menüde "Karışık Yükleme" (sayfa 11). "Aktif Sevkiyattan Aktar" akışı, kalemlerin kendi classification_code/packing_group bilgisini kullandığından belirsizlik içermez.
- 18 test (`test_mixload_ana_program.py`), 12-varyasyonlu dialog davranışı dahil.

### 2. Excel çıktısı zenginleştirildi
- ADR kontrol özeti, LQ/EQ bayrakları, tünel kodu, kritik uyarılar, TASLAK banner — main.py'de yapılan iyileştirmeler artık `export_excel()`'de de var.
- 6 test (`test_excel_export_ana_program.py`).

### 3. KRİTİK — Eksik LQ/EQ limit denetimi tamamlandı
Test-first yaklaşımla port sırasında gözden kaçan bir şey ortaya çıktı: `generate_adr_report()`'ta LQ/EQ işaretli kalemlerin gerçekten kendi limitini aşıp aşmadığını kontrol eden mantık main.py'de vardı ama ana programa HİÇ taşınmamıştı. Şimdi eklendi: iç ambalaj başına miktar, maddenin 7a/7b limitini aşarsa "muafiyet GEÇERSİZ" kritik hatası üretiliyor.

### 4. Tüm testler doğru dosyaya taşındı
main.py'yi hedefleyen 7 test dosyası (test_approval, test_excel_export, test_lq_eq, test_pdf_letterhead, test_real_excel, test_transport_engine, test_validation) silindi; içerikleri `adr_transport_pro_2026.py`'yi hedefleyecek şekilde `_ana_program` sonekiyle yeniden yazıldı. Ayrıca `mix_integration.py`'ye bağımlı olan conftest.py, test_regression.py, test_invariants.py bağımsız hale getirildi (kendi basit ProductDatabase fixture'ı).

### 5. main.py ve mix_integration.py projeden SİLİNDİ
Artık iki dosya da yok. Tek uygulama dosyası: `adr_transport_pro_2026.py`.

**Toplam test sayısı: 224 (2 opsiyonel atlama), hepsi ana programı hedefliyor.**

## Proje Temizliği — Ölü Kod ve Alakasız Dosyalar (v4.6)

Kullanıcının "alakasız dosya var mı" sorusu üzerine tüm proje dosyaları
`adr_transport_pro_2026.py` tarafından gerçekten import edilip edilmediği
açısından tek tek tarandı. Aşağıdakiler HİÇBİR yerden çağrılmadığı
doğrulandıktan sonra kullanıcı onayıyla silindi:

- `ui/` klasörü (5 dosya, 364K) — hiç import edilmiyordu
- `core/` klasörü (4 dosya, 68K) — hiç import edilmiyordu (InputValidator
  sınıfı dahil — bu nedenle tests/test_validation_ana_program.py'deki
  ona bağımlı 3 test sınıfı da kaldırıldı; gerçek uygulamada kullanılan
  ADREngine.validate_shipment / parse_date_flexible testleri korundu)
- `export/` klasörü (2 dosya, 144K) — hiç import edilmiyordu
- `converter.py` (24K) — adr_csv_importer.py'nin eski/üzeri çizilmiş
  kopyası, hiçbir yerden çağrılmıyordu
- `adr.db` (28K) — eksik şema (yalnızca chemicals tablosu, 0 kayıt);
  uygulama varsayılan olarak ~/.adr_transport_pro/adr_database.db kullanır,
  bu dosyaya hiç bakmaz
- `adr_database.json`, `company_database.json` — main.py/mix_integration.py
  silindiğinden beri hiçbir kod tarafından okunmuyordu
- Boş `backups/` ve `resources/styles/` klasörleri
- `ADR A TABLOSU.pdf` (6.3MB) — kullanıcı onayıyla silindi (zaten .xlsx
  sürümü içe aktarımda kullanılıyor)

**Sonuç: proje boyutu ~10MB → 4.9MB (%51 azalma). 193 test, hepsi geçiyor,
uygulama temizlik sonrası sorunsuz açılıyor.**

## Güvenlik Planı İnceleme Raporu (v4.7)

Kullanıcının paylaştığı gerçek örnek belgeye (ASUTEK Endüstriyel Kimyasalları
— "Güvenlik Planı İnceleme Raporu") dayanarak yeni, kalıcı bir özellik
eklendi: firma kimyasal envanterinin tamamını ADR Tablo 1.10.3.1.2
kapsamında statik olarak (miktardan bağımsız, yalnızca sınıf/ambalajlama
grubu/sınıflandırma koduna göre) tarayıp örnekle aynı çok sayfalı PDF
formatında rapor üreten bir sekme.

### Mimari karar
Ana programda ZATEN çok detaylı, iyi test edilmiş bir `SecurityPlanEngine`
vardı (ADR 1.10.4 muafiyeti, Tablo 1.10.3.1.2, Sınıf 7 radyonüklid eşikleri
dahil) — ama bu motor belirli bir SEVKİYATIN kalemlerini (miktar + taşıma
modu dahil) değerlendiriyordu. Kullanıcının istediği ise firma envanterinin
TAMAMININ statik taranması. Sıfırdan yazmak yerine mevcut motora iki yeni
metod eklendi: `screen_inventory_chemical()` (tek kimyasal, miktardan
bağımsız tarama) ve `screen_inventory()` (toplu tarama + özet sayaçlar).

### Yeni sekme: "📋 Envanter İnceleme Raporu" (SafetyPlansPage içinde)
- "Envanteri Tara" düğmesi: `company_products` tablosundaki benzersiz
  (UN, sınıflandırma kodu, PG) kombinasyonlarını `chemicals` tablosundan
  tam kayıt olarak çekip tarar (firma envanteri henüz yoksa tüm
  `chemicals` tablosu taranır).
- Sonuç tablosu: her madde için UN, isim, sınıf/PG, durum (Kapsam İçi /
  Koşullu / Muaf), ve örnek rapordaki gibi Türkçe açıklama metni.
- Firma adı / Hazırlayan / Onaylayan / Geçerlilik süresi giriş alanları.
- "PDF Rapor Oluştur": örnekle aynı formatta (kapak + Tablo 1.10.3.1.2
  referansı + madde bazlı değerlendirme + sonuç/imza sayfası) çok sayfalı
  PDF üretir; mevcut firma logosu varsa antet filigranı olarak eklenir.

### Bu turda gerçek veriyle yakalanan 3 hata (test-first)
1. **`_get_table_key()` boş `class_code`'da çöküyordu** (`"".split()[0]`
   IndexError) — gerçek envanterde bazı kayıtlarda sınıf bilgisi eksik.
   Hem bu metodda hem `check()` metodunda düzeltildi.
2. **Paketleme grubu bazı kayıtlarda Arap rakamıyla** ("1","2","3")
   geliyordu; PG karşılaştırmaları (`pg == "I"`) yalnızca Roma rakamını
   tanıyordu. Güvenlik kararını etkileyen bir alan olduğu için Arap→Roma
   normalizasyonu eklendi.
3. **KRİTİK:** `screen_inventory_chemical()` ham `sqlite3.Row` nesnelerinde
   `getattr()` ile çağrıldığında SESSİZCE boş veri üretiyordu (sqlite3.Row
   attribute erişimini desteklemez, yalnızca anahtar erişimini destekler).
   Bu, gerçek ASUTEK verisiyle ilk testte TÜM 36 kimyasalın (yanlışlıkla)
   "muaf" çıkmasına yol açmıştı — veri gerçekten boş olduğu için değil,
   okuma hatası yüzünden. Artık hem dataclass hem sqlite3.Row/dict
   nesnelerini güvenle okuyan savunmacı bir alan-okuma yardımcısı var.
   Düzeltme sonrası aynı 36 kimyasal için sonuç DEĞİŞMEDİ (gerçekten 0
   kapsam içi, 36 muaf) — ama bu artık doğrulanmış, güvenilir bir sonuç.

### Doğrulama
Örnek rapordaki 4 kimyasal (UN1993, UN2924, UN3341, UN2014) motor
tarafından da MUAF olarak doğrulandı. Kapsam-içi senaryolar (Sınıf 1
patlayıcı, Sınıf 6.2 Kategori A bulaşıcı madde, zehirli gaz, Sınıf 6.1 PG I
zehirli katı) doğru şekilde KAPSAM İÇİ çıkıyor. Gerçek ASUTEK envanteri
(36 kimyasal) uçtan uca tarandı, PDF üretildi ve render edildi (6 fiziksel
sayfa: kapak + tablo referansı + 3 sayfa değerlendirme tablosu + sonuç).

**26 yeni test eklendi. Toplam: 221 test (2 opsiyonel atlama).**

## Türkçe Hata Mesajları (v4.8)

Kullanıcının tespiti: uygulama hata diyaloglarında bazen ham İngilizce
istisna metinleri (örn. "list index out of range", "[Errno 2] No such
file or directory") kullanıcıya doğrudan gösteriliyordu. Kullanıcı
arayüzündeki HER mesaj Türkçe olmalı.

### Çözüm
`_turkce_hata_metni(exc)` adında merkezi bir çeviri yardımcısı eklendi.
Yaygın istisna türlerini (FileNotFoundError, PermissionError,
IsADirectoryError, OSError/IOError, ValueError, KeyError, IndexError,
ImportError, sqlite3.Error) tanıyıp anlamlı Türkçe açıklamaya çevirir.
Tanınmayan istisnalarda ham İngilizce metin YERİNE genel bir Türkçe
mesaj + istisna sınıfı adı gösterilir; teknik ayrıntı yalnızca
`logging` ile günlük dosyasına yazılır, kullanıcı arayüzüne asla sızmaz.

Kod tabanındaki `QMessageBox.critical(self, "Hata", str(exc))` /
`str(e)` kalıplarının TAMAMI (5 konum) bu yardımcıyı kullanacak şekilde
güncellendi. Regresyon testi (`test_all_critical_dialogs_use_helper_not_raw_str`)
bu kalıbın kod tabanına bir daha girmediğini doğrular.

**11 yeni test eklendi. Toplam: 232 test (2 opsiyonel atlama).**
