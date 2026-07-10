"""Sınırlı Miktar (LQ, ADR 3.4) ve İstisnai Miktar (EQ, ADR 3.5) testleri.

Sorunun kaynağı: Tablo A / firma Excel'inde LQ "1 L" gibi miktar, EQ ise
E0–E5 kodu olarak gelirken, sistemin iç kaydı bunları miktardan bağımsız
evet/hayır'a indirgiyordu. Bu testler profesyonel davranışı tanımlar:

  * LQ: maddeye özgü limit metni ("1 L", "5 kg", "0") saklanır ve iç ambalaj
    başına miktar bu limitle karşılaştırılır.
  * EQ: E-kodu saklanır; ADR 3.5.1.2 tablosuna göre iç/dış ambalaj limitleri
    koddan türetilir (E0 = taşınamaz).
  * Evet/hayır alanları artık türetilmiş bilgidir, veri kaynağı değildir.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "anaprog", str(ROOT / "adr_transport_pro_2026.py"))
M = importlib.util.module_from_spec(_spec)
sys.modules["anaprog"] = M
_spec.loader.exec_module(M)


def chem(lq="", eq="", cls="3", **kw):
    return M.Chemical(un_number="1203", proper_shipping_name_tr="TEST",
                      class_code=cls, limited_quantity=lq,
                      excepted_quantity=eq, **kw)


# =========================================================================
# LQ limit metni ayrıştırma — Excel'den her biçimde gelebilir
# =========================================================================
class TestParseLqLimit:
    @pytest.mark.parametrize("text,value,unit", [
        ("1 L", 1.0, "L"),
        ("5 kg", 5.0, "kg"),
        ("1L", 1.0, "L"),
        ("500 ml", 0.5, "L"),
        ("500 g", 0.5, "kg"),
        ("0,5 L", 0.5, "L"),      # Avrupa ondalık
        ("5 L / 1 kg", 5.0, "L"), # bileşik: ilk değer esas
    ])
    def test_valid(self, text, value, unit):
        v, u = M.ADREngine.parse_lq_limit(text)
        assert v == pytest.approx(value) and u == unit

    @pytest.mark.parametrize("text", ["0", "", "  ", None, "nan", "-", "YOK"])
    def test_not_allowed(self, text):
        v, _ = M.ADREngine.parse_lq_limit(text)
        assert v == 0.0


# =========================================================================
# EQ kodları — ADR 3.5.1.2 tablosu
# =========================================================================
class TestEqCodes:
    @pytest.mark.parametrize("code,inner,outer", [
        ("E1", 30, 1000), ("E2", 30, 500), ("E3", 30, 300),
        ("E4", 1, 500), ("E5", 1, 300),
    ])
    def test_limits(self, code, inner, outer):
        i, o = M.ADREngine.eq_limits(code)
        assert (i, o) == (inner, outer)

    @pytest.mark.parametrize("code", ["E0", "", None, "nan", "X9", "e0"])
    def test_not_allowed(self, code):
        i, o = M.ADREngine.eq_limits(code)
        assert (i, o) == (0, 0)

    def test_lowercase_and_spaces_tolerated(self):
        assert M.ADREngine.eq_limits(" e2 ") == (30, 500)


# =========================================================================
# LQ uygunluk kontrolü: sınıf tablosu DEĞİL, maddenin kendi limiti
# =========================================================================
class TestLqEligibility:
    def test_within_limit(self):
        ok, msg, mx = M.ADREngine.check_lq_eligibility(chem(lq="1 L"), 0.9, "L")
        assert ok and mx == 1.0 and "1" in msg

    def test_over_limit(self):
        ok, msg, mx = M.ADREngine.check_lq_eligibility(chem(lq="1 L"), 1.5, "L")
        assert not ok and mx == 1.0

    def test_zero_means_forbidden(self):
        ok, _, mx = M.ADREngine.check_lq_eligibility(chem(lq="0"), 0.1, "L")
        assert not ok and mx == 0.0

    def test_boundary_exact(self):
        ok, _, _ = M.ADREngine.check_lq_eligibility(chem(lq="5 kg"), 5.0, "kg")
        assert ok

    def test_unit_mismatch_flagged(self):
        # Limit litre, giriş kg: sessizce karşılaştırılamaz — uyarı içermeli
        ok, msg, _ = M.ADREngine.check_lq_eligibility(chem(lq="1 L"), 0.5, "kg")
        assert "birim" in msg.lower()

    def test_per_substance_not_per_class(self):
        # Aynı sınıf (3), farklı limitler: her madde KENDİ limitiyle denetlenmeli
        ok1, _, mx1 = M.ADREngine.check_lq_eligibility(chem(lq="1 L", cls="3"), 2.0, "L")
        ok2, _, mx2 = M.ADREngine.check_lq_eligibility(chem(lq="5 L", cls="3"), 2.0, "L")
        assert not ok1 and ok2 and (mx1, mx2) == (1.0, 5.0)


# =========================================================================
# EQ uygunluk kontrolü: kod bazlı, g/ml cinsinden iç ambalaj limiti
# =========================================================================
class TestEqEligibility:
    def test_e2_within(self):
        ok, msg, mx = M.ADREngine.check_eq_eligibility(chem(eq="E2"), 25)
        assert ok and mx == 30 and "E2" in msg

    def test_e2_over(self):
        ok, _, _ = M.ADREngine.check_eq_eligibility(chem(eq="E2"), 31)
        assert not ok

    def test_e0_forbidden(self):
        ok, msg, mx = M.ADREngine.check_eq_eligibility(chem(eq="E0"), 0.5)
        assert not ok and mx == 0 and "E0" in msg

    def test_e5_tight_limit(self):
        ok, _, _ = M.ADREngine.check_eq_eligibility(chem(eq="E5"), 1)
        assert ok
        ok, _, _ = M.ADREngine.check_eq_eligibility(chem(eq="E5"), 2)
        assert not ok


# =========================================================================
# Türetilmiş evet/hayır geriye dönük uyum + kalıcılık
# =========================================================================
class TestDerivedFlagsAndPersistence:
    def test_flags_derived_from_limits(self):
        c = chem(lq="1 L", eq="E2")
        assert M.ADREngine.is_lq_allowed(c) is True
        assert M.ADREngine.is_eq_allowed(c) is True
        c2 = chem(lq="0", eq="E0")
        assert M.ADREngine.is_lq_allowed(c2) is False
        assert M.ADREngine.is_eq_allowed(c2) is False

    def test_legacy_boolean_respected_when_no_limit_text(self):
        # Eski kayıtlar: limit metni yok ama boolean var — kaybolmamalı
        c = M.Chemical(un_number="1789", class_code="8", lq_allowed=True)
        assert M.ADREngine.is_lq_allowed(c) is True

    def test_chemical_roundtrip_with_limits(self, tmp_path):
        db = M.DatabaseManager(str(tmp_path / "t.db"))
        cid = db.add_chemical(chem(lq="1 L", eq="E2"))
        loaded = db.get_chemical(cid)
        assert loaded.limited_quantity == "1 L"
        assert loaded.excepted_quantity == "E2"

    def test_old_db_migrates(self, tmp_path):
        import sqlite3
        p = tmp_path / "eski.db"
        con = sqlite3.connect(p)
        con.execute("""CREATE TABLE chemicals (
            id INTEGER PRIMARY KEY AUTOINCREMENT, un_number TEXT NOT NULL UNIQUE,
            proper_shipping_name_tr TEXT, proper_shipping_name_en TEXT,
            class_code TEXT, packing_group TEXT, tunnel_code TEXT,
            transport_category TEXT, segregation_group TEXT, special_provisions TEXT,
            lq_allowed INTEGER DEFAULT 0, eq_allowed INTEGER DEFAULT 0,
            hazard_labels TEXT, flash_point REAL)""")
        con.execute("INSERT INTO chemicals (un_number, class_code, lq_allowed) VALUES ('1203','3',1)")
        con.commit(); con.close()

        db = M.DatabaseManager(str(p))
        c = db.search_chemicals("1203")[0]
        assert c.limited_quantity == "" and c.lq_allowed is True


# =========================================================================
# adr_database.json -> chemicals aktarımı limitleri taşımalı
# (üç veri kaynağının birleşme noktası)
# =========================================================================
class TestRealExcelChemicalImport:
    """Ana programda JSON değil, gerçek ADR Tablo A Excel'i içe aktarılır."""

    def test_import_carries_lq_eq(self, tmp_path):
        table_a = ROOT / "ADR_A_TABLOSU.xlsx"
        if not table_a.exists():
            pytest.skip("Gerçek ADR_A_TABLOSU.xlsx eksik")
        db = M.DatabaseManager(str(tmp_path / "t.db"))
        count = db.import_table_a_excel(str(table_a))
        assert count > 2800
        c = db.search_chemicals("1203")[0]
        assert c.limited_quantity == "1 L"
        assert c.excepted_quantity == "E2"
        assert c.transport_category == "2"
        assert M.ADREngine.is_lq_allowed(c) is True


# =========================================================================
# Rapor denetimi: LQ/EQ işaretli ama limit aşan kalem KRİTİK hata üretmeli
# =========================================================================
class TestReportEnforcement:
    def _item(self, lq=False, eq=False, qty=10.0, count=1, lq_max=0.0, eq_max=0.0):
        return M.ShipmentItem(un_number="1203", proper_name="TEST", class_code="3",
                              net_quantity=qty, packaging_count=count, unit="L",
                              transport_category="2", is_lq=lq, is_eq=eq,
                              lq_max_per_package=lq_max, eq_max_per_package=eq_max)

    def _has_critical(self, report, needle):
        return any(needle in m for _, m in report.errors)

    def test_lq_over_limit_flagged(self):
        # 10 L / 2 ambalaj = 5 L/ambalaj > 1 L limit -> KRİTİK
        report = M.ADREngine.generate_adr_report(
            [self._item(lq=True, qty=10, count=2, lq_max=1.0)])
        assert self._has_critical(report, "LQ limiti asiliyor")

    def test_lq_within_limit_clean(self):
        report = M.ADREngine.generate_adr_report(
            [self._item(lq=True, qty=2, count=4, lq_max=1.0)])
        assert not self._has_critical(report, "LQ limiti")

    def test_eq_over_limit_flagged(self):
        # 0.1 kg/ambalaj = 100 g > 30 g (E2) -> KRİTİK
        report = M.ADREngine.generate_adr_report(
            [self._item(eq=True, qty=0.1, count=1, eq_max=30.0)])
        assert self._has_critical(report, "EQ ic ambalaj limiti")

    def test_eq_within_limit_clean(self):
        # 25 g < 30 g
        report = M.ADREngine.generate_adr_report(
            [self._item(eq=True, qty=0.025, count=1, eq_max=30.0)])
        assert not self._has_critical(report, "EQ ic ambalaj")

    def test_zero_packaging_count_no_crash(self):
        report = M.ADREngine.generate_adr_report(
            [self._item(lq=True, qty=5, count=0, lq_max=1.0)])
        assert report is not None  # sıfıra bölme çökmesi olmamalı
