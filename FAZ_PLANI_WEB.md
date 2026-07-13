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
