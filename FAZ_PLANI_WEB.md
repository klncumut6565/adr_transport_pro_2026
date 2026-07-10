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
- [ ] Faz 0b — PostgreSQL katmanı: DatabaseManager ile AYNI genel arayüzü sunan
      PgDatabaseManager (psycopg), şema çevirisi (AUTOINCREMENT→IDENTITY,
      PRAGMA'lar kalkar), tüm tablolara company_id + bileşik indeksler.
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
