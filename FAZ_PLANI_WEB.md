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
- [ ] Faz 1 — Kimlik doğrulama + çoklu firma (streamlit-authenticator, company_id filtresi)
- [ ] Faz 2 — 12 sayfanın st.navigation ile taşınması
- [ ] Faz 3 — PDF: QTextDocument+QPrinter → WeasyPrint (HTML şablonlar korunur;
      SecurityPlanEngine filigran hook'u burada bağlanır)
- [ ] Faz 4 — 232 testin motor kısmının webcore'a uyarlanması
- [ ] Faz 5 — Streamlit Cloud dağıtım + secrets + keep-alive workflow
- [ ] Faz 6 — Masaüstü adr_database.db → PostgreSQL veri migrasyonu

## webcore/ notları
- SecurityPlanEngine.generate_inventory_review_html içindeki antet filigranı
  ShipmentEditorPage'e try/except ile bağlıydı; webcore'da bilinçli olarak boş
  düşer, Faz 3'te WeasyPrint hook'u verilecek.
- 285-493 aralığındaki lisans yardımcıları (makine parmak izi, PBKDF2) webcore'a
  ALINMADI; web kimlik doğrulaması Faz 1'de ayrı kurulacak.
