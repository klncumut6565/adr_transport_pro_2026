# Graph Report - adr_transport_pro_2026  (2026-11-16)

## Corpus Check
- 105 files · ~377,263 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 6 file(s) not represented in the graph (top: (none) 2, .ttf 2, .ico 1)

## Summary
- 2270 nodes · 4566 edges · 117 communities (56 shown, 61 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 348 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `48bffcc1`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- SafetyPlansPage
- ProductDatabase
- test_app_ui.py
- .check_all
- ProductRecord
- PgDatabaseManager
- _ortak.py
- pdf_export.py
- ShipmentEditorPage
- test_webcore_smoke.py
- DriverManagementPage
- pathlib
- SegregationRuleEngine
- test_lq_eq.py
- adr_csv_importer.py
- MixChecker
- ADR Transport Pro 2026 — Karışık Yükleme Entegrasyonu
- ADREngine
- main_window.py
- adr_transport_pro_2026.py
- SecurityManager
- test_security_plan_review_report.py
- test_security_plan_review.py
- ADRDatabasePage
- test_lq_eq_ana_program.py
- ADRTransportPro
- ADR Transport Pro — Web'e Geçiş (Tek Sistem Kararı)
- item
- ADREngine
- webcore/models.py
- sevkiyat_editor.py
- ._build_print_html
- SecurityPlanEngine
- .execute_update
- ._check_explosive_interaction
- DatabaseManager
- item
- test_letterhead_ana_program.py
- transport_doc.py
- wrap_for_screen_preview
- DatabaseManager
- test_mixload_ana_program.py
- TestVariantSelection
- ShipmentArchivePage
- MainWindow
- ExcelChemicalPage
- Chemical
- TestTarihSeciciVeAracTipiDropdown
- test_validation.py
- .check
- LoginDialog
- ReportsPage
- needs
- needs
- SecurityPlanEngine
- Company
- SecurityAdminPage
- ResultDetailPanel
- ResultsTableModel
- tests/conftest.py
- turkce_hata_metni
- .execute_one
- test_approval_ana_program.py
- test_validation_ana_program.py
- test_approval.py
- TestOnbellekliListelerSessionState
- PrintPreviewDialog
- PackagingTypeDelegate
- webcore/ (web engine layer, Qt-free)
- ._tenant_ile_calistir
- keepalive.yml
- logging_setup.py
- score_result
- AuthManager
- .import_company_inventory_excel
- validators.py
- TestEskiSahteKontrolKaldirildi
- auth.py
- TestCanliOnizlemeGercekHtml
- _export
- TestTurkishErrorTranslation
- TestKarisikYuklemeAdr2025Dogrulama
- TestGercekKarisikYuklemeMotoru
- Architecture
- TestReportEnforcement
- TestTabloAVaryantKaybi
- TestRealAsutekInventory
- TestFlexibleDates
- TestSayfaGecisindeFormKapaniyor
- TestRealAsutekInventoryScreening
- ADR Transport Pro 2026 — Masaüstü Kurulumu
- SimpleProductDatabase
- TestKalemDuzenleme
- translate_query
- Vehicle
- ASUTEK_Kimyasal_İnceleme_Kimyasal_Envanter__ADR_rev1_519ff6f1.md
- TestAyarlarSayfasi
- TestUrunEkleCanliArama
- tunnel_rules.py
- AboutDialog
- Test Paketi — Karışık Yükleme Entegrasyonu
- ADR_A_TABLOSU_0ee109f1.md

## God Nodes (most connected - your core abstractions)
1. `PgDatabaseManager` - 94 edges
2. `DatabaseManager` - 86 edges
3. `DatabaseManager` - 82 edges
4. `ShipmentEditorPage` - 59 edges
5. `ProductRecord` - 56 edges
6. `MainWindow` - 50 edges
7. `ADR Transport Pro — Web'e Geçiş (Tek Sistem Kararı)` - 42 edges
8. `ADREngine` - 41 edges
9. `MixChecker` - 40 edges
10. `ADRTransportPro` - 36 edges

## Surprising Connections (you probably didn't know these)
- `Düzeltme: UnserializableReturnValueError (önbellekleme sonrası)` --references--> `firmalar_listesi()`  [INFERRED]
  FAZ_PLANI_WEB.md → sayfalar/_ortak.py
- `adr_mix_pro/ (mixed-load / segregation engine)` --references--> `ProductDatabase`  [INFERRED]
  CLAUDE.md → adr_mix_pro/core/database.py
- `webcore/ (web engine layer, Qt-free)` --references--> `ProductDatabase`  [INFERRED]
  CLAUDE.md → adr_mix_pro/core/database.py
- `KRİTİK MİMARİ DÜZELTME: Karışık Yükleme artık GERÇEK motoru kullanıyor` --references--> `ProductDatabase`  [INFERRED]
  FAZ_PLANI_WEB.md → adr_mix_pro/core/database.py
- `adr_mix_pro/ (mixed-load / segregation engine)` --references--> `SegregationRuleEngine`  [INFERRED]
  CLAUDE.md → adr_mix_pro/core/rule_engine.py

## Import Cycles
- None detected.

## Communities (117 total, 61 thin omitted)

### Community 0 - "SafetyPlansPage"
Cohesion: 0.06
Nodes (5): CompanyEditDialog, CompanyManagementPage, SafetyPlansPage, SettingsPage, _turkce_hata_metni()

### Community 1 - "ProductDatabase"
Cohesion: 0.06
Nodes (14): _looks_like_header_artifact(), _normalize_header(), ProductDatabase, _read_csv_robust(), ADRError, ColumnNotFoundError, DatabaseError, ExportError (+6 more)

### Community 2 - "test_app_ui.py"
Cohesion: 0.04
Nodes (16): at(), _giris_ekrani_aktif_mi(), TestBosDurumdaYaniltciSonucGosterilmez, TestDBUlasilamadiUyarisiPasif, TestEskiKayitEvrakNoBos, TestGirisAkisi, TestGirisEkraniPasifModu, TestIkinciUrunEklemeDonmasi (+8 more)

### Community 3 - ".check_all"
Cohesion: 0.05
Nodes (11): TestClass7Labels, TestExplosives, TestFoodCaution, TestInputHygiene, TestUnNormalization, sample_results(), TestClass7Labels, TestExplosives (+3 more)

### Community 4 - "ProductRecord"
Cohesion: 0.07
Nodes (9): check_food_separation(), FoodSeparationOutcome, ProductRecord, _product_info_html(), normalize_un(), AnaDbChemicalAdapter, _gercek_karisik_yukleme_kontrolu(), KRİTİK MİMARİ DÜZELTME: Karışık Yükleme artık GERÇEK motoru kullanıyor (+1 more)

### Community 5 - "PgDatabaseManager"
Cohesion: 0.06
Nodes (10): _dogrula(), tasi(), TestSurucuFormuVeGizlilik, TestTabloABozukDurumKurtarma, TestEnvanterImport, TestFaz6MigrasyonVeYedek, TestTabloAKuresel, TestTopluOkuma (+2 more)

### Community 6 - "_ortak.py"
Cohesion: 0.08
Nodes (19): sayfalar/ (Streamlit pages), Düzeltme (3. tur, Umut'un mimari tespiti): DB'ye hiç gidilmemesi gerekiyordu, Özellik: takvim seçici + araç tipi dropdown (Umut'un talebi), araclar_listesi(), db(), firmalar_listesi(), kullanici(), metin_to_tarih() (+11 more)

### Community 7 - "pdf_export.py"
Cohesion: 0.07
Nodes (13): ProjectFileError, _build_styles(), export_results_to_pdf(), _register_fonts(), _results_table(), _summary_table(), load_project(), _result_from_dict() (+5 more)

### Community 9 - "test_webcore_smoke.py"
Cohesion: 0.07
Nodes (13): KRİTİK DÜZELTME: eski sahte uyumsuzluk kontrolü hâlâ arka planda çalışıyordu, _item_nesneleri(), Test1136, TestCompatibilityDedup, TestDatabase, TestEskiSahteUyumsuzlukKontroluTamamenKaldirildi, TestPdfFaz3, TestQRCodeGevsekBagimlilik (+5 more)

### Community 10 - "DriverManagementPage"
Cohesion: 0.08
Nodes (5): DriverEditDialog, DriverManagementPage, _make_countdown_item(), VehicleEditDialog, VehicleManagementPage

### Community 11 - "pathlib"
Cohesion: 0.10
Nodes (8): _hash_password(), db(), qapp(), page(), db(), db(), db(), db()

### Community 12 - "SegregationRuleEngine"
Cohesion: 0.10
Nodes (7): SegregationRuleEngine, SegregationEngine, SegregationVerdict, checker(), db(), make_record(), rule_engine()

### Community 13 - "test_lq_eq.py"
Cohesion: 0.08
Nodes (8): chem(), TestDerivedFlagsAndPersistence, TestEqCodes, TestEqEligibility, TestLqEligibility, TestParseLqLimit, TestRealExcelChemicalImport, TestReportEnforcement

### Community 14 - "adr_csv_importer.py"
Cohesion: 0.11
Nodes (23): auto_import_if_needed(), _clean(), ensure_schema(), _eq(), find_csv_auto(), get_count(), get_db_path(), import_csv_to_db() (+15 more)

### Community 15 - "MixChecker"
Cohesion: 0.07
Nodes (13): MixChecker, MixLoadCheckPage, VariantPickerDialog, adr_mix_pro/ (mixed-load / segregation engine), 1. Karışık Yükleme ana programa taşındı, _SynDB, TestScale, TestSymmetry (+5 more)

### Community 16 - "ADR Transport Pro 2026 — Karışık Yükleme Entegrasyonu"
Cohesion: 0.06
Nodes (35): 2. Excel çıktısı zenginleştirildi, 3. KRİTİK — Eksik LQ/EQ limit denetimi tamamlandı, 4. Tüm testler doğru dosyaya taşındı, 5. main.py ve mix_integration.py projeden SİLİNDİ, ADR Transport Pro 2026 — Karışık Yükleme Entegrasyonu, Ana motor (main.py) — düzeltilen kritik hatalar (v4.0.1), ANA PROGRAM — Antetli Kağıt Filigranı + TASLAK Damgası (v4.3), ANA PROGRAMA TAŞIMA (v4.2 — adr_transport_pro_2026.py) (+27 more)

### Community 18 - "main_window.py"
Cohesion: 0.10
Nodes (6): Advisory, build_advisory(), PairCheckResult, export_results_to_excel(), HelpDialog, load_dark_stylesheet()

### Community 19 - "adr_transport_pro_2026.py"
Cohesion: 0.07
Nodes (7): ADRReport, DocumentStatus, ExemptionType, generate_qr_html(), UserRole, ValidationResult, WarningLevel

### Community 20 - "SecurityManager"
Cohesion: 0.10
Nodes (4): _get_local_ip(), _hash_password(), SecurityManager, _verify_password()

### Community 21 - "test_security_plan_review_report.py"
Cohesion: 0.09
Nodes (8): chem(), TestBulkScreening, TestEmptyClassCodeRobustness, TestInScopeDetection, TestKnownExampleChemicals, TestPackingGroupNormalization, TestRawRowRobustness, TestReportGeneration

### Community 22 - "test_security_plan_review.py"
Cohesion: 0.09
Nodes (8): chem(), TestBulkScreening, TestEmptyClassCodeRobustness, TestInScopeDetection, TestKnownExampleChemicals, TestPackingGroupNormalization, TestRawRowRobustness, TestReportGeneration

### Community 24 - "test_lq_eq_ana_program.py"
Cohesion: 0.10
Nodes (7): chem(), TestDerivedFlagsAndPersistence, TestEqCodes, TestEqEligibility, TestLqEligibility, TestParseLqLimit, TestRealExcelChemicalImport

### Community 26 - "ADR Transport Pro — Web'e Geçiş (Tek Sistem Kararı)"
Cohesion: 0.07
Nodes (29): ADR Transport Pro — Web'e Geçiş (Tek Sistem Kararı), Denetim notu (Faz 4 sırasında, canlı ortam düzeltmesi), Doğrulama: Umut'un 20 senaryolu ADR 2025 karışık yükleme testi, Düzeltme (2. tur): PDF önizlemesi hâlâ sığmıyordu — JS zamanlama sorunu, Düzeltme (2. tur): önceki dataframe çözümü de yanlıştı, Düzeltme (3. tur): önizleme yüksekliği aşırı büyüdü + sağa kayma, Düzeltme (4. tur): dış çerçeve sabit yükseklikte kalıyordu, Düzeltme: 'ADR Belge No' / 'ADR Bitiş' alanları sürücü formundan kaldırıldı (+21 more)

### Community 27 - "item"
Cohesion: 0.11
Nodes (6): item(), TestDriverCertificate, TestExemptionType, TestItemPersistence, TestPointsUseRealCategory, TestTunnelCodes

### Community 29 - "webcore/models.py"
Cohesion: 0.13
Nodes (6): ADRReport, Chemical, DocumentStatus, ExemptionType, ValidationResult, WarningLevel

### Community 30 - "sevkiyat_editor.py"
Cohesion: 0.10
Nodes (11): Düzeltme (2. tur): "1-2 sn donma" hâlâ devam ediyordu — asıl sebep bulundu, _kimyasal_ara(), _kimyasal_ara(), kimyasal_etiket(), _bos_sevkiyat(), _durumu_baslat(), _gg_aa_yyyy_to_date(), _kimyasal_ara() (+3 more)

### Community 32 - "SecurityPlanEngine"
Cohesion: 0.09
Nodes (5): SecurityPlanEngine, _esc(), _row(), _esc(), _row()

### Community 33 - ".execute_update"
Cohesion: 0.09
Nodes (6): TestTabloABosDurumGorunurlugu, db(), TestAuth, TestSetLocalKiraciBaglami, TestTableAImport, TestTenantIsolationRLS

### Community 34 - "._check_explosive_interaction"
Cohesion: 0.11
Nodes (11): CompatibilityVerdict, lookup_compatibility(), check_footnote_a(), check_footnote_b(), check_footnote_c(), check_footnote_d(), FootnoteVerdict, _has_class9_label() (+3 more)

### Community 36 - "item"
Cohesion: 0.13
Nodes (5): item(), TestExemptionType, TestItemPersistence, TestPointsUseRealCategory, TestTunnelCodes

### Community 37 - "test_letterhead_ana_program.py"
Cohesion: 0.10
Nodes (6): app_window(), _extract_watermark_b64(), _sample_logo_b64(), TestLetterheadWatermarkGeneration, TestLetterheadWatermarkPresence, TestLetterheadWatermarkVisualEffect

### Community 38 - "transport_doc.py"
Cohesion: 0.13
Nodes (6): yedekle(), KRİTİK düzeltme: Canlı Önizleme "Gerekli bir kütüphane kurulu değil" hatası, _logo_b64(), TestLetterheadWatermarkGeneration, build_letterhead_watermark_b64(), _ShipmentEditorPageShim

### Community 39 - "wrap_for_screen_preview"
Cohesion: 0.11
Nodes (6): Düzeltme: Canlı Önizleme gerçek PDF çıktısına hiç benzemiyordu, Üç düzeltme: ikinci ürün eklerken donma + PDF önizleme sığmama + karışık yükleme sorgusu, TestEkranOnizlemeSarmalayici, TestOnizlemeGuvenliVarsayilanOlcek, TestOnizlemeJSGercektenGecerli, wrap_for_screen_preview()

### Community 41 - "test_mixload_ana_program.py"
Cohesion: 0.10
Nodes (6): db(), page(), TestAdapterRobustness, TestCheckExecution, TestInputHygiene, TestPageWiring

### Community 42 - "TestVariantSelection"
Cohesion: 0.11
Nodes (6): _accept_variant(), fake_exec(), _cancel_variant(), TestShipmentImport, TestVariantSelection, fail_if_called()

### Community 47 - "TestTarihSeciciVeAracTipiDropdown"
Cohesion: 0.12
Nodes (4): TestTarihSeciciVeAracTipiDropdown, TestEsZamanliOturumIzolasyonu, kendi_baglantisiyla(), Vehicle

### Community 48 - "test_validation.py"
Cohesion: 0.17
Nodes (4): good_item(), TestFlexibleDates, TestPartiesRequired, TestSilentDates

### Community 49 - ".check"
Cohesion: 0.13
Nodes (3): sorted_pair_key(), TestRuleFileIntegrity, TestRuleFileIntegrity

### Community 50 - "LoginDialog"
Cohesion: 0.17
Nodes (3): _get_machine_fingerprint(), LicenseManager, LoginDialog

### Community 52 - "needs"
Cohesion: 0.16
Nodes (3): TestCompanyInventoryImport, TestRealLqEqEngine, TestTableAImport

### Community 53 - "needs"
Cohesion: 0.16
Nodes (3): TestCompanyInventoryImport, TestRealLqEqEngine, TestTableAImport

### Community 55 - "Company"
Cohesion: 0.20
Nodes (4): Company, Driver, load_demo_data(), main()

### Community 60 - "tests/conftest.py"
Cohesion: 0.19
Nodes (5): checker(), db(), make_record(), rule_engine(), SimpleProductDatabase

### Community 63 - "test_approval_ana_program.py"
Cohesion: 0.22
Nodes (4): db(), make_shipment(), TestApprovalDowngrade, TestValidationPersistence

### Community 64 - "test_validation_ana_program.py"
Cohesion: 0.26
Nodes (3): good_item(), TestPartiesRequired, TestSilentDates

### Community 65 - "test_approval.py"
Cohesion: 0.22
Nodes (4): db(), make_shipment(), TestApprovalDowngrade, TestValidationPersistence

### Community 69 - "webcore/ (web engine layer, Qt-free)"
Cohesion: 0.32
Nodes (8): _login_page(), _logout(), main(), webcore/ (web engine layer, Qt-free), Düzeltme: giriş ekranı pasife alındı (Umut'un talebi), KRİTİK GÜVENLİK/KARARLILIK DÜZELTMESİ: paylaşılan global DB bağlantısı, get_auth(), get_db()

### Community 70 - "._tenant_ile_calistir"
Cohesion: 0.18
Nodes (3): Nihai düzeltme: SET LOCAL — pooler moduna bağımlılık tamamen kaldırıldı, TestKendiKendiniOnaranBaglanti, sahte()

### Community 71 - "keepalive.yml"
Cohesion: 0.17
Nodes (11): jobs, ping, name, on, schedule, workflow_dispatch, runs-on, steps (+3 more)

### Community 75 - "logging_setup.py"
Cohesion: 0.25
Nodes (4): ensure_user_data_dir(), get_logger(), setup_logging(), main()

### Community 76 - "score_result"
Cohesion: 0.25
Nodes (3): score_result(), TestRiskScore, TestRiskScore

### Community 84 - "_export"
Cohesion: 0.33
Nodes (3): _export(), _sheet_text(), TestExcelAdrSummary

### Community 88 - "Architecture"
Cohesion: 0.25
Nodes (6): Architecture, Commands, Data sources / seeding, Known intentional desktop/web divergence, Project overview, Working conventions specific to this repo

### Community 97 - "ADR Transport Pro 2026 — Masaüstü Kurulumu"
Cohesion: 0.33
Nodes (5): 1. Python bağımlılıklarını kur, 2. Çalıştır, ADR Transport Pro 2026 — Masaüstü Kurulumu, Bu pakette neler var, Son değişiklik (bu paket)

### Community 104 - "ASUTEK_Kimyasal_İnceleme_Kimyasal_Envanter__ADR_rev1_519ff6f1.md"
Cohesion: 0.40
Nodes (4): Sheet: CAS-H KODLARI, Sheet: Tesis_Genelinde_Kull._ İndi (2), Sheet: Tesis_Genelinde_Kull._ İnditex, Sheet: veri çekmek için

### Community 109 - "Test Paketi — Karışık Yükleme Entegrasyonu"
Cohesion: 0.50
Nodes (3): Dosyalar, Kritik kural, Test Paketi — Karışık Yükleme Entegrasyonu

## Knowledge Gaps
- **61 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DatabaseManager` connect `DatabaseManager` to `Shipment`, `item`, `PgDatabaseManager`, `._row_to_vehicle`, `.execute_one`, `test_webcore_smoke.py`, `.execute`, `._get_conn`, `test_lq_eq.py`, `._row_to_driver`, `.import_company_inventory_excel`, `.execute_insert`, `webcore/models.py`, `sevkiyat_editor.py`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **Are the 24 inferred relationships involving `PgDatabaseManager` (e.g. with `TestEskiKayitEvrakNoBos` and `TestKontrolMerkeziMasaustuEslesme`) actually correct?**
  _`PgDatabaseManager` has 24 INFERRED edges - model-reasoned connections that need verification._
- **Should `SafetyPlansPage` be split into smaller, more focused modules?**
  _Cohesion score 0.05605499735589635 - nodes in this community are weakly interconnected._
- **Why does `DatabaseManager` connect `DatabaseManager` to `SafetyPlansPage`, `Vehicle`, `ShipmentEditorPage`, `DriverManagementPage`, `ShipmentArchivePage`, `Chemical`, `adr_transport_pro_2026.py`, `Company`, `ADRDatabasePage`, `ADRTransportPro`, `._get_conn`, `ADREngine`, `.execute_one`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._
- **Are the 13 inferred relationships involving `ProductRecord` (e.g. with `MixChecker` and `ProductDatabase`) actually correct?**
  _`ProductRecord` has 13 INFERRED edges - model-reasoned connections that need verification._
- **Should `ProductDatabase` be split into smaller, more focused modules?**
  _Cohesion score 0.05807622504537205 - nodes in this community are weakly interconnected._
- **Why does `ShipmentEditorPage` connect `ShipmentEditorPage` to `SafetyPlansPage`, `SecurityPlanEngine`, `adr_transport_pro_2026.py`, `ADRTransportPro`, `._build_print_html`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._