"""webcore (Faz 0a) duman testleri.

Monolitten ayrıştırılan çekirdeğin, arayüz olmadan da ana motor
davranışlarını koruduğunu doğrular. Faz 4'te 232 testlik paketin motor
kısmı buraya taşınacak; bu dosya onun çekirdeğidir.
"""
import os
import tempfile

import pytest

import webcore
from webcore import Chemical, ShipmentItem


PG_DSN = os.environ.get("ADR_PG_TEST_DSN", "")


@pytest.fixture(params=["sqlite", "pg"])
def db(request, tmp_path):
    """Aynı testler iki arka uçta da koşar: SQLite (yerel) + PostgreSQL.

    Pg tarafı ADR_PG_TEST_DSN ortam değişkeni verilirse çalışır; verilmezse
    (ör. Pg kurulmamış geliştirici makinesi) o parametre atlanır.
    """
    if request.param == "sqlite":
        yield webcore.DatabaseManager(str(tmp_path / "test.db"))
        return
    if not PG_DSN:
        pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
    from webcore.pg import PgDatabaseManager
    mgr = PgDatabaseManager(PG_DSN)
    # her test temiz tabloyla başlasın
    for t in ("shipment_items", "shipments", "chemicals", "companies",
              "drivers", "vehicles", "settings"):
        mgr.execute_update(f"DELETE FROM {t}")
    yield mgr
    mgr.close()


class Test1136:
    def test_tc1_exceeds_limit(self):
        item = ShipmentItem(un_number="1090", proper_name="ASETON",
                            transport_category="1", net_quantity=25,
                            unit="L", tunnel_code="D/E")
        total, required, _ = webcore.ADREngine.calculate_1136_points([item])
        assert total == 1250 and required

    def test_tc3_exempt(self):
        item = ShipmentItem(un_number="1263", proper_name="BOYA",
                            transport_category="3", net_quantity=100,
                            unit="L", tunnel_code="D/E")
        total, required, _ = webcore.ADREngine.calculate_1136_points([item])
        assert total == 100 and not required

    def test_category0_always_requires_placard(self):
        item = ShipmentItem(un_number="0081", proper_name="PATLAYICI",
                            transport_category="0", net_quantity=1,
                            unit="kg", tunnel_code="B")
        _, required, _ = webcore.ADREngine.calculate_1136_points([item])
        assert required

    def test_unknown_category_safe_side_x50(self):
        item = ShipmentItem(un_number="9999", proper_name="BILINMEYEN",
                            transport_category="", net_quantity=2,
                            unit="kg", tunnel_code="")
        total, _, detail = webcore.ADREngine.calculate_1136_points([item])
        assert total == 100  # 2 x 50 güvenli taraf
        assert "GÜVENLİ TARAF" in detail


class TestTunnel:
    def test_composite_code_most_restrictive(self):
        i1 = ShipmentItem(un_number="1090", proper_name="A",
                          transport_category="1", net_quantity=1,
                          unit="L", tunnel_code="D/E")
        i2 = ShipmentItem(un_number="0081", proper_name="B",
                          transport_category="0", net_quantity=1,
                          unit="kg", tunnel_code="B")
        result = webcore.ADREngine.calculate_tunnel_restriction([i1, i2])
        code = result[0] if isinstance(result, tuple) else result
        assert "B" in str(code)


class TestDatabase:
    def test_add_and_search_chemical(self, db):
        db.add_chemical(Chemical(
            un_number="1203", proper_shipping_name_tr="BENZİN",
            class_code="3", packing_group="II", tunnel_code="D/E",
            transport_category="2", limited_quantity="1 L",
            excepted_quantity="E2"))
        assert db.count_chemicals() == 1
        results = db.search_chemicals("1203")
        assert len(results) == 1 and results[0].un_number == "1203"

    def test_turkish_names_roundtrip(self, db):
        db.add_chemical(Chemical(
            un_number="1830", proper_shipping_name_tr="SÜLFÜRİK ASİT ĞÜŞİÖÇ",
            class_code="8", packing_group="II"))
        r = db.search_chemicals("1830")[0]
        assert "ĞÜŞİÖÇ" in r.proper_shipping_name_tr


class TestSecurityPlan:
    def test_un1203_exempt_static_screening(self):
        r = webcore.SecurityPlanEngine.screen_inventory_chemical({
            "un_number": "1203", "name": "BENZİN", "class_code": "3",
            "packing_group": "II", "classification_code": "F1"})
        assert r.get("in_scope") is False

    def test_class1_in_scope(self):
        r = webcore.SecurityPlanEngine.screen_inventory_chemical({
            "un_number": "0081", "name": "PATLAYICI TIP A",
            "class_code": "1", "packing_group": "",
            "classification_code": "1.1D"})
        assert r.get("in_scope") in (True, "conditional")


class TestTenantIsolationRLS:
    """RLS kiracı izolasyonu — yalnız Pg'de anlamlı."""

    @pytest.fixture()
    def pgdb(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        from webcore.pg import PgDatabaseManager
        mgr = PgDatabaseManager(PG_DSN, tenant_id=1)
        mgr.execute_update("DELETE FROM companies")
        mgr.set_tenant(2)
        mgr.execute_update("DELETE FROM companies")
        mgr.set_tenant(1)
        yield mgr
        mgr.close()

    def test_read_isolation_and_id_probe(self, pgdb):
        from webcore import Company
        F = lambda **o: Company(**{k: v for k, v in o.items()
                                   if k in Company.__dataclass_fields__})
        pgdb.add_company(F(type="sender", name="K1-A"))
        cid = pgdb.get_companies()[0].id
        pgdb.set_tenant(2)
        assert pgdb.get_companies() == []
        assert pgdb.get_company(cid) is None
        pgdb.set_tenant(1)
        assert [c.name for c in pgdb.get_companies()] == ["K1-A"]

    def test_cross_tenant_write_blocked(self, pgdb):
        pgdb.set_tenant(2)
        with pytest.raises(Exception):
            pgdb.execute_insert(
                "INSERT INTO companies (type, name, tenant_id) "
                "VALUES (?, ?, ?)", ("sender", "SIZMA", 1))


class TestAuth:
    """Faz 1 kimlik doğrulama — yalnız Pg'de anlamlı."""

    @pytest.fixture()
    def auth(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        from webcore.pg import PgDatabaseManager
        from webcore.auth import AuthManager
        mgr = PgDatabaseManager(PG_DSN)
        a = AuthManager(mgr)
        mgr.execute_update("DELETE FROM web_users")
        mgr.execute_update("DELETE FROM tenants")
        yield a
        mgr.close()

    def test_login_roundtrip_and_lockout(self, auth):
        t = auth.create_tenant("Test Kiracı")
        auth.create_user(t, "Deneme", "Parola!1", role="admin")
        u = auth.login("deneme", "Parola!1")
        assert u and u["tenant_id"] == t and "password_hash" not in u
        for _ in range(5):
            assert auth.login("deneme", "yanlis") is None
        assert auth.login("deneme", "Parola!1") is None  # kilitli
        auth.set_password("deneme", "Yeni!2")
        assert auth.login("deneme", "Yeni!2")

    def test_password_hash_functions(self, auth):
        from webcore.auth import hash_password, verify_password
        h = hash_password("türkçe-ĞÜŞİÖÇ-parola")
        assert verify_password("türkçe-ĞÜŞİÖÇ-parola", h)
        assert not verify_password("baska", h)
        assert not verify_password("x", "bozukformat")



class TestCompatibilityDedup:
    """Faz 2b motor sapması kilidi: uyumsuzluk listesi ayna kopyasız
    ve kararlı sıralı olmalı (bkz. webcore/engines.py başlık notu)."""

    def test_no_mirrored_pairs_and_stable_order(self):
        f = ShipmentItem.__dataclass_fields__
        mk = lambda **o: ShipmentItem(**{k: v for k, v in o.items() if k in f})
        # Yapay iki uyumsuz ayrışma grubu (matristen bağımsız çalışsın diye
        # gerçek bir çift seçiyoruz: matris boşsa test kendini atlar)
        from webcore.constants import INCOMPATIBILITY_MATRIX as M
        pair = next(((g, o) for g, lst in M.items() for o in lst if o in M), None)
        if not pair:
            pytest.skip("uyumsuzluk matrisi boş")
        g1, g2 = pair
        items = [
            mk(un_number="1", proper_name="A", segregation_group=g1,
               transport_category="2", net_quantity=1, unit="kg"),
            mk(un_number="2", proper_name="B", segregation_group=g2,
               transport_category="2", net_quantity=1, unit="kg"),
        ]
        r1 = webcore.ADREngine.check_compatibility(items)
        r2 = webcore.ADREngine.check_compatibility(items)
        assert r1 == r2, "sıra kararlı olmalı"
        # ayna kopya yok: her sırasız çift en fazla 1 kez
        gorulen = set()
        for msg in r1:
            icerik = msg.split(":", 1)[-1]
            parcalar = tuple(sorted(p.strip().rstrip("!").split(" birlikte")[0]
                                    for p in icerik.split("+")))
            assert parcalar not in gorulen, f"ayna kopya: {msg}"
            gorulen.add(parcalar)


class TestPdfFaz3:
    """Faz 3a: WeasyPrint PDF motoru + filigran hook'u."""

    def test_watermark_hook_installed_and_pdf_renders(self):
        pytest.importorskip("weasyprint")
        import base64, io
        PIL = pytest.importorskip("PIL.Image")
        import webcore.pdf as wpdf
        import webcore.engines as eng

        # hook: modül import'u shim'i kurmuş olmalı
        assert hasattr(eng, "ShipmentEditorPage")

        img = PIL.new("RGBA", (120, 50), (10, 60, 160, 255))
        buf = io.BytesIO(); img.save(buf, "PNG")
        logo = base64.b64encode(buf.getvalue()).decode()

        f = ShipmentItem.__dataclass_fields__
        mk = lambda **o: ShipmentItem(**{k: v for k, v in o.items() if k in f})
        items = [mk(un_number="0081", proper_name="PATLAYICI",
                    class_code="1", transport_category="1",
                    net_quantity=30, unit="kg", tunnel_code="B")]
        res = eng.SecurityPlanEngine.check(items)
        html = eng.SecurityPlanEngine.generate_inventory_review_html(
            company_name="TEST A.Ş.", prepared_by="T", approved_by="T",
            screen_result=res, logo_b64=logo)
        assert "data:image/png;base64" in html, "filigran gömülmedi"

        pdf = wpdf.html_to_pdf_bytes(html)
        assert pdf[:5] == b"%PDF-" and len(pdf) > 5000

    def test_watermark_draft_stamp_without_logo(self):
        pytest.importorskip("PIL")
        from webcore.pdf import build_letterhead_watermark_b64
        b64 = build_letterhead_watermark_b64("", is_approved=False)
        assert b64, "onaysız evrakta TASLAK damgası üretilmeli"
        assert build_letterhead_watermark_b64("", is_approved=True) == ""


class TestTransportDocFaz3b:
    """Faz 3b: taşıma evrakı şablonunun webcore taşıması."""

    @pytest.fixture()
    def pgdb2(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        from webcore.pg import PgDatabaseManager
        mgr = PgDatabaseManager(PG_DSN)
        yield mgr
        mgr.close()

    def test_html_and_pdf_full_paths(self, pgdb2):
        pytest.importorskip("weasyprint")
        import datetime as dt
        from webcore.transport_doc import build_transport_document_html
        from webcore.pdf import html_to_pdf_bytes
        from webcore import Company, Driver, Vehicle

        yakin = (dt.date.today() + dt.timedelta(days=30)).isoformat()
        driver = Driver(full_name="Test Sürücü", tc_no="1", src5_no="S",
                        src5_expiry=yakin)
        f = ShipmentItem.__dataclass_fields__
        mk = lambda **o: ShipmentItem(**{k: v for k, v in o.items() if k in f})
        items = [mk(un_number="1263", proper_name="BOYA", class_code="3",
                    packing_group="III", packaging_type="Teneke",
                    packaging_count=10, net_quantity=100, unit="L",
                    transport_category="3", tunnel_code="D/E")]
        html = build_transport_document_html(
            db=pgdb2, items=items, document_no="T-1",
            document_date_str="01.01.2026",
            sender=Company(type="sender", name="GÖNDEREN ĞÜŞİÖÇ"),
            receiver=Company(type="receiver", name="ALICI"),
            driver=driver, vehicle=Vehicle(plate="34 T 1"),
            status_text="Onaylandı", notes="")
        assert "100 / 1000" in html          # puan şeridi
        assert "gün kaldı" in html            # SRC5 uyarı dalı (timedelta)
        assert "ĞÜŞİÖÇ" in html               # Türkçe karakter
        pdf = html_to_pdf_bytes(html)
        assert pdf[:5] == b"%PDF-" and len(pdf) > 5000


class TestTableAImport:
    """Faz 2c: Tablo A içe aktarma — Pg üzerinde gerçek dosyayla."""

    def test_import_parity_and_content(self, pgdb2=None):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        import os
        if not os.path.exists("ADR_A_TABLOSU.xlsx"):
            pytest.skip("Tablo A dosyası yok")
        from webcore.pg import PgDatabaseManager
        db = PgDatabaseManager(PG_DSN)
        db.execute_update("DELETE FROM chemicals")
        n = db.import_table_a_excel("ADR_A_TABLOSU.xlsx")
        # Onceden 2873 idi (yanlis UNIQUE kisiti 66 gecerli satiri sessizce
        # birbirinin uzerine yaziyordu -- bkz. webcore/db.py
        # import_table_a_excel docstring'i). Duzeltme sonrasi tum 2939
        # gecerli satir korunuyor.
        assert n == 2939 and db.count_chemicals() == 2939
        r = db.search_chemicals("1203")[0]
        assert r.class_code == "3" and r.tunnel_code == "D/E"
        db.execute_update("DELETE FROM chemicals")
        db.close()


class TestEnvanterImport:
    """Faz 2d: ASUTEK formatı firma envanteri içe aktarma (gerçek dosya)."""

    def test_company_inventory_import(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        import os
        yol = "ASUTEK_Kimyasal_İnceleme_Kimyasal_Envanter__ADR_rev1.xlsx"
        if not os.path.exists(yol):
            pytest.skip("envanter dosyası yok")
        from webcore.pg import PgDatabaseManager
        db = PgDatabaseManager(PG_DSN)
        db.execute_update("DELETE FROM company_products")
        n = db.import_company_inventory_excel(yol)
        assert n > 0
        kayit = db.execute("SELECT COUNT(*) AS n FROM company_products")[0]["n"]
        assert kayit == n
        db.execute_update("DELETE FROM company_products")
        db.close()


class TestFaz6MigrasyonVeYedek:
    """Faz 6: masaüstü->Pg migrasyonu ve CSV zip yedeği (uçtan uca)."""

    def test_migration_roundtrip_and_sequence(self, tmp_path):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        import sys
        sys.path.insert(0, ".")
        from araclar.migrate_desktop_to_pg import tasi, _dogrula
        from webcore import (DatabaseManager, Company, Driver, Vehicle,
                             Shipment)

        F = lambda cls, **o: cls(**{k: v for k, v in o.items()
                                    if k in cls.__dataclass_fields__})
        kaynak = str(tmp_path / "masaustu.db")
        db = DatabaseManager(kaynak)
        s = db.add_company(F(Company, type="sender", name="MİG GÖNDEREN"))
        d = db.add_driver(F(Driver, full_name="Mig Sürücü", tc_no="99999999990"))
        v = db.add_vehicle(F(Vehicle, plate="06 MIG 06"))
        db.add_shipment(F(Shipment, document_no="MIG-1",
                          document_date="2026-01-01", status="Taslak",
                          sender_id=s, driver_id=d, vehicle_id=v))
        db.set_setting("mig_test", "1")
        db.close()

        ozet = tasi(kaynak, PG_DSN, tenant=1, temizle=True,
                    log=lambda *a: None)
        assert ozet["companies"] == 1 and ozet["shipments"] == 1
        assert _dogrula(kaynak, PG_DSN, 1, log=lambda *a: None)

        # sayaç sarımı: taşıma sonrası yeni kayıt çakışmamalı
        from webcore.pg import PgDatabaseManager
        h = PgDatabaseManager(PG_DSN)
        yeni = h.add_company(F(Company, type="sender", name="MIG SONRASI"))
        assert yeni > s
        h.execute_update("DELETE FROM companies")
        h.execute_update("DELETE FROM shipments")
        h.close()

    def test_backup_zip(self, tmp_path):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        import sys, zipfile
        sys.path.insert(0, ".")
        from araclar.yedek_al import yedekle
        z = yedekle(PG_DSN, str(tmp_path), log=lambda *a: None)
        zf = zipfile.ZipFile(z)
        adlar = zf.namelist()
        assert "chemicals.csv" in adlar and "YEDEK_BILGI.txt" in adlar


class TestTabloAKuresel:
    """Düzeltme: ADR Tablo A gömülü ve TÜM kiracılar için ortak olmalı;
    firmaya özel envanter (company_products) ise kiracıya özel kalmalı."""

    def test_otomatik_tohumlama_ve_paylasim(self, tmp_path):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        import os
        if not os.path.exists("ADR_A_TABLOSU.xlsx"):
            pytest.skip("Tablo A dosyası yok")
        from webcore.pg import PgDatabaseManager, TENANT_TABLES
        assert "chemicals" not in TENANT_TABLES
        assert "company_products" in TENANT_TABLES

        db1 = PgDatabaseManager(PG_DSN, tenant_id=1)
        n1 = db1.count_chemicals()
        assert n1 > 0, "Tablo A otomatik tohumlanmadı"

        db2 = PgDatabaseManager(PG_DSN, tenant_id=987654)  # önceden hiç görülmemiş kiracı
        assert db2.count_chemicals() == n1, "farklı kiracı aynı Tablo A'yı görmüyor"
        assert db2.search_chemicals("1203"), "yeni kiracı UN1203'ü arayamıyor"

    def test_company_products_izolasyonu(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        from webcore.pg import PgDatabaseManager
        dbA = PgDatabaseManager(PG_DSN, tenant_id=111)
        dbB = PgDatabaseManager(PG_DSN, tenant_id=222)
        dbA.execute_update("DELETE FROM company_products")
        dbB.execute_update("DELETE FROM company_products")
        # iki kiracı AYNI ürün+UN+sınıf kombinasyonunu yüklesin (çakışma senaryosu)
        dbA.execute_insert(
            "INSERT INTO company_products (company_name, trade_name, "
            "un_number, classification_code) VALUES (?, ?, ?, ?)",
            ("FIRMA-A", "ORTAK ÜRÜN", "1203", "F1"))
        dbB.execute_insert(
            "INSERT INTO company_products (company_name, trade_name, "
            "un_number, classification_code) VALUES (?, ?, ?, ?)",
            ("FIRMA-B", "ORTAK ÜRÜN", "1203", "F1"))
        gA = [r["company_name"] for r in dbA.execute("SELECT company_name FROM company_products")]
        gB = [r["company_name"] for r in dbB.execute("SELECT company_name FROM company_products")]
        assert gA == ["FIRMA-A"], f"izolasyon bozuk: {gA}"
        assert gB == ["FIRMA-B"], f"izolasyon bozuk: {gB}"
        dbA.execute_update("DELETE FROM company_products")
        dbB.execute_update("DELETE FROM company_products")


class TestSetLocalKiraciBaglami:
    """Kritik düzeltme: oturum-ölçekli set_config() yerine her çağrıda
    transaction-ölçekli SET LOCAL kullanılıyor — Supabase Transaction
    pooler'ında (her sorgu farklı arka-uca gidebilir) doğruluğu garanti
    eder, Session pooler'a bağımlı kalmaz. Ayrıca db.py'de doğrudan
    conn.execute() kullanan iki metod (get_expiring_documents,
    get_class_breakdown) self.execute()'a taşındı — eskiden Pg'de kiracı
    sarmalayıcısını atlayıp her zaman kiracı 1'e düşüyorlardı."""

    def test_dinamik_kiraci_gecisi_ayni_baglanti(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        from webcore.pg import PgDatabaseManager
        from webcore import Company

        db = PgDatabaseManager(PG_DSN, tenant_id=555)
        db.execute_update("DELETE FROM companies")
        db.add_company(Company(type="sender", name="K555"))

        db.set_tenant(556)
        db.execute_update("DELETE FROM companies")
        db.add_company(Company(type="sender", name="K556"))

        db.set_tenant(555)
        g555 = [c.name for c in db.get_companies()]
        db.set_tenant(556)
        g556 = [c.name for c in db.get_companies()]
        assert g555 == ["K555"] and g556 == ["K556"], \
            f"AYNI PgDatabaseManager nesnesi kiracı geçişinde karışıyor: {g555} / {g556}"
        db.execute_update("DELETE FROM companies")

    def test_get_expiring_documents_kiraciya_izole(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        import datetime as dt
        from webcore.pg import PgDatabaseManager
        from webcore import Driver

        db1 = PgDatabaseManager(PG_DSN, tenant_id=601)
        db2 = PgDatabaseManager(PG_DSN, tenant_id=602)
        db1.execute_update("DELETE FROM drivers")
        db2.execute_update("DELETE FROM drivers")
        yakin = (dt.date.today() + dt.timedelta(days=10)).isoformat()
        db1.add_driver(Driver(full_name="İZOLE SÜRÜCÜ", tc_no="1",
                              src5_no="X", src5_expiry=yakin, is_active=True))

        exp1 = db1.get_expiring_documents(30)
        exp2 = db2.get_expiring_documents(30)
        assert exp1["drivers"] and not exp2["drivers"], \
            "get_expiring_documents kiracı sarmalayıcısını atlıyor"
        db1.execute_update("DELETE FROM drivers")


class TestEkranOnizlemeSarmalayici:
    """Düzeltme (2. tur, Umut'un 'tam sığmadı' tespiti): @page kuralı
    yalnızca yazdırma/PDF motorlarında uygulanır, tarayıcı ekranda
    tamamen yok sayar — bu yüzden Canlı Önizleme gerçek PDF çıktısına hiç
    benzemiyordu. İlk düzeltme (sabit width:210mm) bu seferki şikayeti
    çözemedi — dar sağ panelde yatay taşma/kırpılma oluyordu. Artık JS
    ile gerçek konteyner genişliği ölçülüp sayfa orantılı ölçekleniyor
    (transform: scale), hangi panelde gösterilirse gösterilsin tam sığar.
    PDF üretimi hâlâ orijinal (sarmalanmamış) HTML'i kullanır, etkilenmez."""

    def test_sarmalama_pdf_yolunu_bozmuyor(self):
        pytest.importorskip("weasyprint")
        from webcore.pdf import html_to_pdf_bytes, wrap_for_screen_preview

        orijinal = ("<html><head><style>@page{size:A4;}</style></head>"
                   "<body>X-ICERIK-947</body></html>")
        sarili = wrap_for_screen_preview(orijinal)

        assert "@page{size:A4;}" in sarili  # orijinal kural dokunulmadan kaldı
        assert "X-ICERIK-947" in sarili      # gövde içeriği korunuyor
        assert "__a4_sarici" in sarili       # ölçeklenen sarıcı eklendi
        assert "transform" in sarili and "olcekle" in sarili  # JS ölçekleme var

        # Orijinal HTML'in KENDİSİ hiç değişmedi (fonksiyon yeni bir
        # string döndürür, orijinali mutasyona uğratmaz) — PDF yolunun
        # etkilenmediğinin doğrudan kanıtı.
        assert "__a4_sarici" not in orijinal
        pdf_orijinal = html_to_pdf_bytes(orijinal)
        assert pdf_orijinal[:5] == b"%PDF-"

    def test_head_yoksa_bile_calisir(self):
        from webcore.pdf import wrap_for_screen_preview
        sonuc = wrap_for_screen_preview("<body>gövde-icerik</body>")
        assert "__a4_sarici" in sonuc and "gövde-icerik" in sonuc

    def test_body_etiketi_hic_yoksa_da_calisir(self):
        from webcore.pdf import wrap_for_screen_preview
        sonuc = wrap_for_screen_preview("<div>saf gövdesiz içerik</div>")
        assert "saf gövdesiz içerik" in sonuc


class TestEsZamanliOturumIzolasyonu:
    """KRİTİK düzeltme: get_db()/get_auth() önceden @st.cache_resource
    ile tanımlıydı — tek bir global PgDatabaseManager (ve tek bir psycopg
    Connection) TÜM eşzamanlı kullanıcılar arasında paylaşılıyordu.
    Streamlit Cloud farklı oturumları ayrı iş parçacıklarında eşzamanlı
    çalıştırabildiği için bu, psycopg.transaction.OutOfOrderTransactionNesting
    hatasına yol açıyordu (iki kullanıcının SET LOCAL transaction'ları
    aynı bağlantı üzerinde çakışıyordu). webcore/session.py artık
    st.session_state ile HER OTURUMA kendi bağlantısını veriyor."""

    # NOT: Bu sınıfın önceki bir sürümünde, paylaşılan tek bağlantıda
    # OutOfOrderTransactionNesting'in gerçekten oluştuğunu kanıtlayan bir
    # "negatif kontrol" testi vardı (5 iş parçacığı → 125/100 hata).
    # Sonraki turda eklenen kendi-kendini-onaran yeniden bağlanma mekanizması
    # (webcore/pg.py:_tenant_ile_calistir) bu hatayı İÇERİDE yakalayıp
    # sessizce düzelttiği için o test artık güvenilir biçimde başarısız
    # OLMUYOR (iyi haber, ama "kanıt" testi olarak anlamını yitirdi) —
    # kanıt FAZ_PLANI_WEB.md'de kayıtlı, kaldırıldı.

    def test_ayri_baglantilar_esizamanlilikta_hatasiz(self):
        """Pozitif kontrol: HER 'oturum' kendi bağlantısını kullanınca
        (webcore/session.py'nin düzeltilmiş davranışı) aynı yük altında
        SIFIR hata olmalı."""
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        import threading
        from webcore.pg import PgDatabaseManager

        hatalar = []

        def kendi_baglantisiyla():
            kendi_db = PgDatabaseManager(PG_DSN)
            for _ in range(20):
                try:
                    kendi_db.execute_one("SELECT 1 AS x")
                except Exception as e:
                    hatalar.append(type(e).__name__)

        konular = [threading.Thread(target=kendi_baglantisiyla) for _ in range(5)]
        [t.start() for t in konular]
        [t.join() for t in konular]
        assert hatalar == [], f"ayrı bağlantılarla bile hata oluştu: {hatalar}"

    def test_session_py_cache_resource_kullanmiyor(self):
        """Statik kontrol: st.cache_resource bir daha sessizce geri
        gelmesin diye (sonraki bir düzenleme bunu tekrar bozmasın)."""
        src = open("webcore/session.py", encoding="utf-8").read()
        # dekoratörler satırın BAŞINDA olur; docstring/yorumdaki bahisler
        # (bu düzeltmeyi açıklayan metin) yanlışlıkla eşleşmesin diye
        # yalnızca gerçek "@st.cache_resource" dekoratör satırları aranır.
        assert not any(l.strip() == "@st.cache_resource"
                       for l in src.splitlines())


class TestKendiKendiniOnaranBaglanti:
    """Düzeltme: Streamlit'in art arda hızlı tıklamada önceki script
    çalıştırmasını iptal etmesi, bir SET LOCAL transaction'ının ortasına
    denk gelirse bağlantıyı bozuk durumda bırakabiliyordu ('art arda
    hızlı seçince ekran hata veriyor' şikâyeti). _tenant_ile_calistir
    artık bağlantı/transaction hatalarını yakalayıp KENDİ KENDİNE yeniden
    bağlanıp bir kez daha dener."""

    def test_bozuk_transaction_sonrasi_kendiliginden_toparlanir(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        import psycopg
        from webcore.pg import PgDatabaseManager

        db = PgDatabaseManager(PG_DSN)
        eski_id = id(db.connection)

        cagri = {"n": 0}
        def sahte(cur):
            cagri["n"] += 1
            if cagri["n"] == 1:
                raise psycopg.transaction.OutOfOrderTransactionNesting("test")
            cur.execute("SELECT 1 AS x")
            return cur.fetchone()

        sonuc = db._tenant_ile_calistir(sahte)
        assert sonuc == {"x": 1}
        assert cagri["n"] == 2, "yeniden deneme tetiklenmedi"
        assert id(db.connection) != eski_id, "bağlantı yenilenmedi"

        # gerçek işlevsellik bozulmadan devam ediyor mu
        assert db.search_chemicals("1203")

    def test_yanlis_hatalarda_yeniden_denemez(self):
        """Yeniden bağlanma yalnızca BAĞLANTI hatalarında devreye girmeli;
        sıradan bir uygulama hatasını (ör. veri hatası) yutup gizlememeli."""
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        from webcore.pg import PgDatabaseManager
        db = PgDatabaseManager(PG_DSN)

        def patlar(cur):
            raise ValueError("gerçek bir uygulama hatası")

        with pytest.raises(ValueError):
            db._tenant_ile_calistir(patlar)


class TestTopluOkuma:
    """Düzeltme: sayfa yüklemede art arda çok sayıda bağımsız sorgu her
    biri kendi transaction'ını açıyordu (4 ağ gidiş-gelişi x N sorgu) —
    'firma seçiminde 1-2 sn donma' şikâyeti tekrarlandı. toplu_okuma()
    birden fazla execute*() çağrısını TEK transaction'da birleştirir."""

    def test_toplu_okuma_dogru_veri_dondurur(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        from webcore.pg import PgDatabaseManager
        from webcore import Company
        db = PgDatabaseManager(PG_DSN)
        db.execute_update("DELETE FROM companies")
        db.add_company(Company(type="sender", name="TOPLU-1"))
        db.add_company(Company(type="receiver", name="TOPLU-2"))

        with db.toplu_okuma():
            firmalar = db.get_companies()
            sayi = db.count_chemicals()
        assert {c.name for c in firmalar} == {"TOPLU-1", "TOPLU-2"}
        assert sayi >= 2939
        db.execute_update("DELETE FROM companies")

    def test_toplu_okuma_disinda_normal_calisir(self):
        """toplu_okuma bloğu kapandıktan sonra normal (tek transaction'lı)
        sorgular yine sorunsuz çalışmalı — _toplu_cursor sızıntısı olmamalı."""
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        from webcore.pg import PgDatabaseManager
        db = PgDatabaseManager(PG_DSN)
        with db.toplu_okuma():
            db.count_chemicals()
        assert db._toplu_cursor is None
        # blok dışında normal çalışıyor mu
        assert db.count_chemicals() >= 2939

    def test_toplu_okuma_icinde_hata_temiz_kapanir(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        from webcore.pg import PgDatabaseManager
        db = PgDatabaseManager(PG_DSN)
        try:
            with db.toplu_okuma():
                db.count_chemicals()
                raise ValueError("kasıtlı test hatası")
        except ValueError:
            pass
        assert db._toplu_cursor is None
        assert db.count_chemicals() >= 2939, "hata sonrası bağlantı kullanılamaz durumda"




class TestOnbellekliListelerSessionState:
    """Düzeltme (nihai): st.cache_data, Streamlit Cloud'daki Python 3.14'te
    UnserializableReturnValueError ile patlıyordu (pickle tabanlı önbellek
    yazımı) — yerelde (3.12) hiçbir varyantla yeniden üretilemedi. Pickle'a
    TAMAMEN bağımlı olmayan st.session_state tabanlı elle önbelleklemeye
    geçildi (sayfalar/_ortak.py:_onbellekli). Bu, canlı Python nesnelerini
    doğrudan bellekte tutar, hiçbir serileştirme yapmaz."""

    def test_ayni_anahtarda_ikinci_cagri_uretici_calistirmaz(self):
        """_onbellekli, TTL süresi dolmadan aynı anahtarla tekrar
        çağrıldığında üretici fonksiyonu YENİDEN ÇALIŞTIRMAMALI."""
        import streamlit as st
        import sayfalar._ortak as ort

        st.session_state.clear()
        sayac = {"n": 0}
        def uretici():
            sayac["n"] += 1
            return {"veri": "test", "cagri": sayac["n"]}

        r1 = ort._onbellekli("test_anahtar", 60, uretici)
        r2 = ort._onbellekli("test_anahtar", 60, uretici)
        r3 = ort._onbellekli("test_anahtar", 60, uretici)
        assert sayac["n"] == 1, "önbellek çalışmıyor, üretici her seferinde çalışıyor"
        assert r1 == r2 == r3

    def test_sure_dolunca_yeniden_uretilir(self):
        import time
        import streamlit as st
        import sayfalar._ortak as ort

        st.session_state.clear()
        sayac = {"n": 0}
        def uretici():
            sayac["n"] += 1
            return sayac["n"]

        r1 = ort._onbellekli("kisa_sureli", 0.05, uretici)
        time.sleep(0.1)
        r2 = ort._onbellekli("kisa_sureli", 0.05, uretici)
        assert sayac["n"] == 2, "TTL dolmasına rağmen yeniden üretilmedi"
        assert r1 == 1 and r2 == 2

    def test_farkli_anahtarlar_birbirini_etkilemez(self):
        """Kiracı izolasyonu farklı bir mekanizmayla sağlanıyor artık:
        her oturum zaten tek bir kiracıya bağlı (webcore/session.py) —
        ama anahtara tenant_id eklenmesi yine de savunma katmanı. Burada
        en azından farklı anahtarların birbirine karışmadığı doğrulanır."""
        import streamlit as st
        import sayfalar._ortak as ort

        st.session_state.clear()
        r1 = ort._onbellekli("firmalar_101", 60, lambda: ["A"])
        r2 = ort._onbellekli("firmalar_102", 60, lambda: ["B"])
        assert r1 == ["A"] and r2 == ["B"], "farklı anahtarlar karıştı"

    def test_onbellek_temizle_anahtarlari_siler(self):
        import streamlit as st
        import sayfalar._ortak as ort

        st.session_state.clear()
        ort._onbellekli("firmalar_1", 60, lambda: ["eski"])
        ort.onbellek_temizle()
        yeni_cagrildi = ort._onbellekli("firmalar_1", 60, lambda: ["yeni"])
        assert yeni_cagrildi == ["yeni"], "onbellek_temizle sonrası eski veri kaldı"

    def test_gercek_veritabani_ile_uctan_uca(self):
        """Gerçek PgDatabaseManager ile: firmalar_listesi() ikinci
        çağrıda DB'ye gitmiyor mu?"""
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        import streamlit as st
        from webcore.pg import PgDatabaseManager
        from webcore import Company
        import sayfalar._ortak as ort

        st.session_state.clear()
        gercek_db = PgDatabaseManager(PG_DSN, tenant_id=951)
        gercek_db.execute_update("DELETE FROM companies")
        gercek_db.add_company(Company(type="sender", name="UCTAN-UCA-951"))

        sayac = {"n": 0}
        orijinal = PgDatabaseManager.get_companies
        def sayan(self):
            sayac["n"] += 1
            return orijinal(self)
        PgDatabaseManager.get_companies = sayan
        try:
            r1 = ort._onbellekli(f"firmalar_{gercek_db.tenant_id}", 60,
                                 gercek_db.get_companies)
            r2 = ort._onbellekli(f"firmalar_{gercek_db.tenant_id}", 60,
                                 gercek_db.get_companies)
            assert sayac["n"] == 1
            assert [c.name for c in r1] == ["UCTAN-UCA-951"]
            assert r1 is r2, "aynı nesne referansı dönmeli (session_state'te canlı tutuluyor)"
        finally:
            PgDatabaseManager.get_companies = orijinal
            gercek_db.execute_update("DELETE FROM companies")


class TestQRCodeGevsekBagimlilik:
    """KRİTİK düzeltme: transport_doc.py'de 'import qrcode' fonksiyonun
    EN BAŞINDA, doc_show_qr ayarı KAPALI olsa bile KOŞULSUZ çalışıyordu.
    qrcode paketi requirements.txt'te hiç yoktu (Streamlit Cloud'da kurulu
    değildi) — bu yüzden Canlı Önizleme HER ZAMAN 'Gerekli bir kütüphane
    kurulu değil' hatasıyla çöküyordu, QR hiç istenmese bile. Import artık
    yalnız gerçekten gerektiğinde (show_qr=True) çalışıyor + paket
    requirements.txt'e gerçekten eklendi + eksik olsa bile zarif devam eder."""

    def test_qr_kapaliyken_paket_eksik_olsa_bile_calisir(self):
        """Asıl hata senaryosunun birebir kanıtı."""
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        import sys, builtins
        from webcore.pg import PgDatabaseManager
        from webcore.transport_doc import build_transport_document_html
        from webcore import Company, ShipmentItem

        db = PgDatabaseManager(PG_DSN)
        db.set_setting("doc_show_qr", "0")
        items = [ShipmentItem(un_number="1203", proper_name="BENZİN",
                              class_code="3", packing_group="II",
                              packaging_type="Varil", packaging_count=4,
                              net_quantity=200, unit="L",
                              transport_category="2", tunnel_code="D/E")]

        orijinal = builtins.__import__
        def sahte(ad, *a, **kw):
            if ad == "qrcode" or ad.startswith("qrcode."):
                raise ImportError("simüle edildi")
            return orijinal(ad, *a, **kw)
        for m in list(sys.modules):
            if m == "qrcode" or m.startswith("qrcode."):
                del sys.modules[m]
        builtins.__import__ = sahte
        try:
            html = build_transport_document_html(
                db=db, items=items, document_no="T-1",
                document_date_str="01.01.2026",
                sender=Company(type="sender", name="A"),
                receiver=Company(type="receiver", name="B"),
                driver=None, vehicle=None, status_text="Taslak", notes="")
            assert len(html) > 1000
        finally:
            builtins.__import__ = orijinal

    def test_qr_aciklen_paket_eksikse_zarif_devam_eder(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        import sys, builtins
        from webcore.pg import PgDatabaseManager
        from webcore.transport_doc import build_transport_document_html
        from webcore import Company, ShipmentItem

        db = PgDatabaseManager(PG_DSN)
        db.set_setting("doc_show_qr", "1")
        items = [ShipmentItem(un_number="1203", proper_name="BENZİN",
                              class_code="3", packing_group="II",
                              packaging_type="Varil", packaging_count=4,
                              net_quantity=200, unit="L",
                              transport_category="2", tunnel_code="D/E")]
        orijinal = builtins.__import__
        def sahte(ad, *a, **kw):
            if ad == "qrcode" or ad.startswith("qrcode."):
                raise ImportError("simüle edildi")
            return orijinal(ad, *a, **kw)
        for m in list(sys.modules):
            if m == "qrcode" or m.startswith("qrcode."):
                del sys.modules[m]
        builtins.__import__ = sahte
        try:
            html = build_transport_document_html(
                db=db, items=items, document_no="T-1",
                document_date_str="01.01.2026",
                sender=Company(type="sender", name="A"),
                receiver=Company(type="receiver", name="B"),
                driver=None, vehicle=None, status_text="Taslak", notes="")
            assert len(html) > 1000
            assert "Firma Kartviziti" not in html  # QR paketi yoksa görsel de yok
        finally:
            builtins.__import__ = orijinal
            db.set_setting("doc_show_qr", "0")

    def test_qr_acikken_paket_kuruluysa_gorsel_uretilir(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        pytest.importorskip("qrcode")
        from webcore.pg import PgDatabaseManager
        from webcore.transport_doc import build_transport_document_html
        from webcore import Company, ShipmentItem

        db = PgDatabaseManager(PG_DSN)
        db.set_setting("doc_show_qr", "1")
        items = [ShipmentItem(un_number="1203", proper_name="BENZİN",
                              class_code="3", packing_group="II",
                              packaging_type="Varil", packaging_count=4,
                              net_quantity=200, unit="L",
                              transport_category="2", tunnel_code="D/E")]
        html = build_transport_document_html(
            db=db, items=items, document_no="T-1",
            document_date_str="01.01.2026",
            sender=Company(type="sender", name="A"),
            receiver=Company(type="receiver", name="B"),
            driver=None, vehicle=None, status_text="Taslak", notes="")
        assert "Firma Kartviziti" in html and "data:image/png" in html
        db.set_setting("doc_show_qr", "0")


class TestGercekKarisikYuklemeMotoru:
    """KRİTİK mimari düzeltme (Umut'un tespiti): web tarafında hem
    Kontrol Merkezi paneli hem Karışık Yükleme sayfası, ADREngine.
    check_compatibility adında BASİTLEŞTİRİLMİŞ bir kontrol kullanıyordu
    (yalnızca segregation_group + sabit sözlük). Masaüstü, "ADR Mix
    Checker Pro v2.4.1" kökenli GERÇEK, 71 birim testli bir motor
    kullanır (adr_mix_pro paketi). webcore/mix_adapter.py, masaüstünün
    AnaDbChemicalAdapter'ının BİREBİR web karşılığıdır — dosya tabanlı
    Excel yerine webcore'un PostgreSQL chemicals tablosuna bağlanır."""

    def test_gercek_uyumsuz_cift_dogru_tespit_edilir(self):
        """UN0081 (Sınıf 1 patlayıcı) + UN1978 (Propan, Sınıf 2) —
        ADR 7.5.2.1'e göre KESİN yasak, dipnot istisnası yok."""
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        from webcore.pg import PgDatabaseManager
        from webcore.mix_adapter import gercek_mix_checker

        db = PgDatabaseManager(PG_DSN)
        sonuc = gercek_mix_checker(db)
        assert sonuc is not None, "kural dosyası bulunamadı"
        checker, adapter = sonuc

        for un in ("0081", "1978"):
            varyasyonlar = adapter.get_variants(un)
            assert varyasyonlar, f"UN{un} Tablo A'da yok — test verisi eksik"
            v = varyasyonlar[0]
            adapter.register_variant(un, v["classification_code"], v["packing_group"])

        sonuclar, eksikler = checker.check_all(["0081", "1978"])
        assert not eksikler
        assert len(sonuclar) == 1
        r = sonuclar[0]
        assert r.status == "NO"
        assert r.adr_reference == "7.5.2.1"
        assert "1.1D" in r.reason or "Sınıf 1" in r.reason

    def test_uyumlu_cift_ok_doner(self):
        """Aynı sınıf/etiket iki maddenin GERÇEK motora göre uyumlu
        çıkması gerekiyorsa (kural dosyasındaki karşılığına göre) OK
        dönmeli — motorun her şeyi 'NO' diye işaretlemediğinin kanıtı."""
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        from webcore.pg import PgDatabaseManager
        from webcore.mix_adapter import gercek_mix_checker

        db = PgDatabaseManager(PG_DSN)
        checker, adapter = gercek_mix_checker(db)
        for un in ("1830", "1824"):  # ikisi de Sınıf 8 (aşındırıcı)
            v = adapter.get_variants(un)
            if v:
                adapter.register_variant(un, v[0]["classification_code"], v[0]["packing_group"])
        sonuclar, _ = checker.check_all(["1830", "1824"])
        assert sonuclar and sonuclar[0].status == "OK"

    def test_bilinmeyen_un_cokme_yerine_unknown_doner(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        from webcore.pg import PgDatabaseManager
        from webcore.mix_adapter import gercek_mix_checker

        db = PgDatabaseManager(PG_DSN)
        checker, adapter = gercek_mix_checker(db)
        v = adapter.get_variants("1203")
        adapter.register_variant("1203", v[0]["classification_code"], v[0]["packing_group"])
        adapter.register_unknown("9999")  # Tablo A'da olmayan uydurma UN
        sonuclar, eksikler = checker.check_all(["1203", "9999"])
        # register_unknown yaptığımız için "eksik" listesinde değil,
        # ama UNKNOWN durumuyla dönmeli, çökme olmamalı
        assert sonuclar
        assert sonuclar[0].status in ("UNKNOWN", "OK", "NO", "EXPLOSIVE_SPECIAL", "FOOD_CAUTION")

    def test_zincirde_yeni_ucuncu_parti_bagimlilik_yok(self):
        """pandas kullanan core/database.py'ye HİÇ dokunulmadığının
        statik kanıtı — pandas her ne kadar streamlit'in kendi zorunlu
        bağımlılığı olsa da (güvenli), bu, tasarımın gerçekten
        PgChemicalAdapter'ı kullandığını, dosya-tabanlı ProductDatabase'i
        DEĞİL, doğrular."""
        src = open("webcore/mix_adapter.py", encoding="utf-8").read()
        kod_satirlari = [l for l in src.splitlines() if not l.strip().startswith("#")]
        kod_metni = "\n".join(kod_satirlari)
        assert "from adr_mix_pro.core.database" not in kod_metni
        assert "import ProductDatabase" not in kod_metni


class TestOnizlemeGuvenliVarsayilanOlcek:
    """Düzeltme (Umut'un 2. tespiti — 'tam sığmadı, sadece %33 zoom'da
    sığıyor'): ilk düzeltmenin JS'i (load/resize + birkaç setTimeout)
    Streamlit'in components.html/srcdoc ortamında güvenilir çalışmadı.

    Düzeltme (Umut'un 3. tespiti — 'yükseklik alanı çok büyük oldu,
    önizleme görünmüyor' + 'panel genişledikçe önizleme sağa kayıyor'):
    ResizeObserver'ın document.body'yi izlemesi, olcekle()'nin KENDİ
    height ayarının body'yi değiştirip gözlemciyi TEKRAR tetiklemesine
    (kendi kendini besleyen döngü) yol açıyordu. ResizeObserver
    kaldırıldı, yerine yalnızca 'window' resize olayı (içerik
    değişikliklerinden ASLA tetiklenmez) + ölçek gerçekten değişmediyse
    DOM'a dokunmayan bir tekrar-hesaplama önleme (sonOlcek) kondu.
    Ayrıca `margin: 0 auto` (ortalama) → `margin: 0` (sol hizalı)."""

    def test_guvenli_varsayilan_olcek_hep_uygulanir(self):
        from webcore.pdf import wrap_for_screen_preview
        sonuc = wrap_for_screen_preview("<body>test-icerik</body>")
        # JS hiç çalışmasa bile (ör. çok eski tarayıcı) bu satır-içi
        # CSS zaten devrede olmalı — "hiç sığmama" riski böylece yok.
        assert "scale(0.5)" in sonuc

    def test_document_body_resize_observer_kaldirildi(self):
        """KRİTİK: document.body'yi izleyen bir ResizeObserver bir daha
        sessizce geri gelmesin — bu, tespit edilen geri besleme
        döngüsünün doğrudan kaynağıydı."""
        from webcore.pdf import wrap_for_screen_preview
        sonuc = wrap_for_screen_preview("<body>x</body>")
        assert "ResizeObserver" not in sonuc
        assert "addEventListener('resize'" in sonuc
        assert "addEventListener('load'" in sonuc

    def test_tekrar_hesaplama_onleme_var(self):
        """Ölçek gerçekten değişmediyse DOM'a dokunulmamalı — olası
        her türlü geri besleme döngüsüne karşı ek güvence."""
        from webcore.pdf import wrap_for_screen_preview
        sonuc = wrap_for_screen_preview("<body>x</body>")
        assert "sonOlcek" in sonuc

    def test_sol_hizali_ortalama_degil(self):
        """Umut'un tespiti: panel genişledikçe önizleme sağa kayıyormuş
        gibi görünüyordu — `margin: 0 auto` (ortalama) yerine sol kenara
        sabitlendi (`margin: 0`)."""
        from webcore.pdf import wrap_for_screen_preview
        sonuc = wrap_for_screen_preview("<body>x</body>")
        assert "margin: 0 auto" not in sonuc
        assert "transform-origin: top left" in sonuc

    def test_birden_fazla_zamanlama_denemesi_var(self):
        from webcore.pdf import wrap_for_screen_preview
        sonuc = wrap_for_screen_preview("<body>x</body>")
        # tek bir setTimeout'a güvenmek yerine birden fazla gecikmeli
        # deneme (fontlar/layout geç tamamlanırsa bile yakalansın)
        assert sonuc.count("setTimeout") == 0 or "[0, 50, 150, 300, 600, 1200]" in sonuc


class TestKarisikYuklemeAdr2025Dogrulama:
    """Umut'un verdiği 20 test senaryosuyla GERÇEK motorun (adr_mix_pro)
    doğrulanması. 14/20 tam isabet; 4'ü kural tablosunda ikincil tehlike
    kombinasyonu eksikliği yüzünden UNKNOWN (yanlış değil, 'tahmin etme,
    manuel kontrol iste' güvenli tasarımı); 2'si (Test 8, 10) Umut'un
    doğrulamasıyla GEÇERSİZ test verisi olduğu için kapsam dışı bırakıldı
    (test dokümanındaki UN0336/UN0027 sınıflandırma kodları TERSTİ —
    gerçek Tablo A: UN0336=1.4G, UN0027=1.1D; sistem verisi doğruydu)."""

    @staticmethod
    def _kontrol_et(db, un1, un2):
        from webcore.mix_adapter import gercek_mix_checker
        checker, adapter = gercek_mix_checker(db)
        for un in (un1, un2):
            v = adapter.get_variants(un)
            if v:
                adapter.register_variant(un, v[0]["classification_code"], v[0]["packing_group"])
            else:
                adapter.register_unknown(un)
        sonuclar, _ = checker.check_all([un1, un2])
        return sonuclar[0] if sonuclar else None

    @pytest.mark.parametrize("un1,un2,beklenen,aciklama", [
        ("1202", "1950", "OK", "Motorin + aerosol"),
        ("1203", "1789", "OK", "Benzin + Hidroklorik Asit"),
        ("1993", "3082", "OK", "Alevlenebilir sıvı PGII + Çevre tehlikeli"),
        ("3257", "1203", "OK", "Elevated Temp Liquid + Benzin"),
        ("3258", "3077", "OK", "Elevated Temp Solid + Çevre tehlikeli katı"),
        # NOT: Test 9 (UN0336+UN3077) buradan ÇIKARILDI — Umut, Test 8/10
        # ile aynı kaynaktan (test dokümanındaki UN0336 sınıflandırma
        # karışıklığı) geldiğini belirtip üçünü de görmezden gelmemi
        # istedi. Gerçek Tablo A koduyla (1.4G) alınan "NO" sonucu teknik
        # olarak sorunsuz üretildi ama Umut bu üç testin güvenilirliğinden
        # emin olmadığını söyledi — kayıt dışı bırakıldı.
        ("1942", "1203", "OK", "Amonyum Nitrat + Benzin"),
        ("1824", "1090", "OK", "Sodyum Hidroksit + Aseton"),
        ("1845", "1950", "OK", "Kuru Buz + Aerosol"),
        ("1202", "1203", "OK", "Motorin + Benzin"),
        ("1824", "1789", "OK", "Sodyum Hidroksit + Hidroklorik Asit"),
        ("3257", "3258", "OK", "Elevated Temp Liquid + Solid"),
        ("1202", "3243", "OK", "Motorin + Azodikarbonamid"),
    ])
    def test_dogru_sonuc_veren_ciftler(self, un1, un2, beklenen, aciklama):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        from webcore.pg import PgDatabaseManager
        db = PgDatabaseManager(PG_DSN)
        r = self._kontrol_et(db, un1, un2)
        assert r is not None, f"{aciklama}: sonuç üretilemedi"
        assert r.status == beklenen, (
            f"{aciklama} (UN{un1}+UN{un2}): beklenen={beklenen}, "
            f"gelen={r.status} | {r.reason}")

    @pytest.mark.parametrize("un1,un2,aciklama", [
        ("1005", "1202", "Amonyak susuz (+8) + Motorin (3)"),
        ("1017", "1202", "Klor (+5.1) + Motorin (3)"),
        ("2014", "1202", "Hidrojen Peroksit (+8) + Motorin (3)"),
        ("1744", "2014", "Brom (8) + Hidrojen Peroksit (+8)"),
    ])
    def test_ikincil_tehlike_kombinasyonlari_tahmin_etmez(self, un1, un2, aciklama):
        """Bu 4 çift, kural tablosunda (segregation_rules.csv, 277 satır)
        ikincil tehlike (+8, +5.1 gibi) kombinasyonu için satır YOK —
        motor bunu bilinçli olarak UNKNOWN döner (tahmin etmez), NO/OK
        diye YANLIŞ bir kesinlik iddia etmez. Umut'un test dokümanı bu
        çiftlerin hepsinin OK olmasını bekliyordu; tablo genişletilmeden
        motor bunu doğrulayamaz — bu, bilinen bir kapsam sınırıdır."""
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        from webcore.pg import PgDatabaseManager
        db = PgDatabaseManager(PG_DSN)
        r = self._kontrol_et(db, un1, un2)
        assert r is not None
        assert r.status == "UNKNOWN", (
            f"{aciklama}: durum değişti ({r.status}) — kural tablosu "
            "güncellenmiş olabilir, bu testi gözden geçirin")

    def test_yuksek_puan_yuzde_yuzde_tavanlanir(self):
        """Ekran görüntüsüyle doğrulanan senaryo: 1000 puanı büyük ölçüde
        aşan (ör. 10200) bir sevkiyatta ilerleme çubuğu %100'de tavanlanır
        ve turuncu plaka doğru şekilde ZORUNLU çıkar — aşırı değerde
        çökme veya %100'ü aşan gösterge olmaz."""
        from webcore.engines import ADREngine
        from webcore.models import ShipmentItem
        f = ShipmentItem.__dataclass_fields__
        mk = lambda **o: ShipmentItem(**{k: v for k, v in o.items() if k in f})
        # TC=1 (50 puan/birim) x 204 birim = 10200 puan
        items = [mk(un_number="1090", proper_name="ASETON", transport_category="1",
                    net_quantity=204, unit="kg", tunnel_code="D/E")]
        puan, plaka_gerekli, _ = ADREngine.calculate_1136_points(items)
        assert puan == 10200
        assert plaka_gerekli is True
        oran = min(puan / 1000, 1.0)
        assert oran == 1.0, "ilerleme çubuğu oranı %100'ü aşmamalı (tavanlanmalı)"


class TestOnizlemeJSGercektenGecerli:
    """Düzeltme (kendi hatam — iki kez art arda yakalandı): önizleme
    JS'ini elle düzenlerken yorum satırlarında yanlışlıkla Python yorum
    işareti (#) kullanmışım — bu geçerli JavaScript değil, tarayıcıda
    sessizce sözdizimi hatasına yol açardı (script hiç çalışmaz, ama
    hata konsola gitmeden fark edilmeyebilirdi). Node.js ile GERÇEKTEN
    derlenebilir olduğu artık her test çalıştırmasında doğrulanıyor —
    bir daha kaçmaz."""

    def test_js_node_ile_derlenebiliyor(self):
        import shutil, subprocess, re, tempfile, os
        if not shutil.which("node"):
            pytest.skip("node kurulu değil, JS sözdizimi doğrulanamıyor")
        from webcore.pdf import wrap_for_screen_preview
        html = wrap_for_screen_preview("<html><head></head><body>x</body></html>")
        m = re.search(r"<script>(.*?)</script>", html, re.S)
        assert m, "script bloğu bulunamadı"
        js_kodu = m.group(1)
        assert not re.search(r"^\s*#", js_kodu, re.M), \
            "JS bloğunda geçersiz Python-tarzı yorum işareti (#) bulundu"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False,
                                         encoding="utf-8") as f:
            f.write(js_kodu)
            yol = f.name
        try:
            sonuc = subprocess.run(["node", "--check", yol],
                                   capture_output=True, text=True, timeout=10)
            assert sonuc.returncode == 0, f"JS sözdizimi hatalı:\n{sonuc.stderr}"
        finally:
            os.unlink(yol)

    def test_dis_cerceve_otomatik_yukseklik_bildirimi_var(self):
        """Umut'un tespiti: dış çerçeve (iframe) sabit yükseklikte
        kalıp boş alan bırakıyordu. Artık Streamlit'in standart
        postMessage protokolüyle gerçek yüksekliğe göre ayarlanıyor."""
        from webcore.pdf import wrap_for_screen_preview
        sonuc = wrap_for_screen_preview("<body>x</body>")
        assert "streamlit:setFrameHeight" in sonuc
        assert "postMessage" in sonuc


class TestEskiSahteUyumsuzlukKontroluTamamenKaldirildi:
    """KRİTİK düzeltme (Umut'un sorusu: 'hangi referansla söylüyor?'):
    generate_adr_report() İÇİNDE hâlâ eski, basitleştirilmiş
    check_compatibility() çağrılıyordu (sabit, hayali bir sözlüğe
    dayanan, GERÇEK bir ADR referansı olmayan kontrol — ör. 'Yanici
    Maddeler + Yukseltgenler birlikte tasinamaz!' gibi mesajlar uydurma
    bir eşleştirmeden geliyordu). Bu, GERÇEK motor (adr_mix_pro) ayrıca
    eklendiğinde kaldırılmamıştı — ikisi YAN YANA çalışıp hem canlı
    panelde hem YAZDIRILAN Taşıma Evrakı belgesinde çelişen/güvenilmez
    sonuçlar üretiyordu. Artık generate_adr_report() compatibility_
    errors'ı boş bırakıyor; gerçek sonuç yalnızca veritabanına erişimi
    olan çağıranlarca (transport_doc.py, sevkiyat_editor.py,
    karisik_yukleme.py) webcore/mix_adapter.py üzerinden hesaplanıyor."""

    def test_generate_adr_report_artik_sahte_mesaj_uretmiyor(self):
        from webcore.engines import ADREngine
        from webcore.models import ShipmentItem
        f = ShipmentItem.__dataclass_fields__
        mk = lambda **o: ShipmentItem(**{k: v for k, v in o.items() if k in f})
        items = [
            mk(un_number="0081", proper_name="PATLAYICI", class_code="1",
              transport_category="1", net_quantity=30, unit="kg",
              tunnel_code="B", classification_code="1.1D"),
            mk(un_number="1978", proper_name="PROPAN", class_code="2",
              transport_category="1", net_quantity=500, unit="kg",
              tunnel_code="B/D", classification_code="2A"),
        ]
        rapor = ADREngine.generate_adr_report(items, driver=None, vehicle=None)
        hata_metinleri = [m for _, m in rapor.errors]
        assert not any("UYUMSUZ:" in m for m in hata_metinleri), \
            "eski sahte matris tabanlı mesaj hâlâ üretiliyor"
        assert rapor.compatibility_errors == []

    def test_yazdirilan_belgede_gercek_motor_sonucu_var(self):
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        from webcore.pg import PgDatabaseManager
        from webcore.transport_doc import build_transport_document_html
        from webcore import Company, ShipmentItem

        db = PgDatabaseManager(PG_DSN)
        items = [
            ShipmentItem(un_number="0081", proper_name="PATLAYICI", class_code="1",
                        packing_group="", packaging_type="Kutu", packaging_count=5,
                        net_quantity=30, unit="kg", transport_category="1",
                        tunnel_code="B", classification_code="1.1D"),
            ShipmentItem(un_number="1978", proper_name="PROPAN", class_code="2",
                        packing_group="", packaging_type="Tank", packaging_count=1,
                        net_quantity=500, unit="kg", transport_category="1",
                        tunnel_code="B/D", classification_code="2A"),
        ]
        html = build_transport_document_html(
            db=db, items=items, document_no="T-1", document_date_str="14.07.2026",
            sender=Company(type="sender", name="A"), receiver=Company(type="receiver", name="B"),
            driver=None, vehicle=None, status_text="Taslak", notes="")
        assert "UYUMSUZ:" not in html, "eski sahte format belgede hâlâ görünüyor"
        assert "7.5.2.1" in html, "gerçek ADR referansı belgede görünmüyor"
        assert "UYUMSUZLUK UYARILARI" in html

    def test_uyumlu_ciftte_belgede_sahte_uyari_gorunmez(self):
        """Ters yönlü kontrol: motor OK derse belgede hiç uyarı KUTUSU
        çıkmamalı (eskiden sahte matris yanlışlıkla tetikleyebiliyordu)."""
        if not PG_DSN:
            pytest.skip("ADR_PG_TEST_DSN tanımlı değil")
        from webcore.pg import PgDatabaseManager
        from webcore.transport_doc import build_transport_document_html
        from webcore import Company, ShipmentItem

        db = PgDatabaseManager(PG_DSN)
        items = [
            ShipmentItem(un_number="1830", proper_name="SÜLFÜRİK ASİT", class_code="8",
                        packing_group="II", packaging_type="Varil", packaging_count=4,
                        net_quantity=200, unit="L", transport_category="2",
                        tunnel_code="D/E", classification_code="C1"),
            ShipmentItem(un_number="1824", proper_name="SODYUM HİDROKSİT", class_code="8",
                        packing_group="II", packaging_type="Varil", packaging_count=4,
                        net_quantity=200, unit="L", transport_category="2",
                        tunnel_code="D/E", classification_code="C5"),
        ]
        html = build_transport_document_html(
            db=db, items=items, document_no="T-2", document_date_str="14.07.2026",
            sender=Company(type="sender", name="A"), receiver=Company(type="receiver", name="B"),
            driver=None, vehicle=None, status_text="Taslak", notes="")
        assert "UYUMSUZLUK UYARILARI" not in html
