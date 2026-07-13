# ADR Transport Pro — Web'e Geçiş (Tek Sistem Kararı)

Karar: Streamlit tek platform. Qt masaüstü DONDURULDU (bozulmaz, yeni geliştirme yapılmaz).
Veritabanı: PostgreSQL (Supabase), çoklu firma = her tabloda company_id satır izolasyonu.
Uyku sorunu: GitHub Actions keep-alive (Faz 5'te .github/workflows/keepalive.yml).

## Faz durumu
- [x] Faz 0a — Çekirdek ayrıştırma: `webcore/` paketi oluşturuldu.
      constants / models / DatabaseManager / ADREngine+SecurityPlanEngine,
      monolitten SATIRI SATIRINA (motor değişikliği YOK), sıfır Qt bağımlılığı.
      Duman testleri: DB CRUD+arama, 1.1.3.6 (TC1 x25=1250 plaka zorunlu,
      TC3 x100=100 muaf), envanter güvenlik taraması (UN1203 muaf) — geçti.
- [x] Faz 0b — PostgreSQL katmanı: `webcore/pg.py` → PgDatabaseManager,
      DatabaseManager'ın alt sınıfı; 56 iş metodunun tamamı miras (değişiklik yok).
      Lehçe çevirisi TranslatingCursor'da (en alt katman): ?→%s, LIKE→ILIKE,
      INSERT OR REPLACE/IGNORE→ON CONFLICT, strftime→to_char,
      julianday→::date (NULLIF('') korumalı), date('now',...)→INTERVAL.
      Şema geçici SQLite'tan okunur (migrasyonlar dahil NİHAİ hâl) ve çevrilir;
      her iş tablosuna tenant_id BIGINT DEFAULT 1 + indeks (adı company_id değil:
      şemadaki 'companies' tablosuyla karışmaması için). FK'lar bilinçli taşınmadı
      (SQLite'ta zorlanmıyordu; Faz 6'da 0→NULL temizliğiyle açılacak).
      2 metot override (get_top_senders/chemicals: Pg GROUP BY katılığı).
      Doğrulama: 10 adımlı uçtan uca yaşam döngüsü + tests_webcore artık
      iki arka uçta parametrik koşuyor (11 test yeşil).
      KALAN: Supabase bağlantısı gelince ADR_PG_TEST_DSN ile aynı testler
      Supabase'e karşı koşulacak; requirements'a psycopg[binary] eklenecek.
- [x] Faz 1a — Kiracı izolasyonu: PostgreSQL Row Level Security.
      Her iş tablosunda tenant_izolasyon politikası (USING + WITH CHECK,
      FORCE RLS — tablo sahibi de muaf değil); aktif kiracı bağlantı
      oturumunda app.tenant_id ile taşınır (set_config), tenant_id
      DEFAULT'u da buradan beslenir. 56 iş metodu değişmeden kiracıya
      kilitlendi. Doğrulama: okuma ayrımı, id yoklama, çapraz yazma
      (InsufficientPrivilege), set_tenant geçişi.
- [x] Faz 1b — Kimlik doğrulama: `webcore/auth.py` → tenants + web_users
      tabloları (BİLİNÇLİ olarak RLS dışı: giriş anında kiracı bilinmez),
      PBKDF2-HMAC-SHA256 600k tur + kullanıcı başına tuz, roller
      (admin/user/viewer), 5 hatalı girişte 15 dk kilit, parola sıfırlama.
      Akış: login() → tenant_id → PgDatabaseManager.set_tenant() → RLS.
      KALAN (Faz 2 ile birlikte): Streamlit giriş sayfası bu modülü kullanacak.
- [~] Faz 2 — Streamlit iskeleti KURULDU: `app.py` (giriş sayfası →
      AuthManager.login → set_tenant → st.navigation) + `sayfalar/`
      (gosterge_paneli, kimyasal_veritabani, sevkiyatlar — liste görünümü).
      Bağlantı dizesi .streamlit/secrets.toml → [db].dsn (repoya girmez;
      Cloud'da Secrets ekranından verilecek). Arayüz duman testleri
      AppTest ile başsız koşuyor (giriş görünür / yanlış parola hatası /
      doğru giriş → panel + metrikler). Suite: 18 test yeşil.
      Faz 2b TAMAMLANDI (Umut): sevkiyat editörü (Doğrula: 1.1.3.6 +
      tünel + uyumsuzluk; Kaydet: motor sonuçları sevkiyata kalıcı yazılır),
      firmalar/sürücüler/araçlar CRUD sayfaları, karışık yükleme ekranı
      (7.5.2), güvenlik planı ekranı (1.10.3). webcore/session.py ile
      cache kaynakları app.py'den ayrıldı (çift-render düzeltmesi).
      NOT — bilinçli motor sapması: check_compatibility tekilleştirme/sıra
      düzeltmesi (webcore/engines.py başlık notu + kilit testi).
      Faz 2c BÜYÜK ORANDA TAMAM: `sayfalar/ayarlar.py` (yalnız admin) —
      doc_company_* firma bilgileri (evrak antetiyle birebir anahtarlar),
      antet logosu yükle/kaldır (PDF filigranını besler), ADR Tablo A
      xlsx içe aktarma (Pg'de 2873 kayıt / 5 sn, SQLite ile parite testli)
      + onaylı tablo boşaltma. db.py yapıştırma düzeltmesi: içe aktarıcının
      ADREngine referansları geç-import'a bağlandı (döngü riski notuyla).
      Faz 2d TAMAM: `sayfalar/raporlar.py` — dönem seçimli özet metrikler,
      sınıf kırılımı (tablo+grafik), son 6 ay dağılımı, en çok gönderen/
      kimyasal listeleri; çok sayfalı Excel ve PDF dışa aktarma (WeasyPrint).
      Ayarlar'a firma envanteri içe aktarma eklendi (ASUTEK formatı,
      'UN NUMARASI' başlığı otomatik bulunur, EQ Tablo A'dan tamamlanır;
      gerçek dosyayla Pg'de testli). SAYFA TAŞIMA FAZI (2a-2d) KAPANDI:
      12 masaüstü sayfasının web karşılıkları tamam.
- [~] Faz 3a — PDF motoru: `webcore/pdf.py` → html_to_pdf_bytes (WeasyPrint,
      A4) + build_letterhead_watermark_b64 (monolitten satırı satırına, saf
      Pillow) + filigran HOOK'u: engines'e ShipmentEditorPage vekili enjekte
      edilir, motor koduna dokunulmadan Faz 0a'daki "bilinçli boş" kapatıldı.
      Güvenlik planı sayfasına PDF indirme eklendi (sonuç session'da tutulur).
      Cloud: requirements.txt += weasyprint, packages.txt (libpango...).
      Faz 3b TAMAMLANDI: `webcore/transport_doc.py` →
      build_transport_document_html; monolit _build_print_html'den (579
      satır) satırı satırına, 16 self.* erişimi parametreye eşlendi
      (envanter belgeli). İki taşıma düzeltmesi: hasattr(self) savunması
      parametreye çevrildi, eksik timedelta importu eklendi. Sevkiyat
      editörüne "Taşıma Evrakı PDF" butonu (sonuç session'da, indirme
      rerun'a dayanıklı). Testler: puan şeridi, SRC5 süre-uyarı dalı,
      Türkçe karakter, %PDF imzası. KALAN (Faz 3c → Faz 2c ile):
      antet logosu yükleme (Ayarlar sayfası), doc_company_* ayar ekranı.
- [x] Faz 4 — TEST TAŞIMA TAMAM (Umut 5 parça + son 4 dosya birlikte):
      webcore suite 198 test. Taşınanlar: adr_mix_pro motoru, Türkçe hata
      motoru (webcore/errors.py), doğrulama katmanı, mevzuat hesap motoru,
      LQ/EQ, onay yaşam döngüsü (test_approval), gerçek Tablo A
      (test_real_excel), güvenlik planı motor+rapor (test_security_plan_review;
      QTextDocument PDF testi WeasyPrint'e çevrildi), statik filigran
      (test_letterhead). Masaüstünde kalanlar (Qt sayfa/pencere akışları):
      test_mixload, test_excel_export, letterhead Presence/VisualEffect,
      TestRealAsutekInventory'nin 2 Qt testi (test_ui_scan_button_populates_table,
      test_ui_pdf_export_end_to_end) — tests/ altında çalışmaya devam ederler.
      Taşımanın yakaladığı gerçek regresyon: 66-satır düzeltmesi UNIQUE
      kısıtla birlikte yeniden-içe-aktarma tekilliğini de kaldırmıştı
      (2. yükleme 5878 kayıt yapardı); import_table_a_excel'e TAM SATIR
      İMZASI tabanlı idempotenslik eklendi (varyantlar korunur, kopya
      eklenmez) — test_idempotent yeniden yeşil.
      DÜZELTME (Umut'un sorusu üzerine): TestRealAsutekInventory'nin ilk
      taşımada TAMAMI "Qt'ye bağlı" sayılıp atlanmıştı, ama 4 testinden
      yalnız 2'si gerçekten Qt'ye bağlıydı. Diğer 2'si
      (test_full_pipeline_no_crash, test_pg1_item_un2054_exempt_per_class8_rule
      — SecurityPlanEngine.screen_inventory'yi gerçek ASUTEK envanteriyle
      uçtan uca çalıştırıyor, Qt yok) TestRealAsutekInventoryScreening
      olarak webcore'a taşındı; bu ikisi masaüstünde de silinip yalnız
      web tarafında kaldı (kod tekrarı olmasın diye). Faz 4 artık gerçekten
      %100 tamam.
- [x] Faz 4.5 — "ADR Kontrol Merkezi" canlı panel + canlı evrak önizleme
      TAMAMLANDI: sayfalar/sevkiyat_editor.py iki sütuna ayrıldı (sol:
      form + ürün listesi + Kaydet; sağ: ADR Kontrol Merkezi). Eski
      "🔍 Doğrula" butonu kaldırıldı — 1.1.3.6 puanı/plaka durumu, tünel
      kısıtlama kodu, sürücü ADR/SRC5 sertifika durumu (renkli: geçerli/
      30 gün içinde dolan/süresi dolmuş), doğrulama hata+uyarıları ve
      7.5.2 uyumsuzluk kontrolü artık HİÇBİR butona bağlı değil — Streamlit
      zaten her etkileşimde tüm scripti yeniden çalıştırdığı için bunlar
      üst seviyede tutularak otomatik "canlı" hale geldi. Canlı Evrak
      Önizleme: build_transport_document_html ile üretilen HTML,
      st.components.v1.html üzerinden KAYDETMEDEN ÖNCE bile (taslak
      haldeyken) sağ panelde gerçek zamanlı görünüyor; PDF üretimi
      (WeasyPrint) ayrı bir "PDF oluştur ve indir" butonunda kaldı (her
      tuş vuruşunda ağır render koşmasın diye — HTML önizleme ucuzdur,
      PDF dönüşümü değildir). Doğrulama: tüm motor çağrıları (puan/tünel/
      validate_shipment/check_compatibility/parse_date_flexible/
      build_transport_document_html) gerçek verilerle ve boş ürün
      listesiyle kuru-çalıştırıldı, çökme yok; tests_webcore/ 198 test
      yeşil kaldı (regresyon yok); pyflakes temiz.
      NOT: Başlığı masaüstündeki gibi "Taşıma Evrakı" yapmak ayrı bir
      karar olarak bekliyor (mevcut AppTest "Sevkiyat Editörü" başlığını
      doğruluyor, onay almadan değiştirilmedi).
- [ ] Faz 5 — Streamlit Cloud dağıtım + secrets + keep-alive workflow
- [x] Faz 6 — Veri migrasyonu + yedek: `araclar/migrate_desktop_to_pg.py`
      (ID'ler ve ilişkiler korunur, kolon kesişimiyle şema-toleranslı,
      tenant_id atanır, IDENTITY sayaçları setval ile sarılır, --temizle /
      ON CONFLICT id ile idempotent, yerleşik sayı+ilişki doğrulaması;
      prova: 2939 kimyasal + 5 sevkiyat + ilişkiler + sayaç kanıtı) ve
      `araclar/yedek_al.py` (tüm tablolar zaman damgalı CSV zip; ücretsiz
      planda otomatik yedek olmamasına karşı felaket-kurtarma kopyası,
      pg_dump alternatifi notuyla). İkisi de suite'te uçtan uca testli.
      KULLANIM: gerçek geçiş günü tek komut —
      python araclar/migrate_desktop_to_pg.py --sqlite adr_database.db
        --dsn "SUPABASE_POOLER_DSN" --tenant 1 --temizle

## webcore/ notları
- SecurityPlanEngine.generate_inventory_review_html içindeki antet filigranı
  ShipmentEditorPage'e try/except ile bağlıydı; webcore'da bilinçli olarak boş
  düşer, Faz 3'te WeasyPrint hook'u verilecek.
- 285-493 aralığındaki lisans yardımcıları (makine parmak izi, PBKDF2) webcore'a
  ALINMADI; web kimlik doğrulaması Faz 1'de ayrı kurulacak.
- DÜZELTME (Faz 4 sırasında, Umut'un tespiti): chemicals tablosundaki
  UNIQUE(un_number, classification_code, packing_group) kısıtı yanlıştı.
  Resmi ADR Tablo A'da bu üçlü AYNI olup yalnızca özel hüküm (6. sütun) ile
  ayrışan gerçekten farklı satırlar var (örn. UN1133 F1 PG II: 640C/640D
  varyantları — 48 böyle üçlü, 66 fazladan satır). import_table_a_excel bu
  kısıtı "birincil anahtar" sayıp böyle satırları birbirinin üzerine
  yazıyordu: 2939 geçerli satırdan yalnızca 2873'ü kalıyordu. Kısıt
  kaldırıldı, import artık her satırı kendi kaydı olarak ekliyor (2939→2939,
  UN1133 doğrulandı: 6 varyant, 640C ve 640D ayrı ayrı görünüyor). Sonuç:
  import artık idempotent DEĞİL (tekrar çalıştırma satırları çoğaltır) —
  Ayarlar sayfasındaki "temiz yükleme için önce boşalt" uyarısı zaten bunu
  varsayıyordu. Canlı Supabase için tek seferlik migrasyon:
  migration_chemicals_unique_kaldir.sql. Not: _upsert_chemical (firma
  envanteri birleştirmesi için) aynı üçlüyü hâlâ kullanıyor — bu, küçük
  firma envanterleri için makul bir sezgisel yöntem, ama resmi Tablo A için
  GEÇERSİZ olduğu artık docstring'de açıkça belirtiliyor.

## Denetim notu (Faz 4 sırasında, canlı ortam düzeltmesi)
- Umut'un 66-satır düzeltmesi (UNIQUE kısıtının Tablo A'nın özel-hükümle
  ayrışan satırlarını yutması) canlı Supabase'de kendiliğinden etkin OLMAZDI:
  CREATE TABLE IF NOT EXISTS mevcut tabloyu değiştirmez, kısıt üretimde
  kalıyordu. PgDatabaseManager.init_database'e kendi kendini iyileştiren
  migrasyon eklendi: her açılışta chemicals üzerindeki UNIQUE kısıtları
  pg_constraint'ten bulunup düşürülür. Kanıt: kısıt elle geri konup init
  koşuldu -> kısıt yok, içe aktarma 2939 tam, UN1133 6 varyant.


## Mimari düzeltme (Umut'un tespiti üzerine): Tablo A global, envanter kiracıya özel
Umut'un "Ürün ekle'de Tablo A verisi neden yok, ben bunun gömülü kalmasını
istemiştim" sorusu üç ayrı hatayı ortaya çıkardı:

1. **chemicals (ADR Tablo A) yanlışlıkla TENANT_TABLES'taydı.** Tablo A
   yönetmeliğin herkes için aynı olan resmi verisi, firma sırrı değil.
   Kiracıya kilitlenince her yeni kiracı Tablo A'yı BOŞ görüyordu.
   → chemicals TENANT_TABLES'tan çıkarıldı; RLS/politika/FORCE RLS
   canlıda kurulmuşsa kendi kendini iyileştirerek söker.
2. **Otomatik tohumlama eklendi:** chemicals boşsa, repoyla gelen
   ADR_A_TABLOSU.xlsx'ten PgDatabaseManager.init_database() içinde
   otomatik yüklenir (webcore/pg.py:_tohumla_tablo_a). Artık kimse elle
   yüklemek zorunda değil — tam da istenen "gömülü" davranış.
3. **Denetim sırasında ayrı bir gerçek hata bulundu:** company_products
   (FİRMAYA özel envanter, Ayarlar'dan yüklenen) hiçbir zaman
   TENANT_TABLES'ta OLMAMIŞTI — Faz 1'den beri izolasyonsuzdu, farklı
   kiracıların aynı ürün+UN+sınıf kombinasyonu birbirinin üzerine
   yazabilirdi (ON CONFLICT tenant_id'siz kısıt üzerinden). Eklendi;
   UNIQUE kısıtı da tenant_id dahil edecek şekilde göçürüldü
   (kendi kendini iyileştiren migrasyon, üçüncü örnek).
Üçü de canlı (önceden dağıtılmış) şema üzerinde test edildi: eski RLS'li
chemicals + tenant_id'siz company_products durumundan başlanıp yeni koda
geçildiğinde hatasız kendini onardı. Regresyon testleri:
TestTabloAKuresel (paylaşım + otomatik tohumlama), company_products
izolasyon testi (aynı ürün bilgisiyle çakışma senaryosu). Suite: 219 test.


## Görünürlük iyileştirmesi (Umut: "hala kullanılamıyor" sonrası)
Önceki turdaki mimari düzeltme (chemicals global + otomatik tohumlama)
doğruydu ama tohumlama hatası yalnızca Python logger'a yazılıyordu —
Streamlit arayüzünde görünmüyordu, yani Cloud'da bir şey ters giderse
kullanıcı sebepsiz bir boşlukla baş başa kalıyordu. Eklendi:
- PgDatabaseManager.seed_bilgisi: tohumlama denendi mi/başarılı mı/hata
  metni, dosya yolu — sayfalar bunu okuyabilir.
- Kimyasal Veritabanı ve Ürün Ekle (Taşıma Evrakı) sayfalarına: tablo
  gerçekten boşsa sebep mesajı + "🔄 Tablo A'yı şimdi yükle" butonu
  (embedded dosyadan, admin olmayan roller de görebilir/tetikleyebilir —
  bu salt-okunur referans veri, zarar riski yok).
- Kanıt: dosyayı geçici olarak kaldırıp seed_bilgisi'nin doğru hata
  mesajını ürettiği doğrulandı; UI testiyle kilitlendi. Suite: 220 test.

ÖNEMLİ — Cloud'da hâlâ boş görünüyorsa muhtemel sebep KOD DEĞİL,
YENİDEN BAŞLAMAMA: Streamlit Cloud, cache_resource ile oluşturulan
PgDatabaseManager'ı process ömrü boyunca bir kez kurar; git push sonrası
Cloud genelde otomatik yeniden başlar ama gecikebilir. Kontrol sırası:
1) Manage app → Reboot app (otomatik olmadıysa zorla tetikler)
2) Reboot sonrası Kimyasal Veritabanı sayfasını aç — artık boşsa
   sebep mesajı görünür olacak (dosya bulunamadı / DB hatası / vb.)
3) Hâlâ belirsizse "🔄 Tablo A'yı şimdi yükle" butonuna bas — sonucu
   ekranda görürsün.


## KRİTİK ALTYAPI BULGUSU: Transaction pooler + RLS/oturum durumu uyumsuzluğu
Umut'un canlıda aldığı `psycopg.errors.DuplicatePreparedStatement` hatası,
kökeni çok daha ciddi bir soruna işaret ediyordu.

**Sorun:** Supabase Connect ekranında Faz 0b'de seçtiğimiz "Transaction
pooler" (port 6543, PgBouncer/Supavisor transaction modu), HER SORGUYU
farklı bir arka-uç Postgres bağlantısına yönlendirebilir. Supabase'in
kendi dokümantasyonu açıkça belirtiyor: bu modda oturum durumu (SET,
set_config, hazırlanmış ifadeler, advisory lock'lar) İSTEMCİLER ARASINDA
KORUNMAZ ve "clients must not use any session-based features, since each
transaction ends up in a different connection."

Bizim mimarimiz TAM OLARAK bunu ihlal ediyordu:
1. `SELECT set_config('app.tenant_id', ..., false)` bağlantı açılışında
   BİR KEZ çalıştırılıyor (webcore/pg.py:_get_conn). Transaction pooler
   altında bu değer yalnızca O ANKİ arka-uca yazılır; sonraki sorgular
   BAŞKA bir arka-uca gidebilir ve orada app.tenant_id hiç set edilmemiş
   olabilir → RLS'in COALESCE(...,1) varsayılanı sessizce devreye girer.
   Şu an tek kiracı (id=1) olduğu için bu VERİ SIZINTISI OLARAK henüz
   GÖRÜNMEDİ (yanlış varsayılan bile "doğru" kiracıya denk geliyordu) —
   ama ikinci kiracı eklendiğinde ciddi bir izolasyon riskiydi.
2. psycopg'nin otomatik sunucu-taraflı PREPARE'i, transaction modunda
   aynı isimdeki hazırlanmış ifadenin başka bir arka-uçta zaten var
   olmasıyla çakışıyordu → DuplicatePreparedStatement (Umut'un gördüğü
   hata).

**Uygulanan düzeltme (kod tarafı, kalıcı):**
- `psycopg.connect(..., prepare_threshold=None)` — sunucu-taraflı otomatik
  PREPARE tamamen kapatıldı. Bu, hangi pooler modu kullanılırsa kullanılsın
  DuplicatePreparedStatement'i kalıcı olarak önler.

**YAPILMASI GEREKEN (Umut, Streamlit Cloud Secrets'ta, 5 dakika):**
Supabase → Connect → bağlantı dizesini **port 6543 (Transaction pooler)**
yerine **port 5432, Session pooler** ile değiştir (host aynı kalır:
`aws-x-region.pooler.supabase.com`, yalnız port 5432). Session modu her
istemciye (yani her Streamlit Cloud process'ine) YAŞAM BOYU SABİT bir
arka-uç bağlantısı ayırır — tam olarak bizim "bağlantıyı bir kez aç, tekrar
kullan" mimarimizin varsaydığı davranış. IPv4 uyumludur (Direct bağlantının
IPv6 sorunu burada yok), bu yüzden Streamlit Cloud için de sorunsuz çalışır.
Supabase'in kendi dokümantasyonu da kalıcı/uzun-ömürlü backend'ler için
tam olarak bunu öneriyor. Değişiklik yalnızca DSN'deki portu değiştirmek;
kod tarafında başka hiçbir şey değişmez.

Suite: 220 test (mevcut testler yerel Postgres'e karşı zaten session-benzeri
tek bağlantı kullanıyordu, bu sınıf hatayı yerelde yakalayamazdık —
yalnız gerçek Supabase pooler davranışında ortaya çıkar).


## Nihai düzeltme: SET LOCAL — pooler moduna bağımlılık tamamen kaldırıldı
Önceki turda Session pooler'a (port 5432) geçiş ÖNERİLMİŞTİ ama bu dışarıdan,
doğrulayamadığım bir ayara bağımlıydı ve Umut "hâlâ gözükmüyor" dedi. Kod
tarafında kalıcı, pooler-bağımsız çözüm uygulandı:

- Bağlantı açılışındaki BİR KEZLİK `set_config(..., false)` (oturum-ölçekli)
  TAMAMEN KALDIRILDI.
- Yerine: `_tenanted_cursor()` — her `execute/execute_one/execute_insert/
  execute_update` çağrısı artık kendi transaction'ını açıyor, İÇİNDE önce
  `SET LOCAL app.tenant_id = <int>` sonra gerçek sorgu çalışıyor. PgBouncer/
  Supavisor'ın transaction modu sözleşmesi gereği bir transaction'ın TAMAMI
  tek arka-uçta yürür — yani bu ikili HER ZAMAN aynı bağlantıda, pooler
  modundan (Transaction/Session) tamamen bağımsız olarak doğru çalışır.
  Artık Supabase Secrets'ta port 6543 mi 5432 mi olduğu ÖNEMSİZ.
- Ek bulgu (aynı denetimde): `db.py`'de get_expiring_documents ve
  get_class_breakdown doğrudan `conn.execute()` kullanıyordu — bu, yeni
  (ve eski) kiracı sarmalayıcısını TAMAMEN ATLIYORDU. Pg altında bu iki
  fonksiyon her zaman kiracı 1'e düşüyordu (tek kiracı olduğu için şu ana
  kadar görünmedi). self.execute()'a taşındı, artık kiracıya doğru izole.

Doğrulama: aynı PgDatabaseManager nesnesi üzerinde set_tenant ile ileri-geri
geçiş, get_expiring_documents kiracı izolasyonu, çapraz yazma engeli — hepsi
regresyon testleriyle kilitli. Suite: 222 test.

SONUÇ: Tablo A'nın "hâlâ gözükmemesi" muhtemelen bu kiracı-bağlamı
güvenilmezliğinin dolaylı bir belirtisiydi (chemicals artık global olduğu
için doğrudan value değil ama init_database() sırasındaki DuplicatePreparedStatement
çökmesi TÜM bağlantı kurulumunu, dolayısıyla otomatik tohumlamayı da
engelliyordu). Bu commit'ten sonra Cloud'da reboot + normal kullanım
yeterli olmalı; Session pooler'a geçiş artık gerekli değil ama zararı da yok.


## GERÇEK KÖK SEBEP BULUNDU: "== 0" eşiği, "1 kayıtlı bozuk" durumu yakalamıyordu
Umut'un ekran görüntüsü kesin kanıtı verdi: "0 kayıt görüntüleniyor
(toplam 1)". Tablo BOŞ değildi — muhtemelen önceki DuplicatePreparedStatement
çökmesi sırasında yarıda kesilen bir içe aktarmadan kalma TEK bir bozuk
kayıt vardı. Hem otomatik tohumlama (`_tohumla_tablo_a`) hem de UI'daki
kurtarma butonları hep "== 0 mı?" diye soruyordu; "1" bu testten "hayır,
dolu" diye geçiyor ve HER İKİ kurtarma mekanizması da sessizce devre dışı
kalıyordu. Reboot bu yüzden hiçbir şeyi değiştirmiyordu.

**Düzeltme:** `TABLO_A_EKSIK_ESIGI = 2000` eşiği eklendi (gerçek tam sayı
2939). Artık "> 0" / "== 0" yerine "< 2000" kontrolü var — hem
_tohumla_tablo_a hem sayfalar/kimyasal_veritabani.py hem
sayfalar/sevkiyat_editor.py'de. Kanıtlandı: chemicals'ı elle 1 satıra
düşürüp yeni bağlantı açıldığında otomatik tohumlama tetiklendi ve tablo
sessizce 2940 kayda tamamlandı (gerçek 2939 + test artığı 1 satır —
idempotent içe aktarma mevcut veriyi silmez, üzerine ekler).

Suite: 223 test. Bu düzeltme push edildikten sonra Cloud'da reboot
GERÇEKTEN etkili olacak — önceki reboot'lar hâlâ eski "== 0" kontrollü
kodu çalıştırıyordu.


## Düzeltme: Canlı Önizleme gerçek PDF çıktısına hiç benzemiyordu
Sebep: taşıma evrakı şablonundaki `@page {{ size: A4; margin: 8mm 10mm; }}`
kuralı yalnızca yazdırma/PDF motorlarında (WeasyPrint dahil) uygulanır —
TARAYICILAR bunu ekranda tamamen yok sayar. Aynı HTML, Canlı Önizleme'de
(components.html, normal ekran render'ı) sayfa genişliği/kenar boşluğu
kısıtı olmadan dağınık akıyordu; PDF'e çevrilince ise WeasyPrint @page'i
uygulayıp düzgün A4 üretiyordu — ikisi arasındaki fark buydu.

Düzeltme: `webcore/pdf.py` → `wrap_for_screen_preview()`. Yalnızca
ÖNİZLEME kopyasına (components.html'e giden), @page'in ekranda
yapamadığını taklit eden bir <style> enjekte eder (width:210mm, sayfa
kenar boşluğu, "kağıt" gölgesi). PDF üretimi (`html_to_pdf_bytes`) HÂLÂ
orijinal, sarmalanmamış HTML'i alıyor — hiç etkilenmedi. Kanıtlandı:
sarmalama yalnızca <head>'e ekleme yapıyor, <body> içeriği birebir aynı
kalıyor, orijinal @page kuralı korunuyor, PDF orijinal HTML'den sorunsuz
üretiliyor. Suite: 225 test.


## Düzeltme: Uygulama "Running get_db()." ekranında sonsuza kadar donuyordu
Sebep: her açılışta (her Cloud reboot'unda) TÜM şema göç kontrolleri (10+
ALTER TABLE/DROP CONSTRAINT taraması) yeniden koşuyordu. Bunlar normalde
zararsızdır (koşul sağlanmışsa ALTER hiç çalışmaz) AMA önceki bir çökmeden
(DuplicatePreparedStatement) kalma yarım kesilmiş bir işlem tabloyu kısa
süreli kilitli bırakmışsa, sıradan bir SELECT bile o kilidi bekleyip
UYGULAMAYI SONSUZA KADAR DONDURABİLİYORDU (hiçbir zaman timeout olmuyordu).

İki katmanlı düzeltme:
1. Bağlantıya `lock_timeout=6s` + `statement_timeout=25s` eklendi
   (webcore/pg.py:_get_conn). Bir kilit gerçekten oluşsa bile artık en
   fazla birkaç saniye beklenip GÖRÜNÜR bir hataya düşülüyor — bir daha
   sessizce sonsuza kadar donmuyor.
2. Şema sürüm işareti (`_SEMA_SURUM`, settings tablosunda saklanır):
   göçler bir kez tamamlanınca işaretlenir; sonraki her açılış bunu görüp
   ağır taramaların TAMAMINI atlıyor. Ölçüldü: ilk bağlantı ~5.7 sn
   (tam göç + 2939 kayıt tohumlama), sonraki bağlantılar ~0.04 sn
   (138 kat hızlanma). Bu hem donma riskini en aza indiriyor hem de
   her reboot'u çok daha hızlı hâle getiriyor.

Suite: 225 test (fonksiyonellik bozulmadı, arama/izolasyon/tohumlama
hepsi hızlı yolda da doğru çalışıyor).

ACİL MÜDAHALE (bu commit'ten BAĞIMSIZ, Umut'un o anki donmuş oturumunu
açmak için): Supabase SQL Editor'de aşağıdaki sorgu, 2 dakikadan uzun
süredir "idle in transaction" durumunda takılı kalmış (muhtemelen önceki
çökmeden kalma) oturumları sonlandırır:
    SELECT pg_terminate_backend(pid), query, state, now()-query_start AS sure
    FROM pg_stat_activity
    WHERE state = 'idle in transaction' AND now() - query_start > interval '2 minutes';


## Düzeltme: Ürün arama Enter gerektiriyordu ve sonuçlar tek satırda görünüyordu
Umut'un şikâyeti: "1993" gibi bir UN aradığında sonuçlar Enter'a basmadan
çıkmıyordu VE çıktığında sanki tek sonuç varmış gibi görünüyordu.

Kök sebep, iki ayrı Streamlit davranışıydı:
1. `st.text_input` varsayılan olarak yalnızca Enter'a basılınca / odak
   kaybedilince (blur) uygulamayı yeniden çalıştırır — her tuş vuruşunda
   DEĞİL. Streamlit'in bu widget için "canlı" bir modu yoktur.
2. `st.selectbox` her zaman KAPALI, tek satırlık bir açılır kutu olarak
   render olur — kaç eşleşme olursa olsun ekranda hep "1 satır" gibi
   görünür; tüm seçenekleri alt alta göstermek için tıklayıp açmak gerekir.

Düzeltme: `sayfalar/sevkiyat_editor.py`'deki arama, `st.dataframe`'in
YERLEŞİK araç çubuğu aramasına geçirildi — bu, TAMAMEN İSTEMCİ TARAFINDA
(tarayıcıda) çalışır, sunucuya hiç gitmeden HER TUŞ VURUŞUNDA anında
filtreler (masaüstü uygulamasındaki canlı arama hissine en yakın yerleşik
Streamlit özelliği). Tüm eşleşmeler aynı anda tablo satırları olarak
görünür; bir satıra tıklamak seçim yapar (`on_select="rerun"`,
`selection_mode="single-row"`, seçim `.selection.rows` üzerinden okunur).

Doğrulama: sayfa hatasız render oluyor, eski text_input/selectbox tamamen
kalktı, ürün listesi tablosu render oluyor. (Not: AppTest test aracı
dataframe satır tıklamasını simüle edemiyor — segfault veriyor, bu test
aracının kendi kısıtı; seçim mantığı Streamlit'in resmi/belgelenmiş
on_select API'sini birebir kullanıyor.) Suite: 225 test (+1 yeni).


## Düzeltme (2. tur): önceki dataframe çözümü de yanlıştı
Umut'un ilk düzeltmemi ("st.dataframe + yerleşik arama araç çubuğu")
reddetmesi haklıydı: bu, TÜM Tablo A'yı (2939 satır) varsayılan olarak
gösteriyordu — istenenin tam tersi. Asıl istek netti: yazana kadar hiçbir
şey görünmesin, "1993" yazınca yalnızca gerçekten eşleşen ~6 kayıt
listelensin, Enter gerekmesin.

Streamlit'in kendi widget'larıyla (text_input: Enter/blur gerektirir;
selectbox: kapalı tek satır; dataframe: ya hep-göster ya hiç-göster) bu
tam olarak karşılanamıyor — bunun için özel tasarlanmış bir bileşen var:
`streamlit-searchbox` (m-wrzr/streamlit-searchbox, PyPI). Her tuş
vuruşunda arka planda verilen Python fonksiyonunu (burada
search_chemicals) çağırıp sonuçları açılır bir liste olarak gösterir —
Enter yok, tüm tablo yok, yalnızca o anki eşleşmeler.

requirements.txt'e eklendi. `sayfalar/sevkiyat_editor.py`'deki Ürün Ekle
artık `st_searchbox(_kimyasal_ara, ...)` kullanıyor; `_kimyasal_ara`
2 karakter altında boş liste döner (gürültü olmasın), üstünde
`db().search_chemicals(terim, limit=20)` çağırıp (etiket, Chemical nesnesi)
ikilileri döner.

Doğrulama: gerçek "1993" senaryosu — 6 sonuç, hepsi UN1993 (tabloyu
filtresiz göstermiyor). Suite: 227 test.


## KRİTİK GÜVENLİK/KARARLILIK DÜZELTMESİ: paylaşılan global DB bağlantısı
Umut'un canlıda aldığı `psycopg.transaction.OutOfOrderTransactionNesting`
hatası, en ciddi mimari kusuru ortaya çıkardı.

**Sebep:** `webcore/session.py`'deki `get_db()`/`get_auth()` fonksiyonları
`@st.cache_resource` ile tanımlıydı — argümansız olduğu için TEK bir
global singleton PgDatabaseManager (ve tek bir psycopg Connection)
ÜRETİYORDU. Streamlit Cloud, farklı kullanıcı oturumlarının script'lerini
AYRI İŞ PARÇACIKLARINDA eşzamanlı çalıştırabildiği için, uygulamaya aynı
anda giren TÜM KULLANICILAR aynı tek bağlantıyı PAYLAŞIYORDU. SET LOCAL
transaction sarmalayıcısı (önceki tur) bu tehlikeyi GÖRÜNÜR bir hataya
çevirdi; öncesinde muhtemelen sessizce yanlış kiracıya sorgu gitmesi /
veri karışıklığı riski taşıyordu (kanıtlanmamış ama mimari olarak mümkündü).

**Kanıt (yerelde yeniden üretildi):** 6 iş parçacığı PAYLAŞILAN tek
bağlantı üzerinden eşzamanlı sorgu attığında 125/180 çağrı
OutOfOrderTransactionNesting ile patladı — Umut'un gördüğü hatanın
birebir aynısı.

**Düzeltme:** `get_db()`/`get_auth()` artık `st.session_state` kullanıyor
(`st.cache_resource` DEĞİL) — her Streamlit OTURUMUNA (her kullanıcı/
tarayıcı sekmesi) kendi özel bağlantısı. Aynı 6 iş parçacıklı testte
SIFIR hata. Bu aynı zamanda kiracı izolasyonunu GÜÇLENDİRDİ: artık yalnız
RLS'e değil, oturumlar arası tamamen ayrı Python nesnelerine de dayanıyor.

Doğrulama: negatif kontrol (paylaşılan bağlantı → hata üretir, kanıtlı) +
pozitif kontrol (ayrı bağlantılar → sıfır hata) + statik kontrol
(st.cache_resource bir daha sessizce geri gelmesin). Suite: 230 test.


## Düzeltme: firma seçiminde 1-2 sn donma + art arda hızlı tıklamada hata
İki ayrı sorun, ikisi de SET LOCAL değişikliğinin (önceki tur) yan etkisi.

**1) Performans:** `sayfalar/sevkiyat_editor.py`, firma/sürücü/araç
LİSTELERİNİ zaten tam çekiyordu (get_companies/get_drivers/get_vehicles)
AMA seçili olanı göstermek için ayrıca 5 kez tek-kayıt sorgusu
(get_company/get_driver/get_vehicle) atıyordu — tamamen gereksiz, liste
zaten bellekte. SET LOCAL her sorguyu kendi transaction'ına (BEGIN+SET
LOCAL+SORGU+COMMIT, 4 ağ gidiş-gelişi) sardığından bu 5 gereksiz sorgu
özellikle pahalılaşmıştı. Düzeltme: ID'ler artık bellekteki listeden
aranıyor (`next((f for f in firmalar if f.id==fid), None)`); yalnızca
sürücü/araç `active_only=True` filtresiyle listede yoksa (pasif yapılmış
eski kayıt) tek seferlik yedek sorguya düşülüyor. Ölçüldü: 38 kat hızlanma.

**2) Kararlılık — kendi kendini onaran yeniden bağlanma:** Streamlit,
kullanıcı hızlı art arda bir widget'la etkileşime girdiğinde ÖNCEKİ
script çalıştırmasını iptal edip yenisini başlatır (normal davranış).
Bu iptal bir SET LOCAL transaction'ının ortasına denk gelirse, oturumun
TEK bağlantısı (her oturuma özel — bkz. önceki düzeltme) bozuk durumda
kalabiliyordu. `webcore/pg.py:_tenant_ile_calistir` artık bağlantı/
transaction hatalarında (OutOfOrderTransactionNesting, OperationalError,
InterfaceError) bağlantıyı KENDİ KENDİNE kapatıp yeniden kurar ve işlemi
BİR KEZ tekrar dener — kullanıcı hiçbir şey fark etmeden devam eder.
(Yol düzeltmesi de yapıldı: istisna sınıfı yanlışlıkla `psycopg.errors.*`
altında aranıyordu, gerçek yol `psycopg.transaction.*` — düzeltilmeseydi
except bloğu hiç çalışmayacaktı, kanıtlanarak bulundu.)

Doğrulama: sahte hata enjekte edilip yeniden bağlanma+tekrar deneme
tetiklendiği kanıtlandı; gerçek uygulama hatalarının (ValueError vb.)
yutulmadığı da ayrıca doğrulandı. Suite: 231 test.


## Düzeltme: Kimyasal Veritabanı sayfası hâlâ eski tüm-liste davranışındaydı
Umut'un doğru tespiti: bir önceki tur yalnızca Taşıma Evrakı → Ürün Ekle
bölümünü düzeltmişti; Kimyasal Veritabanı sayfası aynı hataya (text_input
+ varsayılan olarak ilk 200 kayıt) hâlâ sahipti. Netleştirme sorusuna
Umut'un cevabı: "Taşıma Evrakı'ndaki gibi — yazınca öneriler çıksın,
seçince detayları göreyim" (tablo değil, tek-kayıt arama+detay).

`sayfalar/kimyasal_veritabani.py` tamamen yeniden yazıldı: aynı
streamlit-searchbox deseni (Enter yok, yalnızca eşleşenler), bir sonuç
seçilince UN No, ad (TR/EN), sınıf, PG, tünel, TK, sınıflandırma kodu,
tali tehlike, ayrışma grubu, LQ/EQ (izin durumuyla), özel hükümler —
TÜM alanları gösteren bir detay kartı açılıyor.

Doğrulama: sayfa başlangıçta hiçbir tablo göstermiyor (yalnızca "aramak
için en az 2 karakter" mesajı), eski text_input tamamen kalktı, "1993"
araması 6 doğru sonuç veriyor. Suite: 232 test.


## Düzeltme (2. tur): "1-2 sn donma" hâlâ devam ediyordu — asıl sebep bulundu
Önceki turdaki düzeltme (5 gereksiz tek-kayıt sorgusunu kaldırma) doğruydu
ama sorunun küçük bir kısmıydı. Asıl büyük israf: sayfa her yenilendiğinde
(her seçimde) firmalar/sürücüler/araçlar/kimyasal-sayısı için 4 AYRI sorgu
atılıyordu, her biri KENDİ transaction'ını (BEGIN+SET LOCAL+SORGU+COMMIT
= 4 ağ gidiş-gelişi) açıyordu — toplam 16 gidiş-geliş, TEK bir sayfa
yenilemesinde. Streamlit Cloud → Supabase arası gerçek internet
gecikmesinde (~50-100ms/gidiş-geliş) bu, tam da bildirilen "1-2 saniye"
donmasını açıklıyor.

Düzeltme: `webcore/pg.py` → `toplu_okuma()` context manager'ı. Birden
fazla execute*() çağrısını TEK transaction'da (tek SET LOCAL, tek BEGIN/
COMMIT) birleştiriyor:
    with d.toplu_okuma():
        firmalar = d.get_companies()
        suruculer = d.get_drivers()
        araclar = d.get_vehicles()
        sayi = d.count_chemicals()
`_tenant_ile_calistir`, aktif bir toplu okuma varsa yeni transaction
açmak yerine onu paylaşıyor. `sayfalar/sevkiyat_editor.py`'de hem ana
liste yükleme (firmalar+sürücüler+araçlar+kimyasal sayısı) hem de
sevkiyat yükleme (`_yukle`: sevkiyat+kalemler) toplu_okuma'ya alındı —
16 gidiş-geliş → 6'ya indi (yaklaşık 2.7 kat azalma; PgBouncer transaction
modu açısından da doğru, ilişkili okumalar tek transaction'da aynı
arka-uçta yürüyor).

Doğrulama: doğru veri döndüğü, blok dışında normal çalıştığı, blok
içinde hata olursa cursor referansının temiz kapandığı (sızıntı yok)
test edildi. Suite: 235 test.


## Düzeltme (3. tur, Umut'un mimari tespiti): DB'ye hiç gidilmemesi gerekiyordu
Umut'un doğru gözlemi: "firma seçimi bir yenileme gerektirecek bir durum
değil" — haklıydı. toplu_okuma() (2. tur) ağ gidiş-gelişini azaltmıştı
ama hâlâ HER seçimde veritabanına gidiliyordu; oysa firma/sürücü/araç
listeleri yalnızca Firmalar/Sürücüler/Araçlar sayfalarından bir kayıt
değiştirilene kadar SABİTTİR — her dropdown seçiminde yeniden sorulmasına
hiç gerek yok.

Çözüm: `sayfalar/_ortak.py`'ye `st.cache_data(ttl=60)` tabanlı önbellek
eklendi (firmalar_listesi/suruculer_listesi/araclar_listesi/tablo_a_sayisi).
`sayfalar/sevkiyat_editor.py` artık bu önbellekli fonksiyonları kullanıyor
— aynı kiracıda 60 saniyelik pencerede tekrar seçim yapmak DB'ye HİÇ
gitmiyor, tamamen bellekten.

GÜVENLİK: st.cache_data varsayılan olarak TÜM oturumlar arası paylaşılan
bir önbellektir — tenant_id'nin (hashlenen parametre olarak, `_db`'nin
aksine) önbellek anahtarına dahil edilmesi ZORUNLUYDU, aksi hâlde bir
kiracının firma listesi başka bir kiracıya sızabilirdi. Kanıtlandı: aynı
kiracıda 3 art arda çağrı → 1 DB isteği (önbellek çalışıyor); iki farklı
kiracı → ayrı ayrı doğru veri, sızıntı yok.

Firmalar/Sürücüler/Araçlar sayfalarındaki TÜM ekleme/düzenleme
noktalarına `onbellek_temizle()` çağrısı eklendi — bir kayıt
değiştirildiğinde önbellek TTL'yi beklemeden anında tazelenir. Tablo A
manuel yeniden yüklemesi de kendi önbelleğini (`tablo_a_onbellek_temizle`)
temizliyor.

Doğrulama: DB çağrı sayacıyla önbelleğin gerçekten devreye girdiği +
kiracılar arası izolasyonun korunduğu (kritik güvenlik testi) kanıtlandı.
Suite: 237 test.


## Düzeltme: UnserializableReturnValueError (önbellekleme sonrası)
Bir önceki turun st.cache_data önbelleklemesi canlıda
`UnserializableReturnValueError` ile patladı. st.cache_data, dönen
değeri önbellek deposuna yazarken pickle'lıyor; Company/Driver/Vehicle
basit dataclass'lar olsa da Streamlit Cloud'daki Python 3.14'te bu bazen
başarısız oluyordu (yerelde 3.12'de kesin sebep yeniden üretilemedi —
sürüm farkı gibi görünüyor). Kovalamak yerine HER ORTAMDA garanti çalışan
yola geçildi: `sayfalar/_ortak.py`'deki önbellek fonksiyonları artık özel
sınıf nesneleri yerine düz sözlükler (`dataclasses.asdict`) döndürüyor —
pickle için en güvenli, en basit veri türü. Company/Driver/Vehicle
nesnelerine dönüşüm çağıran tarafta (`firmalar_listesi()` vb.) yapılıyor.

Doğrulama: önbelleğin gerçekten düz sözlük döndürdüğü, bu sözlüklerin
pickle.dumps ile sorunsuz serileştiği, ve çağıran tarafın doğru
dataclass nesnesine geri çevirdiği test edildi. Suite: 238 test.
