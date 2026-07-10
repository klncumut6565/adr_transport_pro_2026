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


@pytest.fixture()
def db(tmp_path):
    return webcore.DatabaseManager(str(tmp_path / "test.db"))


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
            "un_number": "1203", "name": "BENZİN", "adr_class": "3",
            "packing_group": "II", "classification_code": "F1"})
        assert r.get("in_scope") is False

    def test_class1_in_scope(self):
        r = webcore.SecurityPlanEngine.screen_inventory_chemical({
            "un_number": "0081", "name": "PATLAYICI TIP A",
            "adr_class": "1", "packing_group": "",
            "classification_code": "1.1D"})
        assert r.get("in_scope") in (True, "conditional")
