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
