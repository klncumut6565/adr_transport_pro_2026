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
      webcore suite 212 test. Taşınanlar: adr_mix_pro motoru, Türkçe hata
      motoru (webcore/errors.py), doğrulama katmanı, mevzuat hesap motoru,
      LQ/EQ, onay yaşam döngüsü (test_approval), gerçek Tablo A
      (test_real_excel), güvenlik planı motor+rapor (test_security_plan_review;
      QTextDocument PDF testi WeasyPrint'e çevrildi), statik filigran
      (test_letterhead). Masaüstünde kalanlar (Qt sayfa/pencere akışları):
      test_mixload, test_excel_export, letterhead Presence/VisualEffect,
      TestRealAsutekInventory — tests/ altında çalışmaya devam ederler.
      Taşımanın yakaladığı gerçek regresyon: 66-satır düzeltmesi UNIQUE
      kısıtla birlikte yeniden-içe-aktarma tekilliğini de kaldırmıştı
      (2. yükleme 5878 kayıt yapardı); import_table_a_excel'e TAM SATIR
      İMZASI tabanlı idempotenslik eklendi (varyantlar korunur, kopya
      eklenmez) — test_idempotent yeniden yeşil.
- [ ] Faz 4.5 — "ADR Kontrol Merkezi" canlı panel + canlı evrak önizleme
      (Faz 4 biter bitmez, Faz 5'ten ÖNCE yapılacak — Umut'un önceliği).
      Masaüstü ShipmentEditorPage'in sağındaki sabit panel: 1.1.3.6 puan
      sayacı, durum göstergeleri, sürücü sertifika durumu, uyarı/hata
      listesi — TÜMÜ her alan değişiminde (firma/sürücü/araç seçimi,
      kalem ekleme/silme) ANINDA güncellenir; ayrıca alttaki "Canlı Evrak
      Önizleme" ile taşıma evrakı ekranda gerçek zamanlı biçimlendirilmiş
      olarak görünür (şu anki web'deki tek seferlik "Doğrula" butonu ve
      indir-öncesi-önizlemesiz "Taşıma Evrakı PDF" butonunun yerini alacak).
      Hedef: masaüstü deneyimiyle mümkün olduğunca kusursuz eşleşen,
      reaktif bir sevkiyat editörü — bu iş bittiğinde Faz 4'ün güvenlik
      ağı sayesinde motor tarafında regresyon riski olmadan yapılmış olacak.
- [ ] Faz 5 — Streamlit Cloud dağıtım + secrets + keep-alive workflow
- [ ] Faz 6 — Masaüstü adr_database.db → PostgreSQL veri migrasyonu

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
