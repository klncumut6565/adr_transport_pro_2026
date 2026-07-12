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
- [ ] Faz 4 — 232 testin motor kısmının webcore'a uyarlanması
- [ ] Faz 5 — Streamlit Cloud dağıtım + secrets + keep-alive workflow
- [ ] Faz 6 — Masaüstü adr_database.db → PostgreSQL veri migrasyonu

## webcore/ notları
- SecurityPlanEngine.generate_inventory_review_html içindeki antet filigranı
  ShipmentEditorPage'e try/except ile bağlıydı; webcore'da bilinçli olarak boş
  düşer, Faz 3'te WeasyPrint hook'u verilecek.
- 285-493 aralığındaki lisans yardımcıları (makine parmak izi, PBKDF2) webcore'a
  ALINMADI; web kimlik doğrulaması Faz 1'de ayrı kurulacak.
