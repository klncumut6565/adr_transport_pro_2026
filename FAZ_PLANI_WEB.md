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
- [x] Faz 5 — TAMAMLANDI. Streamlit Cloud dağıtımı canlı, Secrets
      tanımlı. keep-alive workflow (.github/workflows/keepalive.yml)
      GitHub Actions izin kısıtı (token'da 'workflow' scope yoktu, bu
      dosya türü kod tarafından push edilemiyor — GitHub'ın güvenlik
      kuralı) yüzünden Umut'un kendi tarayıcısından elle eklendi.
      APP_URL repo değişkeni tanımlandı. Doğrulama: workflow API
      üzerinden elle tetiklendi, çalıştırma 'success' sonucuyla
      tamamlandı (hem job hem 'Uygulamaya ping at' adımı ayrı ayrı
      success). 15 dakikada bir otomatik çalışıyor; hem Streamlit'in
      doğal uyku moduna girmesini hem Supabase'in 7 gün istek yoksa
      duraklatma davranışını (giriş ekranındaki SELECT 1 sayesinde
      tek pingle) engelliyor.
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


## Düzeltme (nihai): UnserializableReturnValueError — st.cache_data tamamen kaldırıldı
Önceki tur (düz sözlük döndürme) canlıda AYNI hatayı vermeye devam etti,
AYNI satırda. Derinlemesine incelendi: Streamlit'in DataCache.write_result
metodu değeri DEĞİL, `CachedResult(value, messages, main_id, sidebar_id)`
sarmalayıcısını pickle'lıyor — sorun muhtemelen bu sarmalayıcının
kendisinde veya Streamlit Cloud'un Python 3.14 ortamına özgü bir pickle
davranışında; yerelde (3.12, hatta AppTest ile gerçek ScriptRunContext
içinde bile) yeniden üretilemedi. (Önceki yerel testlerde "No runtime
found, using MemoryCacheStorageManager" uyarısı çıkıyordu — bu ipucu bile
takip edilip AppTest ile gerçek bağlamda tekrar denendi, yine de
üretilemedi; sürüme özgü bir durum olduğu sonucuna varıldı.)

Kesin sebebi kovalamak yerine KÖKTEN farklı bir yola geçildi:
**st.cache_data tamamen kaldırıldı**, yerine PICKLE'A HİÇ İHTİYAÇ
DUYMAYAN `st.session_state` tabanlı elle önbellekleme kondu
(`sayfalar/_ortak.py:_onbellekli`). session_state canlı Python
nesnelerini doğrudan bellekte tutar — hiçbir serileştirme adımı yok,
dolayısıyla pickle ile ilgili hiçbir hata sınıfı bir daha oluşamaz.

Mimariyle de tutarlı: her Streamlit oturumunun zaten kendi DB bağlantısı
var (bkz. get_db() düzeltmesi), oturum başına önbellek de doğal bir
sınır — kiracılar arası sızıntı riski yapısal olarak yok (bir oturum
aynı anda yalnızca bir kiracıya bağlı).

Doğrulama: önbelleğin ikinci çağrıda üretici fonksiyonu çalıştırmadığı,
TTL dolunca yeniden ürettiği, farklı anahtarların karışmadığı,
onbellek_temizle'nin doğru çalıştığı, ve gerçek PgDatabaseManager ile
uçtan uca (DB çağrı sayacıyla) doğrulandı. Ayrıca sayfa iki kez art arda
çalıştırılıp (widget etkileşimi taklidi) hatasız olduğu kontrol edildi.
Suite: 240 test.


## Düzeltme: SRC5 zorunluluğu kaldırıldı + form-gizliliği doğrulandı
Umut'un iki isteği:
1. Yeni sürücü eklerken "SRC5 belgesi zorunlu" hatası kaldırılsın —
   `sayfalar/suruculer.py`'de form kaydı yalnızca Ad Soyad'ı zorunlu
   tutacak şekilde düzeltildi. ÖNEMLİ AYRIM: bu yalnızca FORM-seviyesi
   bir kısıtlamaydı; gerçek ADR mevzuat kontrolü (sevkiyat sırasında
   SRC5 gerekliliği, webcore/engines.py'deki motor) DEĞİŞTİRİLMEDİ —
   sürücü SRC5'siz eklenebilir ama sevkiyatta hâlâ doğru şekilde uyarılır.
2. Firmalar/Sürücüler/Araçlar sayfalarındaki "Yeni Ekle" formu tıklanmadıkça
   yer kaplamasın — KONTROL EDİLDİ, bu davranış her üç sayfada da ZATEN
   doğru uygulanmıştı (buton+session_state+st.stop() deseni). AppTest ile
   doğrulandı: form kapalıyken yalnızca arama kutusu render oluyor (form
   alanları hiç yok).

Doğrulama: üç sayfanın da varsayılan kapalı render olduğu + SRC5 olmadan
sürücü kaydının başarıyla tamamlandığı test edildi. Suite: 242 test.


## Düzeltme: 'Yeni Ekle' formu gerçekten kapanmıyordu (sayfa geçişinde kalıcıydı)
Önceki tur yalnızca "sayfaya İLK KEZ girildiğinde form kapalı mı?" diye
test etmişti — bu her zaman doğruydu. Umut'un "hâlâ gözüküyor" demesi
FARKLI bir senaryoya işaret ediyordu: form_ac bayrağı st.session_state'te
tutulur ve OTURUM boyunca kalıcıdır. Kullanıcı formu açıp (Kaydet/İptal
demeden) BAŞKA bir sayfaya geçip sonra GERİ dönerse, form_ac hâlâ True
olduğundan form açık görünmeye devam ediyordu — bu, kesinlikle gerçekleşmiş
olması muhtemel bir senaryo (bugün onlarca test turu boyunca sayfalar
arası çokça geçiş yapıldı).

Kanıtlandı (AppTest ile üç ayrı script çalıştırması, session_state
elden ele taşınarak): Sürücüler → Yeni Sürücü tıkla (form_ac=True) →
Firmalar'a geç → Sürücüler'e GERİ dön → form_ac hâlâ True ÇIKTI (bug
doğrulandı).

Düzeltme: `sayfalar/_ortak.py` → `sayfaya_taze_girildi(sayfa_adi)`.
Aktif sayfa adını session_state'te izler; BAŞKA bir sayfadan bu sayfaya
YENİ geçildiyse form_ac bayrağını zorla False'a çeker. Firmalar/
Sürücüler/Araçlar'ın üçünde de uygulandı.

İki senaryo da test edildi: (1) form açıkken başka sayfaya gidip geri
dönünce KAPANIYOR, (2) AYNI sayfada kalıp bir alanla etkileşime girerken
(ör. yazı yazarken) YANLIŞLIKLA KAPANMIYOR (devam eden veri girişi
korunuyor). Suite: 244 test.


## Özellik eklendi: Taşınan Ürünler kalemleri artık düzenlenebiliyor
Umut'un tespiti doğruydu: kaydedilmiş bir ürün kalemi yalnızca 🗑️ ile
silinebiliyordu, düzenlemek için silip yeniden eklemek gerekiyordu.
`sayfalar/sevkiyat_editor.py`'ye ✏️ Düzenle butonu eklendi — tıklanınca
satır, ambalaj türü/adedi/net miktar/birim/LQ/EQ alanlarını önceden
doldurulmuş şekilde gösteren bir düzenleme formuna dönüşüyor ("💾
Değişikliği kaydet" / "Vazgeç" butonlarıyla).

Bilinçli tasarım kararı: kimyasal (UN/ad/sınıf/PG/tünel vb. — Tablo A'dan
gelen alanlar) düzenlenemiyor, yalnızca kalem-özel bilgiler (ambalaj,
miktar, LQ/EQ) değiştirilebiliyor. Kimyasal yanlışsa silip doğru
kimyasalla yeniden eklemek daha güvenli — yarı-güncellenmiş bir kalemin
Tablo A alanlarıyla tutarsız kalması riskini önler.

Doğrulama: düzenle → alanları değiştir → kaydet → kalem yerinde
güncellendi + UN numarası değişmedi + düzenleme modu kapandı; ayrıca
Vazgeç'in hiçbir değişiklik uygulamadığı ayrı test edildi. Suite: 246 test.


## Düzeltme: 'ADR Belge No' / 'ADR Bitiş' alanları sürücü formundan kaldırıldı
Umut'un talebi: sürücü ekleme/düzenleme formundaki bu iki hücre gereksiz
yer kaplıyordu, kaldırıldı. Önemli teknik ayrıntı: bu alanlar veritabanında
ve mevzuat motorunda (webcore/engines.py'deki sürücü ADR sertifikası
kontrolü, sürücü listesindeki "ADR: ..." gösterimi, Taşıma Evrakı Kontrol
Merkezi panelindeki sertifika durumu) HÂLÂ CANLI KULLANILIYOR — bu yüzden
yalnızca form GİRİŞ alanları kaldırıldı, veri modeli/iş mantığı
DEĞİŞMEDİ.

KRİTİK KORUMA: mevcut bir sürücü DÜZENLENİRKEN önceden girilmiş ADR
belge bilgisinin form alanı yok diye SESSİZCE SİLİNMEMESİ sağlandı —
değerler "Düzenle" tıklanınca zaten session_state'e yükleniyordu, kayıt
sırasında görünmeyen alanlardan değil doğrudan session_state'ten okunup
korunuyor. Yeni sürücüde alan boş kalır (SRC5 ile aynı mantık — mevzuat
kontrolü o zaman "sertifika yok" uyarısı verir, beklenen davranış).

Doğrulama: formda ADR alanlarının artık görünmediği + önceden ADR belgesi
girilmiş bir sürücü düzenlenip başka bir alan (telefon) değiştirildiğinde
ADR belge no/bitişinin VERİ TABANINDA DEĞİŞMEDEN kaldığı (veri kaybı
kanıtlı şekilde yok) test edildi. Suite: 248 test.


## Düzeltme: ADR Kontrol Merkezi paneli masaüstünün büyük kısmını göstermiyordu
Umut'un tespiti: web panelinde masaüstündeki hesaplanan çoğu şey hiç
görünmüyordu. Kök sebep: web, masaüstünün kullandığı TEK gerçek kaynak
fonksiyonu (ADREngine.generate_adr_report — puan, plaka, tünel, yazılı
talimat, muafiyet türü ve TÜM uyarı seviyelerini bir arada üretir)
KULLANMIYORDU; bunun yerine calculate_1136_points + 
calculate_tunnel_restriction + validate_shipment'ı AYRI AYRI çağırıyordu.

Eksik çıkanlar:
1. **Yazılı Talimat (ADR 8.1.2.1) göstergesi** — masaüstünde var, web'de
   hiç yoktu. Eklendi.
2. **Muafiyet türü göstergesi** (rapor.exemption_type) — hiç yoktu.
   Eklendi.
3. **info seviyeli mesajlar** — masaüstü "Uyarı ve Hatalar" listesinde
   errors/warnings YANINDA info mesajlarını da gösterir (ör. "SRC5
   belgesi: X", "1.1.3.6: Miktar muafiyeti uygulanır" gibi onay/
   bilgilendirme satırları). Web yalnızca errors+warnings gösteriyordu,
   info'yu sessizce atıyordu. Artık ℹ️ ile ayrı gösteriliyor.

`sayfalar/sevkiyat_editor.py`'deki Kontrol Merkezi paneli artık TEK bir
`generate_adr_report()` çağrısından besleniyor — masaüstüyle birebir aynı
hesaplama yolu, ayrı fonksiyonların birbirinden sapması riski kalmadı.

Doğrulama: Sınıf 1 senaryosunda Yazılı Talimat + Muafiyet göstergelerinin
göründüğü, SRC5'li sürücüde info mesajının kaybolmadığı test edildi.
Suite: 246 test.


## Düzeltme: 'Veritabanına şu an ulaşılamıyor' uyarısı pasife alındı
Umut'un talebi: giriş ekranındaki sarı uyarı kutusu görsel gürültü
yaratıyordu, istemedi ama silinmesini de istemedi ("belki daha sonra
açtırırım"). `app.py`'ye `DB_ULASILAMADI_UYARISI_GOSTER = False` bayrağı
eklendi — yalnızca uyarı METNİNİN görünürlüğünü kontrol eder.

KRİTİK KORUMA: bayrak False olsa bile `get_db().execute_one("SELECT 1 AS
ping")` çağrısı HER ZAMAN çalışır — bu ping, Faz 5/6'da kurulan keep-alive
mekanizmasının veritabanı ayağıdır (GitHub Actions'ın 15 dakikada bir
attığı HTTP isteği bu satır sayesinde Supabase'e de dokunur; aksi hâlde
yalnızca Streamlit'i uyanık tutar, Supabase'in 7 gün duraklatma sayacını
SIFIRLAMAZ). Yani bu değişiklik keep-alive'ı bozmadan yalnızca kullanıcı
deneyimini sadeleştirdi.

Doğrulama: DB'ye kasıtlı yanlış bağlantı dizesiyle bağlanıp uyarının
göstermediği + giriş formunun yine de göründüğü + bayrağın tek satırla
geri açılabilir olduğu test edildi. Suite: 248 test.


## KRİTİK düzeltme: Canlı Önizleme "Gerekli bir kütüphane kurulu değil" hatası
Kök sebep: `webcore/transport_doc.py`'de `import qrcode`, fonksiyonun EN
BAŞINDA, `doc_show_qr` ayarı KAPALI olsa bile KOŞULSUZ çalışıyordu.
`qrcode` paketi `requirements.txt`'te hiç yoktu (Streamlit Cloud'da kurulu
değildi) — bu yüzden Canlı Önizleme/PDF üretimi HER ZAMAN, QR kodu hiç
istenmese bile "Gerekli bir kütüphane kurulu değil" hatasıyla çöküyordu.

İlk şüphem Pillow'du (aynı dosyada `build_letterhead_watermark_b64`
Pillow kullanıyor) — ama test ettim, o zaten kendi ImportError'ını
zarifçe yutuyordu (Pillow yokken bile çalışıyor). Sistematik bir AST
taramasıyla webcore/ altındaki TÜM üçüncü parti importları
requirements.txt ile karşılaştırınca gerçek suçlu bulundu: qrcode.

Düzeltme: import artık yalnız `show_qr` gerçekten True ise çalışıyor
(fonksiyon başından `if show_qr:` bloğunun içine taşındı) + kendi
ImportError'ını da Pillow'daki gibi zarifçe yutuyor (paket yine de eksik
kalırsa QR'sız devam eder, çökmez) + paket gerçekten requirements.txt'e
eklendi (qrcode[pil]).

Doğrulama: 4 kombinasyon test edildi (QR açık/kapalı × paket kurulu/eksik)
— hepsi doğru davranıyor; en kritik olanı (3. senaryo: QR kapalı + paket
eksik) artık başarılı, bu asıl hatanın birebir kanıtıydı. Ayrıca AST
taramasıyla webcore/ genelinde başka gizli eksik bağımlılık kalmadığı
doğrulandı (Pillow, qrcode, weasyprint, psycopg, rapidfuzz, openpyxl,
streamlit — hepsi requirements.txt'te). Suite: 251 test.


## Üç düzeltme: ikinci ürün eklerken donma + PDF önizleme sığmama + karışık yükleme sorgusu
Umut'un üç ayrı geri bildirimi:

**1) KRİTİK — ikinci ürün eklerken donma:** `streamlit-searchbox`
(üçüncü parti bileşen) sabit bir `key="urun_arama_kutusu"` kullanıyordu.
Her ürün eklendikten sonra çağrılan `st.rerun()`, bileşenin kendi JS↔
Python durumunu TAŞIYARAK yeniden render etmesine yol açıyordu — bu,
bileşenin senkronizasyonunu kaybedip donmasına neden oluyordu (bilinen
bir custom-component deseni: dışarıdan tetiklenen rerun + sabit key).
Düzeltme: anahtar artık `f"urun_arama_kutusu_{len(kalemler)}"` — kalem
sayısı değiştikçe (her eklemeden sonra) bileşen SIFIRDAN, temiz durumla
başlıyor, önceki durum hiç taşınmıyor.

**2) PDF önizlemesi tam sığmıyordu:** `wrap_for_screen_preview` sabit
`width: 210mm` (~794px) kullanıyordu — ADR Kontrol Merkezi'nin DAR sağ
sütununda (toplam genişliğin ~%30'u) bu, yatay taşma/kırpılmaya yol
açıyordu. Düzeltme: sayfa A4 oranlarında sabit inşa edilir ama JS ile
iframe'in GERÇEK genişliği ölçülüp `transform: scale()` ile orantılı
küçültülüyor — hangi panelde gösterilirse gösterilsin tam sığıyor.

**3) Karışık yükleme canlı sonuçları:** zaten vardı ve doğru çalışıyordu
— `ADREngine.check_compatibility(items)` her render'da çağrılıyor,
sonuçlar "Uyarı ve Hatalar" bölümünde "Uyumsuzluk: ..." olarak
gösteriliyor. Gerçek bir uyumsuz ikili (Asitler+Bazlar) ile test edilip
doğru tespit ettiği kanıtlandı.

Doğrulama: 2 ürünlü durumun hatasız render olduğu, arama kutusu
anahtarının dinamik olduğu, sarmalayıcının içerik/JS/PDF-izolasyonunu
koruduğu, karışık yükleme kontrolünün gerçek bir uyumsuzluğu yakaladığı
test edildi. Suite: 254 test.


## KRİTİK MİMARİ DÜZELTME: Karışık Yükleme artık GERÇEK motoru kullanıyor
Umut'un haklı itirazı: bir önceki turdaki "zaten doğru çalışıyor"
değerlendirmem YANLIŞTI. Hem ADR Kontrol Merkezi paneli hem ayrı
"Karışık Yükleme Kontrolü" sayfası, `webcore.engines.ADREngine.
check_compatibility` adında BASİTLEŞTİRİLMİŞ bir kontrol kullanıyordu —
yalnızca segregation_group alanı + sabit, hayali bir INCOMPATIBILITY_
MATRIX sözlüğüne dayanıyordu. Test ettiğimde bu sahte matrisin
"Asitler+Bazlar" gibi GERÇEK ADR kuralına dayanmayan bir çift ürettiğini
gördüm.

Masaüstü ise "ADR Mix Checker Pro v2.4.1" kökenli, 71 birim testli GERÇEK
bir motor kullanıyor: `adr_mix_pro` paketi — tam segregasyon kural
motoru (resources/data/segregation_rules.csv, ADR 7.5.2 tam tablosu),
Sınıf 1 patlayıcı dipnotları (a/b/c/d, 7.5.2.2), CV28 gıda ayrımı kuralı
(7.5.4), tünel kısıtı notları, risk puanlama. Bu paket repoda zaten
duruyordu (Qt'ye hiç bağımlı değil), yalnızca web'e hiç bağlanmamıştı.

**Kritik keşif — masaüstü kendi ürünüyle bile dosya-tabanlı motoru
DOĞRUDAN kullanmıyor:** monolitte `MixLoadCheckPage`, adr_mix_pro'nun
Excel-okuyan `ProductDatabase`'i yerine `AnaDbChemicalAdapter` adında
kendi SQL veritabanına (chemicals tablosu) bağlanan bir ADAPTÖR
kullanıyor. `webcore/mix_adapter.py` bu adaptörün BİREBİR web karşılığı
(`PgChemicalAdapter`) — SQL sorguları masaüstünden birebir alındı,
webcore.pg'nin TranslatingCursor'ı `?`→`%s`/`LIKE`→`ILIKE` çevirisini
otomatik yaptığı için sorgu metinleri değişmeden çalıştı.

Aynı UN'ün Tablo A'da birden fazla varyasyonu olabileceği için (ör.
UN1950→12 satır), adaptör kayıtları toptan yüklemez — her UN,
`register_variant()` ile HANGİ varyasyonun kullanılacağı (sevkiyat
kaleminin zaten taşıdığı classification_code/packing_group'tan) açıkça
belirtildikten sonra belleğe alınır; masaüstündeki güvenlik tasarımı
aynen korundu.

`sayfalar/sevkiyat_editor.py` (Kontrol Merkezi paneli) ve
`sayfalar/karisik_yukleme.py` (ayrı sayfa, ayrıca streamlit-searchbox'a
geçirildi) artık ikisi de bu GERÇEK motoru kullanıyor.

Doğrulama: UN0081(Sınıf1 patlayıcı)+UN1978(Propan) → GERÇEK motor "NO,
ADR 7.5.2.1, dipnot istisnası yok" diyor (eski sahte matris bunu hiç
bilmiyordu); UN1830+UN1824 (ikisi Sınıf 8) → OK dönüyor (motorun her
şeyi yasaklamadığının kanıtı); bilinmeyen UN çökme yerine UNKNOWN
dönüyor; zincirde pandas gerektiren dosya-tabanlı ProductDatabase'e HİÇ
dokunulmadığı statik olarak doğrulandı (pandas zaten Streamlit'in kendi
zorunlu bağımlılığı, ekstra risk yok). Suite: 258 test.


## Düzeltme (2. tur): PDF önizlemesi hâlâ sığmıyordu — JS zamanlama sorunu
Umut'un ekran görüntüsü kanıtladı: önizleme yalnızca tarayıcı %33'e
küçültülünce sığıyordu — yani ilk düzeltmenin JS ölçekleme mantığı
Streamlit'in components.html/srcdoc ortamında hiç çalışmamıştı.

Kök sebep (kesinleştirilemedi ama en olası): `window.addEventListener
('load', ...)` + birkaç setTimeout, srcdoc ile yerleştirilen bir
iframe'de zamanlama açısından güvenilmez.

İki katmanlı düzeltme:
1. **Güvenli varsayılan ölçek:** JS hiç çalışmasa/gecikse BİLE geçerli
   olan satır-içi CSS `transform: scale(0.5)` — artık "JS çalışmazsa hiç
   sığmama" senaryosu yapısal olarak imkansız, en kötü ihtimalle sabit
   %50 küçültme uygulanır (dar panelde makul bir varsayım).
2. **ResizeObserver:** `load` olayına tek başına güvenmek yerine, tarayıcının
   KENDİSİ konteynerin GERÇEK nihai boyutuna ulaştığında tetiklediği
   `ResizeObserver` API'sine geçildi — zamanlama varsayımına dayanmaz.
   `load`/`resize` + 6 farklı gecikmeli deneme (0-1200ms) ek güvenlik ağı
   olarak korundu.

Doğrulama: sarmalamanın güvenli varsayılan ölçeği + ResizeObserver'ı +
birden fazla zamanlama denemesini içerdiği, içeriğin/@page kuralının
korunduğu, PDF yolunun hâlâ etkilenmediği test edildi. Suite: 261 test.


## Doğrulama: Umut'un 20 senaryolu ADR 2025 karışık yükleme testi
Gerçek adr_mix_pro motoru, Umut'un hazırladığı 20 senaryolu titiz test
setiyle sınandı. Sonuç: **14/20 tam isabet**, 4'ü kural tablosu kapsam
sınırı (UNKNOWN, yanlış değil — "tahmin etme" güvenli tasarımı), 2'si
(Test 8, 10) Umut'un doğrulamasıyla GEÇERSİZ test verisi olduğu için
kapsam dışı bırakıldı.

**Test 8/9/10 çözümü (Umut'un talebiyle güncellendi):** İlk şüphem, sistemin D-G patlayıcı uyumluluk grubu
verisinin (compatibility_groups.py: D↔G="X") yanlış olabileceğiydi —
harici bir kaynakla (Kanada TDG) çelişiyordu. Umut, kendi Tablo A'sını
kontrol edip sistemdeki UN0336(1.4G)/UN0027(1.1D) verisinin DOĞRU
olduğunu, test dokümanındaki varsayımların (1.1D/1.3G, ters) YANLIŞ
olduğunu doğruladı. Umut ardından Test 9'un da (UN0336+UN3077) aynı
kaynaktan geldiğini belirtip üçünü de (8/9/10) görmezden almamı istedi
— Test 9'un kilitli regresyon testi de kaldırıldı. D-G uyumluluk sorusu
bu turda kapanmadı (test verisi geçersiz olduğu için sınanamadı) — ayrı
bir zamanda gerçek bir D-G çiftiyle yeniden test edilebilir.

**Kalıcı kayıt altına alınanlar (TestKarisikYuklemeAdr2025Dogrulama,
18 test):**
- 13 çift → tam isabet, kalıcı regresyon testi olarak kilitlendi (Test 9 sonradan Umut'un talebiyle çıkarıldı — bkz. yukarı)
- 4 çift (UN1005+1202, UN1017+1202, UN2014+1202, UN1744+2014) → UNKNOWN
  davranışı BİLİNÇLİ ve BEKLENEN olarak belgelenip kilitlendi (ikincil
  tehlike +8/+5.1 kombinasyonları segregation_rules.csv'de (277 satır)
  eksik — motor tahmin etmiyor, "manuel kontrol" diyor)
- Ekran görüntüsüyle doğrulanan ek senaryo: 1000 puanı büyük ölçüde aşan
  (10200) bir sevkiyatta ilerleme çubuğunun %100'de tavanlandığı,
  turuncu plakanın doğru ZORUNLU çıktığı ayrıca test edildi

**AÇIK KALAN (Umut'un kararına bağlı):**
1. segregation_rules.csv'nin ikincil tehlike (+8, +5.1, +6.1 vb.)
   kombinasyonlarını kapsayacak şekilde genişletilmesi — şu an 4 gerçek
   senaryo UNKNOWN dönüyor, tam ADR 7.5.2.1 tablosu bu kombinasyonları
   da içeriyor.
2. UN2814 (Bulaşıcı Madde) + gıda ayrımı sorusu: sistemdeki kayıtta
   özel_hükümler="318" var, CV28 gibi bir gıda-ayrımı kodu yok — motor
   "gerekmez" diyor. Bu, gerçek ADR Tablo A'da UN2814'ün CV28 taşıyıp
   taşımadığı sorusu, Umut'un doğrulaması gerekiyor.

Suite: 278 test (Test 9 çıkarıldıktan sonra).


## Düzeltme: boş durumda yanıltıcı 'turuncu plaka gerekmez' sonucu
Umut'un tespiti: hiç ürün eklenmeden önce panel "0/1000 puan (%0)" +
yeşil "Turuncu plaka gerekmez (1.1.3.6 muafiyeti)" gösteriyordu — bu,
sanki bir sonuca varılmış gibi YANILTICIYDI; aslında henüz hiçbir şey
hesaplanmamıştı, hesaplanacak veri yoktu. Düzeltme: `items` boşken artık
nötr bir "Ürün eklendikçe puan ve turuncu plaka durumu burada
hesaplanacak." mesajı gösteriliyor; ürün eklenince normal hesaplama
(ilerleme çubuğu + gerçek plaka durumu) devam ediyor, davranış değişmedi.

Doğrulama: boş durumda ne yanıltıcı "gerekmez" mesajının ne de "0/1000"
metninin göründüğü, yeni bilgi mesajının doğru çıktığı, ürün eklenince
normal hesaplamanın bozulmadan devam ettiği test edildi. Suite: 280 test.


## Düzeltme: sol menü daraltıldı, ADR Kontrol Merkezi paneli genişletildi
Umut'un talebi: sol gezinme menüsü gereksiz yere geniş alan kaplıyordu,
sağdaki ADR Kontrol Merkezi paneli (özellikle Canlı Evrak Önizleme) bu
yüzden dar kalıyordu.

İki değişiklik (`app.py` + `sayfalar/sevkiyat_editor.py`):
1. Sol gezinme menüsü CSS ile daraltıldı (`[data-testid="stSidebar"]`,
   varsayılan ~336px'ten 230px'e) — `app.py`'de global olarak enjekte
   edildiği için TÜM sayfalarda geçerli, tek yerden yönetiliyor.
2. Taşıma Evrakı'ndaki sol/sağ sütun oranı `[2.3, 1]` → `[1.7, 1]`
   olarak değiştirildi; sağ panel (Kontrol Merkezi) artık daha geniş.

Doğrulama: CSS'in gerçekten sayfada bulunduğu (data-testid seçicisi +
min-width değeri) ve sütun oranının doğru güncellendiği test edildi;
her iki sayfanın da (app.py giriş sonrası, sevkiyat_editor.py) hatasız
render olmaya devam ettiği doğrulandı. Suite: 282 test.


## Düzeltme (3. tur): önizleme yüksekliği aşırı büyüdü + sağa kayma
Umut'un iki gözlemi: (1) önizlemenin yükseklik alanı çok büyümüş,
içerik görünmüyordu, (2) panel genişledikçe önizleme sağa doğru
kayıyormuş gibi görünüyordu.

**Kök sebep 1 (yükseklik):** Önceki turda eklenen `ResizeObserver`,
`document.body`'yi izliyordu — AMA `olcekle()` fonksiyonunun kendisi
`sarici.style.height`'i değiştiriyordu, bu da body'nin doğal
yüksekliğini etkileyip ResizeObserver'ı TEKRAR tetikliyordu: kendi
kendini besleyen bir döngü. Küçük bir yuvarlama sapması bile bu
döngüde birikip yüksekliğin sürekli büyümesine yol açabiliyordu.

**Kök sebep 2 (sağa kayma):** `#__a4_sarici` `margin: 0 auto` ile
ORTALANIYORDU — panel genişledikçe sabit-genişlikli (ölçeklenmiş)
içerik, ortalama nedeniyle konteynerin ortasına doğru "kayıyormuş" gibi
görünüyordu.

**Düzeltme:**
1. ResizeObserver TAMAMEN kaldırıldı — yerine yalnızca `window` resize
   olayı kullanılıyor. Bu, İÇERİK değişikliklerinden (kendi height
   ayarımızdan) ASLA tetiklenmez, yalnızca panel/pencere GERÇEKTEN
   yeniden boyutlanınca — geri besleme döngüsü yapısal olarak imkansız.
2. Tekrar-hesaplama önleme: ölçek gerçekten değişmediyse (>%1 fark
   yoksa) DOM'a hiç dokunulmuyor — ek güvenlik katmanı.
3. `margin: 0 auto` → `margin: 0`, `transform-origin: top center` →
   `top left` — içerik artık panel genişliğinden bağımsız olarak SOL
   kenara sabit, öngörülebilir konumda.

Ayrıca bu turda bir kendi hatamı da düzelttim: ilk yazdığım JS
yorumlarının birkaçında yanlışlıkla Python yorum işareti (#) kullanmışım
— bu geçerli JavaScript değil, tarayıcıda sözdizimi hatasına yol açardı.
Node.js ile (`node --check`) JS'in gerçekten derlenebilir olduğu
doğrulandı.

Doğrulama: sol hizalama, ResizeObserver'ın gerçekten kaldırıldığı,
window resize'ın kullanıldığı, tekrar-hesaplama önlemenin varlığı ayrı
ayrı test edildi. Suite: 284 test.


## Düzeltme (4. tur): dış çerçeve sabit yükseklikte kalıyordu
Umut'un tespiti: içerik doğru ölçekleniyordu ama panelin DIŞ ÇERÇEVESİ
(components.html'in iframe'i) sabit height=850 kaldığı için altında
büyük bir boş gri alan kalıyordu — "satır yüksekliği de orantılı
büyütülüp küçültülmeli" talebi.

Düzeltme: Streamlit'in TÜM components.html iframe'lerinde dinlediği
standart `streamlit:setFrameHeight` postMessage protokolü kullanılarak
dış çerçeve de JS tarafından GERÇEK içerik yüksekliğine göre anında
ayarlanıyor. Python tarafındaki `height=` parametresi artık yalnızca
JS çalışana kadarki başlangıç değeri (850 → 400'e indirildi,
`scrolling=False` — kaydırmaya gerek kalmadı, yükseklik zaten doğru).

**Süreç notu:** bu düzeltmeyi yazarken AYNI hatayı (JS yorumlarında
yanlışlıkla Python # işareti kullanma) İKİNCİ KEZ yaptım — ilk seferinde
1 satırda, düzeltirken gözden kaçan 3 satır daha vardı. Node.js ile
(`node --check`) sistematik taradım, hepsini buldum ve düzelttim. Bunun
bir daha sessizce kaçmaması için KALICI bir test eklendi
(TestOnizlemeJSGercektenGecerli) — her `pytest` çalıştırmasında üretilen
JS gerçekten Node ile derleniyor, Python-tarzı yorum kalıntısı ayrıca
regex ile de aranıyor.

Doğrulama: JS'in Node ile gerçekten derlendiği, dış çerçeve otomatik
yükseklik bildiriminin (postMessage) var olduğu test edildi. Suite:
286 test.


## Düzeltme: giriş ekranı pasife alındı (Umut'un talebi)
Umut'un talebi: kullanıcı adı/şifre giriş ekranı pasif yapılsın —
silinmesin, geri açılabilir olsun (aynı desen: DB_ULASILAMADI_UYARISI_
GOSTER). `app.py`'ye `GIRIS_EKRANI_AKTIF = False` bayrağı eklendi.

⚠️ **GÜVENLİK UYARISI (Umut'a iletildi):** bu bayrak False iken uygulama
HİÇBİR kimlik doğrulaması yapmadan doğrudan açılıyor. Uygulama genel
erişime açık (Streamlit Cloud) ve gerçek iş verisi (firmalar, sürücüler,
sevkiyatlar) barındırıyor — bu durumda adresi bilen HERKES tüm veriye
erişebilir. Bu, bilinçli olarak uygulanan bir istekti, kod tarafında
engellenmedi (kullanıcının kendi iş kararı), ama riskin net şekilde
belirtildiği bir uyarı yorum olarak koda ve bu belgeye işlendi.

Uygulama: `main()`, GIRIS_EKRANI_AKTIF=False iken `_login_page()`'i hiç
çağırmıyor — bunun yerine sistemdeki İLK AKTİF kullanıcıyı veritabanından
çekip otomatik oturum açıyor (tenant_id dahil, hardcode edilmiş bir
değere güvenmiyor — kiracı bağlamı hâlâ doğru kuruluyor). DB'ye
ulaşılamazsa (giriş formunun aksine eskiden koruması olmayan bu yeni
yolda) artık zarifçe hata gösterip duruyor, çökmüyor.

Test stratejisi: gerçek giriş FORMUNU test eden 3 eski test + 1 DB-uyarı
testi, GIRIS_EKRANI_AKTIF=False iken anlamsız olduğu için SİLİNMEDİ,
bilinçli olarak ATLANIYOR (bayrak tekrar True yapılırsa otomatik
yeniden aktif olurlar — regresyon koruması kaybolmuyor). Yeni bypass
davranışı için 2 test eklendi: form hiç görünmüyor + otomatik giriş
yapılıyor, DB hatasında zarifçe hata (çökme değil). Suite: 284 test
(4 bilinçli atlama).
