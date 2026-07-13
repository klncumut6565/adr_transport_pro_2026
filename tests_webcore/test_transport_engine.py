"""webcore.ADREngine — mevzuat hesap testleri (Faz 4).

Masaüstü tests/test_transport_engine_ana_program.py'nin webcore karşılığı.
Bu testler, 1.1.3.6 puan hesabı, tünel kısıtı, muafiyet tipi ve sürücü
sertifika kontrolündeki gerçek hataları sabitler. Hepsi düzeltme ÖNCESİ
yazılmıştır (test-first): düzeltmeler bu testleri geçirmek zorundadır.
"""
from datetime import datetime, timedelta

from webcore import (ADREngine, ShipmentItem, Driver, DatabaseManager,
                      Shipment, ExemptionType)


def item(un="1203", cls="3", qty=100.0, tc="2", tunnel="", lq=False, eq=False):
    return ShipmentItem(
        un_number=un, proper_name=f"TEST {un}", class_code=cls,
        net_quantity=qty, transport_category=tc, tunnel_code=tunnel,
        is_lq=lq, is_eq=eq, unit="kg",
    )


# =========================================================================
# BUG-A: 1.1.3.6 puanı maddenin GERÇEK taşıma kategorisini kullanmalı
# (eski kod LQ/EQ dışındaki her şeyi kategori 2 (x3) sayıyordu)
# =========================================================================
class TestPointsUseRealCategory:
    def test_category1_x50(self):
        # Kategori 1: 30 kg x 50 = 1500 > 1000 -> plaka ZORUNLU.
        # Eski kod 30 x 3 = 90 hesaplayıp "gerekmez" diyordu (sahada felaket).
        total, required, _ = ADREngine.calculate_1136_points([item(qty=30, tc="1")])
        assert total == 1500
        assert required is True

    def test_category3_x1(self):
        total, required, _ = ADREngine.calculate_1136_points([item(qty=800, tc="3")])
        assert total == 800
        assert required is False

    def test_category2_x3(self):
        total, _, _ = ADREngine.calculate_1136_points([item(qty=100, tc="2")])
        assert total == 300

    def test_category4_zero_points(self):
        total, required, _ = ADREngine.calculate_1136_points([item(qty=5000, tc="4")])
        assert total == 0
        assert required is False

    def test_category0_no_exemption_possible(self):
        # Kategori 0: miktar ne olursa olsun muafiyet YOK, plaka zorunlu
        total, required, _ = ADREngine.calculate_1136_points([item(qty=0.1, tc="0")])
        assert required is True

    def test_mixed_categories_sum(self):
        items = [item(qty=10, tc="1"), item(un="1830", cls="8", qty=100, tc="2"),
                 item(un="3082", cls="9", qty=100, tc="3")]
        total, required, _ = ADREngine.calculate_1136_points(items)
        assert total == 10 * 50 + 100 * 3 + 100 * 1 == 900
        assert required is False

    def test_lq_eq_exempt_from_points(self):
        items = [item(qty=999, tc="1", lq=True), item(un="1830", qty=999, tc="1", eq=True)]
        total, required, _ = ADREngine.calculate_1136_points(items)
        assert total == 0 and required is False

    def test_unknown_category_conservative(self):
        # Kategori bilinmiyorsa GÜVENLİ taraf: en kısıtlayıcı (x50) varsayılıp
        # mesajda uyarılmalı; asla sessizce düşük çarpan uygulanmamalı.
        total, required, msg = ADREngine.calculate_1136_points([item(qty=100, tc="")])
        assert total >= 100 * 50
        assert required is True
        assert "kategori" in msg.lower()

    def test_boundary_exactly_1000(self):
        total, required, _ = ADREngine.calculate_1136_points([item(qty=1000, tc="3")])
        assert total == 1000 and required is False
        total, required, _ = ADREngine.calculate_1136_points([item(qty=1001, tc="3")])
        assert required is True


# =========================================================================
# BUG-B: Muafiyet tipi — 0 < puan <= 1000 aralığı da 1.1.3.6'dır
# (eski kod sadece puan == 0 iken muafiyet gösteriyordu)
# =========================================================================
class TestExemptionType:
    def test_500_points_is_1136_exempt(self):
        report = ADREngine.generate_adr_report([item(qty=500, tc="3")])
        assert report.exemption_type == ExemptionType.ADR_1_1_3_6.value
        assert report.orange_plate_required is False

    def test_over_limit_no_exemption(self):
        report = ADREngine.generate_adr_report([item(qty=2000, tc="3")])
        assert report.exemption_type == ExemptionType.NONE.value
        assert report.orange_plate_required is True

    def test_all_lq_is_lq_exemption(self):
        report = ADREngine.generate_adr_report([item(lq=True), item(un="1830", lq=True)])
        assert report.exemption_type == ExemptionType.LQ.value


# =========================================================================
# BUG-C: Bileşik tünel kodları ("D/E", "(C/D)") tanınmalı
# (eski kod tek harf dışındakileri yok sayıp "kısıt yok" diyordu)
# =========================================================================
class TestTunnelCodes:
    def test_combined_code_most_restrictive(self):
        assert ADREngine.calculate_tunnel_restriction([item(tunnel="D/E")]) == "D"

    def test_parenthesized(self):
        assert ADREngine.calculate_tunnel_restriction([item(tunnel="(C/D)")]) == "C"

    def test_mixed_items_strictest_wins(self):
        items = [item(tunnel="E"), item(un="1830", tunnel="B/D"), item(un="3082", tunnel="D/E")]
        assert ADREngine.calculate_tunnel_restriction(items) == "B"

    def test_plain_codes_still_work(self):
        assert ADREngine.calculate_tunnel_restriction([item(tunnel="C")]) == "C"
        assert ADREngine.calculate_tunnel_restriction([item(tunnel="")]) == "E"
        assert ADREngine.calculate_tunnel_restriction([]) == "E"


# NOT: "BUG-D: Bozuk sertifika tarihi" testleri (TestDriverCertificate)
# kaldırıldı — sürücü ADR sertifikası alanları (adr_certificate_no/expiry)
# Driver modelinden TAMAMEN silindi (Umut'un talebi: sürücüyle ilgisiz
# alanlardı). Bozuk tarih koruması SRC5 için hâlâ geçerli ve
# test_validation.py'deki TestFlexibleDates ile kapsanıyor.


# =========================================================================
# BUG-E: tunnel_code / transport_category / segregation_group kalıcı olmalı
# (eski şemada bu sütunlar yoktu; arşivden açılan sevkiyat tünel kısıtını
# kaybediyordu)
# =========================================================================
class TestItemPersistence:
    def test_roundtrip_preserves_safety_fields(self, tmp_path):
        db = DatabaseManager(str(tmp_path / "test.db"))
        sh = Shipment(document_no="T-1", document_date="2026-07-05")
        sid = db.add_shipment(sh)
        it = item(qty=42, tc="1", tunnel="D/E")
        it.shipment_id = sid
        it.segregation_group = "Oxidizers"
        db.add_shipment_item(it)

        loaded = db.get_shipment_items(sid)[0]
        assert loaded.transport_category == "1"
        assert loaded.tunnel_code == "D/E"
        assert loaded.segregation_group == "Oxidizers"

    def test_existing_db_migrates(self, tmp_path):
        """Eski şemayla oluşturulmuş adr.db, yeni sürümde açılınca
        ALTER TABLE ile sorunsuz yükseltilmeli."""
        import sqlite3
        p = tmp_path / "eski.db"
        con = sqlite3.connect(p)
        con.execute("""CREATE TABLE shipment_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT, shipment_id INTEGER NOT NULL,
            chemical_id INTEGER, un_number TEXT, proper_name TEXT,
            class_code TEXT, packing_group TEXT, packaging_type TEXT,
            packaging_count INTEGER DEFAULT 1, net_quantity REAL DEFAULT 0,
            gross_quantity REAL DEFAULT 0, unit TEXT DEFAULT 'kg',
            is_lq INTEGER DEFAULT 0, is_eq INTEGER DEFAULT 0,
            lq_max_per_package REAL DEFAULT 0, eq_max_per_package REAL DEFAULT 0,
            notes TEXT)""")
        con.execute("INSERT INTO shipment_items (shipment_id, un_number) VALUES (1, '1203')")
        con.commit(); con.close()

        db = DatabaseManager(str(p))  # migrasyon burada çalışmalı
        loaded = db.get_shipment_items(1)[0]
        assert loaded.un_number == "1203"
        assert loaded.transport_category == ""  # eski kayıt: boş ama ÇÖKME YOK
