# FAZ 4 TAŞIMA NOTU: monolit testinden uyarlandı; yükleyici bloğu
# "import webcore as M" ile değiştirildi (webcore aynı adları dışa açar).
# Qt sayfa sınıflarına dokunan testler masaüstünde kaldı (tests/ altında
# çalışmaya devam ederler); burada yalnız motor/veritabanı testleri koşar.
"""Ana program — Güvenlik Planı İnceleme Raporu (v4.7) testleri.

Kullanıcının paylaştığı gerçek "ASUTEK Endüstriyel Kimyasalları — Güvenlik
Planı İnceleme Raporu" örneğine dayanır. Rapor, firma kimyasal envanterini
ADR Tablo 1.10.3.1.2 kapsamında statik olarak (miktardan bağımsız, yalnızca
sınıf/PG/sınıflandırma koduna göre) tarar ve örnek belgeyle aynı formatta
çok sayfalı bir PDF üretir.

Bu turda yakalanan ve düzeltilen gerçek hatalar:
  1. _get_table_key(): class_code boşsa "".split()[0] IndexError fırlatıyordu
     (gerçek envanterde bazı kayıtlarda class_code boş).
  2. Paketleme grubu bazı kayıtlarda Arap rakamıyla ("1","2","3") geliyor;
     PG karşılaştırmaları güvenlik kararını etkilediği için Roma rakamına
     normalize edilmesi gerekiyordu.
  3. screen_inventory_chemical() ham sqlite3.Row nesnelerinde getattr ile
     SESSİZCE boş veri üretiyordu (sqlite3.Row attribute erişimini
     desteklemez) — bu, TÜM sonuçların yanlışlıkla "muaf" çıkmasına yol
     açabilecek ciddi bir hataydı. Şimdi hem dataclass hem sqlite3.Row/dict
     nesnelerini güvenle okuyor.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import webcore as M  # Faz 4: monolit yerine ayrıştırılmış çekirdek



TABLE_A = ROOT / "ADR_A_TABLOSU.xlsx"
ASUTEK = ROOT / "ASUTEK_Kimyasal_İnceleme_Kimyasal_Envanter__ADR_rev1.xlsx"
needs_real_excel = pytest.mark.skipif(
    not (TABLE_A.exists() and ASUTEK.exists()), reason="Gerçek Excel dosyaları eksik")


def chem(un_number, class_code, packing_group="", classification_code="",
        name="TEST", special_provisions=""):
    return M.Chemical(un_number=un_number, class_code=class_code,
                      packing_group=packing_group,
                      classification_code=classification_code,
                      proper_shipping_name_tr=name,
                      special_provisions=special_provisions)


# =========================================================================
# Örnek rapordaki 4 kimyasal — gerçek belgede hepsi MUAF çıkmıştı
# =========================================================================
class TestKnownExampleChemicals:
    @pytest.mark.parametrize("un,cls,pg,code,name", [
        ("1993", "3", "III", "F1", "ALEVLENEBİLİR SIVI, B.B.B."),
        ("2924", "3", "III", "FC", "ALEVLENEBİLİR SIVI, AŞINDIRICI, B.B.B."),
        ("3341", "4.2", "III", "S2", "TİYOÜRE DİOKSİT"),
        ("2014", "5.1", "II", "OC1", "HİDROJEN PEROKSİT SULU ÇÖZELTİ"),
    ])
    def test_matches_real_report_exempt_verdict(self, un, cls, pg, code, name):
        r = M.SecurityPlanEngine.screen_inventory_chemical(
            chem(un, cls, pg, code, name))
        assert r["in_scope"] is False, (
            f"UN{un} gerçek raporda MUAF idi, ama motor '{r['in_scope']}' döndürdü")


# =========================================================================
# Kapsam içi olması gereken maddeler (gerçek ADR 1.10.3.1.2 mantığı)
# =========================================================================
class TestInScopeDetection:
    def test_class1_explosive_always_in_scope(self):
        r = M.SecurityPlanEngine.screen_inventory_chemical(
            chem("0081", "1.1", classification_code="1.1D", name="PATLAYICI"))
        assert r["in_scope"] is True

    def test_class6_2_category_a_infectious_in_scope(self):
        r = M.SecurityPlanEngine.screen_inventory_chemical(
            chem("2814", "6.2", classification_code="I1", name="BULAŞICI MADDE"))
        assert r["in_scope"] is True

    def test_toxic_gas_in_scope(self):
        r = M.SecurityPlanEngine.screen_inventory_chemical(
            chem("1017", "2", classification_code="TC", name="KLOR"))
        assert r["in_scope"] is True

    def test_class6_1_pg1_toxic_solid_in_scope(self):
        r = M.SecurityPlanEngine.screen_inventory_chemical(
            chem("1994", "6.1", "I", "T1", "ZEHİRLİ MADDE"))
        assert r["in_scope"] is True

    def test_class8_pg1_corrosive_EXEMPT_in_packages(self):
        """Class 8 PG I: Tablo 1.10.3.1.2'de ambalaj sütunu 'b' (miktar ne
        olursa olsun muaf) — yalnızca TANK ≥3000L taşımada kapsama girer.
        Bu, ambalajlı taşımada PG I aşındırıcıların bile muaf olduğu
        (sezgiye aykırı ama doğru) bir ADR kuralıdır."""
        r = M.SecurityPlanEngine.screen_inventory_chemical(
            chem("1830", "8", "I", "C1", "AŞINDIRICI MADDE"))
        assert r["in_scope"] is False

    def test_class3_pg3_exempt_no_matching_row(self):
        r = M.SecurityPlanEngine.screen_inventory_chemical(
            chem("1202", "3", "III", name="MAZOT"))
        assert r["in_scope"] is False


# =========================================================================
# BUG-1: class_code boş olunca IndexError
# =========================================================================
class TestEmptyClassCodeRobustness:
    def test_empty_class_code_no_crash(self):
        r = M.SecurityPlanEngine.screen_inventory_chemical(
            chem("9999", "", "", "", "BİLİNMEYEN"))
        assert r["in_scope"] is False  # çökmeden muaf kabul edilir

    def test_none_class_code_no_crash(self):
        c = M.Chemical(un_number="9998", class_code=None)
        r = M.SecurityPlanEngine.screen_inventory_chemical(c)
        assert r["in_scope"] is False


# =========================================================================
# BUG-2: Paketleme grubu Arap rakamıyla geldiğinde normalize edilmeli
# =========================================================================
class TestPackingGroupNormalization:
    def test_arabic_1_normalized_to_roman(self):
        """PG '1' (Arap) ile 'I' (Roma) AYNI sonucu vermeli — aksi halde
        güvenlik-kritik bir PG I madde sessizce muaf sayılabilir."""
        r_roman = M.SecurityPlanEngine.screen_inventory_chemical(
            chem("1994", "6.1", "I", "T1"))
        r_arabic = M.SecurityPlanEngine.screen_inventory_chemical(
            chem("1994", "6.1", "1", "T1"))
        assert r_roman["in_scope"] == r_arabic["in_scope"] is True

    def test_arabic_2_and_3_also_normalized(self):
        r2 = M.SecurityPlanEngine.screen_inventory_chemical(chem("1830", "8", "2"))
        rII = M.SecurityPlanEngine.screen_inventory_chemical(chem("1830", "8", "II"))
        assert r2["in_scope"] == rII["in_scope"]


# =========================================================================
# BUG-3: Ham sqlite3.Row nesnesi getattr ile SESSİZCE boş veri üretiyordu
# =========================================================================
class TestRawRowRobustness:
    def test_raw_sqlite_row_gives_same_result_as_dataclass(self, tmp_path):
        db = M.DatabaseManager(str(tmp_path / "t.db"))
        db.add_chemical(chem("0081", "1.1", classification_code="1.1D",
                             name="PATLAYICI TEST"))
        raw_row = db.execute_one(
            "SELECT * FROM chemicals WHERE un_number=?", ("0081",))
        chemical_obj = db._row_to_chemical(raw_row)

        r_raw = M.SecurityPlanEngine.screen_inventory_chemical(raw_row)
        r_obj = M.SecurityPlanEngine.screen_inventory_chemical(chemical_obj)

        assert r_raw["un_number"] == r_obj["un_number"] == "0081"
        assert r_raw["in_scope"] == r_obj["in_scope"] is True

    def test_plain_dict_also_works(self):
        d = {"un_number": "0081", "class_code": "1.1",
             "classification_code": "1.1D", "packing_group": "",
             "proper_shipping_name_tr": "TEST"}
        r = M.SecurityPlanEngine.screen_inventory_chemical(d)
        assert r["un_number"] == "0081"
        assert r["in_scope"] is True


# =========================================================================
# screen_inventory (toplu tarama) — sayaçlar
# =========================================================================
class TestBulkScreening:
    def test_counts_add_up(self):
        chemicals = [
            chem("1993", "3", "III"),           # muaf
            chem("2014", "5.1", "II"),           # muaf
            chem("0081", "1.1", classification_code="1.1D"),  # kapsam içi
            chem("2814", "6.2", classification_code="I1"),    # kapsam içi
        ]
        result = M.SecurityPlanEngine.screen_inventory(chemicals)
        assert result["total"] == 4
        assert result["in_scope_count"] == 2
        assert result["exempt_count"] == 2
        assert len(result["results"]) == 4

    def test_empty_inventory(self):
        result = M.SecurityPlanEngine.screen_inventory([])
        assert result["total"] == 0
        assert result["in_scope_count"] == 0


# =========================================================================
# PDF/HTML rapor üretimi
# =========================================================================
class TestReportGeneration:
    def test_html_contains_expected_sections(self):
        result = M.SecurityPlanEngine.screen_inventory(
            [chem("1993", "3", "III"), chem("0081", "1.1", classification_code="1.1D")])
        html = M.SecurityPlanEngine.generate_inventory_review_html(
            company_name="TEST FİRMA A.Ş.", prepared_by="Test Danışman",
            approved_by="Test Onaylayan", screen_result=result,
            date_str="01/01/2026", validity_years=2)
        assert "TEST FİRMA A.Ş." in html
        assert "GÜVENLİK PLANI İNCELEME RAPORU" in html
        assert "ADR TABLO 1.10.3.1.2" in html
        assert "CİDDİ SONUÇLARA NEDEN OLABİLECEK MADDELER" in html
        assert "GÜVENLİK PLANI HAZIRLANMASI GEREKLİDİR" in html  # kapsam içi var

    def test_conclusion_when_all_exempt(self):
        result = M.SecurityPlanEngine.screen_inventory([chem("1993", "3", "III")])
        html = M.SecurityPlanEngine.generate_inventory_review_html(
            company_name="F", prepared_by="P", approved_by="A",
            screen_result=result)
        assert "GÜVENLİK PLANI HAZIRLANMASINA GEREK YOKTUR" in html
        assert "GEREKLİDİR" not in html

    def test_empty_result_no_crash(self):
        result = M.SecurityPlanEngine.screen_inventory([])
        html = M.SecurityPlanEngine.generate_inventory_review_html(
            company_name="F", prepared_by="P", approved_by="A",
            screen_result=result)
        assert "Envanterde kimyasal bulunamadı" in html

    def test_pdf_actually_renders(self, tmp_path):
        # Faz 4 uyarlaması: monolit bu PDF'i QTextDocument+QPrinter ile
        # üretiyordu; web karşılığı WeasyPrint'tir (webcore.pdf).
        pytest.importorskip("weasyprint")
        from webcore.pdf import html_to_pdf_bytes
        result = M.SecurityPlanEngine.screen_inventory(
            [chem("1993", "3", "III"), chem("2924", "3", "III")])
        html = M.SecurityPlanEngine.generate_inventory_review_html(
            company_name="F", prepared_by="P", approved_by="A",
            screen_result=result)
        blob = html_to_pdf_bytes(html)
        assert blob[:5] == b"%PDF-"
        assert len(blob) > 3000


class TestRealAsutekInventoryScreening:
    """Faz 4 tamamlama: TestRealAsutekInventory'nin masaüstünde bırakılan
    4 testinden yalnız 2'si gerçekten Qt'ye bağlıydı
    (test_ui_scan_button_populates_table, test_ui_pdf_export_end_to_end —
    ADRTransportPro penceresi + widget'lara dokunuyorlar, tests/ altında
    kalmaya devam ederler). Aşağıdaki iki test ise saf motor/veritabanı
    testidir (Qt yok) ve buraya taşındı; ONCEKİ not (bu ikisinin
    test_webcore_smoke.py::TestEnvanterImport ile karşılandığı) yanlıştı —
    o test yalnızca import'un satır eklediğini doğruluyor,
    SecurityPlanEngine.screen_inventory pipeline'ını hiç çalıştırmıyordu."""

    def _load_chemicals(self, db):
        rows = db.execute(
            "SELECT DISTINCT un_number, classification_code, packing_group "
            "FROM company_products")
        result = []
        for r in rows:
            row = db.execute_one(
                "SELECT * FROM chemicals WHERE un_number=? AND "
                "classification_code=? AND packing_group=?",
                (r["un_number"], r["classification_code"] or "",
                 r["packing_group"] or ""))
            if row:
                result.append(db._row_to_chemical(row))
        return result

    @needs_real_excel
    def test_full_pipeline_no_crash(self, tmp_path):
        db = M.DatabaseManager(str(tmp_path / "t.db"))
        db.import_table_a_excel(str(TABLE_A))
        db.import_company_inventory_excel(str(ASUTEK))
        chemicals = self._load_chemicals(db)
        assert len(chemicals) == 36

        result = M.SecurityPlanEngine.screen_inventory(chemicals)
        assert result["total"] == 36
        # Tüm sonuçlar dolu UN numarasına sahip olmalı (BUG-3 regresyonu)
        assert all(r["un_number"] for r in result["results"])

    @needs_real_excel
    def test_pg1_item_un2054_exempt_per_class8_rule(self, tmp_path):
        """UN2054 (MORFOLİN, Sınıf 8 (+3), PG I) gerçek envanterde var;
        Class 8 PG I paket kuralı 'b' (muaf) olduğundan exempt olmalı."""
        db = M.DatabaseManager(str(tmp_path / "t.db"))
        db.import_table_a_excel(str(TABLE_A))
        db.import_company_inventory_excel(str(ASUTEK))
        chemicals = self._load_chemicals(db)
        result = M.SecurityPlanEngine.screen_inventory(chemicals)
        un2054 = next(r for r in result["results"] if r["un_number"] == "2054")
        assert un2054["in_scope"] is False


# =========================================================================
# Gerçek ASUTEK verisiyle uçtan uca
# =========================================================================
# NOT: TestRealAsutekInventory'nin Qt'ye bağlı 2 testi (pencere + sayfa
# akışı: test_ui_scan_button_populates_table, test_ui_pdf_export_end_to_end)
# masaüstünde kaldı. Saf motor testleri (test_full_pipeline_no_crash,
# test_pg1_item_un2054_exempt_per_class8_rule) yukarıda
# TestRealAsutekInventoryScreening olarak taşındı.
