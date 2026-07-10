"""Ana program — Karışık Yükleme sayfası (v4.4 entegrasyonu) testleri.

Bu özellik ilk olarak main.py'ye (artık kullanılmıyor) entegre edilmişti.
main.py iptal edildiği için tüm mantık burada, gerçek ana programda
(adr_transport_pro_2026.py) sıfırdan doğru mimariyle inşa edildi:

  * Veri kaynağı artık adr_database.json değil, ana programın kendi SQL
    veritabanı (chemicals tablosu, composite anahtar UN+SınıfKodu+PG).
  * Aynı UN'nin birden fazla Tablo A varyasyonu varsa (UN1950 = 12 kod),
    kullanıcı VariantPickerDialog ile hangi varyasyonun taşınacağını
    açıkça seçer — sessizce rastgele/ilk varyasyon kullanılmaz.
  * "Aktif Sevkiyattan Aktar": sevkiyat kalemleri kendi classification_code
    ve packing_group bilgisini taşıdığından, bu yolda belirsizlik yoktur.
"""
import os
import sys
import tempfile
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

from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog  # noqa: E402

_app = QApplication.instance() or QApplication([])
for _f in ("information", "warning", "critical"):
    setattr(QMessageBox, _f, staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))

TABLE_A = ROOT / "ADR_A_TABLOSU.xlsx"
needs_real_excel = pytest.mark.skipif(
    not TABLE_A.exists(), reason="Gerçek ADR_A_TABLOSU.xlsx eksik")


@pytest.fixture()
def db(tmp_path):
    return M.DatabaseManager(str(tmp_path / "t.db"))


@pytest.fixture()
def page(db):
    return M.MixLoadCheckPage(db, parent=None)


def _accept_variant(monkeypatch, index: int):
    """VariantPickerDialog.exec()'i, listeden `index` numaralı satırı
    seçip kabul edecek şekilde sahteler (gerçek GUI etkileşimi olmadan)."""
    def fake_exec(self):
        self.selected_row = self._variants[index]
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(M.VariantPickerDialog, "exec", fake_exec)


def _cancel_variant(monkeypatch):
    def fake_exec(self):
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(M.VariantPickerDialog, "exec", fake_exec)


class TestPageWiring:
    def test_page_added_to_content_stack(self, tmp_path, monkeypatch):
        orig_init = M.DatabaseManager.__init__

        def patched_init(self, db_path=None):
            orig_init(self, db_path or str(tmp_path / "t.db"))
        monkeypatch.setattr(M.DatabaseManager, "__init__", patched_init)

        db_probe = M.DatabaseManager()
        sec = M.SecurityManager(db_probe._get_conn())
        w = M.ADRTransportPro(security=sec)
        try:
            assert hasattr(w, "mix_load_page")
            assert isinstance(w.mix_load_page, M.MixLoadCheckPage)
            assert w.content_stack.indexOf(w.mix_load_page) == 11
        finally:
            w.close()


@needs_real_excel
class TestVariantSelection:
    def test_single_variant_no_dialog(self, page, monkeypatch, db):
        db.import_table_a_excel(str(TABLE_A))

        def fail_if_called(self):
            raise AssertionError("Tek varyasyonlu UN için dialog açılmamalı")
        monkeypatch.setattr(M.VariantPickerDialog, "exec", fail_if_called)

        page._add_un("1203")
        assert "1203" in page._un_order

    def test_multi_variant_opens_dialog_with_all_options(self, page, monkeypatch, db):
        """KRİTİK: UN1950 (AEROSOL) 12 varyasyonun HEPSİ seçenek olarak
        sunulmalı — kullanıcının kendi tespiti buydu."""
        db.import_table_a_excel(str(TABLE_A))
        captured = {}

        def fake_exec(self):
            captured["variants"] = list(self._variants)
            self.selected_row = self._variants[0]
            return QDialog.DialogCode.Accepted
        monkeypatch.setattr(M.VariantPickerDialog, "exec", fake_exec)

        page._add_un("1950")
        assert len(captured["variants"]) == 12
        assert "1950" in page._un_order

    def test_selected_variant_is_the_one_registered(self, page, monkeypatch, db):
        db.import_table_a_excel(str(TABLE_A))
        variants = page.adapter.get_variants("1950")
        target_code = variants[5]["classification_code"]

        _accept_variant(monkeypatch, 5)
        page._add_un("1950")

        rec = page.adapter.try_get_record("1950")
        assert rec.classification_code == target_code

    def test_cancel_dialog_does_not_add_un(self, page, monkeypatch, db):
        db.import_table_a_excel(str(TABLE_A))
        _cancel_variant(monkeypatch)
        page._add_un("1950")
        assert "1950" not in page._un_order

    def test_unknown_un_added_without_dialog(self, page, monkeypatch, db):
        db.import_table_a_excel(str(TABLE_A))

        def fail_if_called(self):
            raise AssertionError("Bilinmeyen UN için dialog açılmamalı")
        monkeypatch.setattr(M.VariantPickerDialog, "exec", fail_if_called)

        page._add_un("8888")
        assert "8888" in page._un_order
        assert "veritabanında yok" in page.un_list.item(0).text()


class TestInputHygiene:
    def test_invalid_un_rejected(self, page):
        page._add_un("12")
        assert page._un_order == []

    def test_un_prefix_accepted(self, page, monkeypatch, db):
        db.execute_update(
            "INSERT INTO chemicals (un_number, class_code, proper_shipping_name_tr) "
            "VALUES (?,?,?)", ("1830", "8", "SÜLFÜRİK ASİT"))
        page._add_un("UN1830")
        assert "1830" in page._un_order

    def test_duplicate_not_added_twice(self, page, db):
        db.execute_update(
            "INSERT INTO chemicals (un_number, class_code, proper_shipping_name_tr) "
            "VALUES (?,?,?)", ("1203", "3", "BENZİN"))
        page._add_un("1203")
        page._add_un("1203")
        assert page._un_order.count("1203") == 1

    def test_clear_resets_everything(self, page, db):
        db.execute_update(
            "INSERT INTO chemicals (un_number, class_code, proper_shipping_name_tr) "
            "VALUES (?,?,?)", ("1203", "3", "BENZİN"))
        page._add_un("1203")
        page._clear_all()
        assert page._un_order == [] and page.un_list.count() == 0


class TestShipmentImport:
    def test_import_uses_items_own_variant_no_ambiguity(self, page, monkeypatch, db):
        """Sevkiyat kalemi kendi classification_code/PG bilgisini tasidigi
        icin, UN'nin baska varyasyonlari olsa bile dialog acilmamali."""
        db.execute_update(
            "INSERT INTO chemicals (un_number, classification_code, packing_group, "
            "class_code, proper_shipping_name_tr) VALUES (?,?,?,?,?)",
            ("1950", "5A", "", "2", "AEROSOL - ASFIKSAN"))
        db.execute_update(
            "INSERT INTO chemicals (un_number, classification_code, packing_group, "
            "class_code, proper_shipping_name_tr) VALUES (?,?,?,?,?)",
            ("1950", "5T", "", "6.1", "AEROSOL - ZEHIRLI"))

        def fail_if_called(self):
            raise AssertionError("Sevkiyattan aktarımda dialog açılmamalı")
        monkeypatch.setattr(M.VariantPickerDialog, "exec", fail_if_called)

        class FakeShipmentPage:
            items = [M.ShipmentItem(un_number="1950", classification_code="5T",
                                    packing_group="", proper_name="AEROSOL")]

        class FakeMainWindow:
            shipment_page = FakeShipmentPage()

        page.parent_window = FakeMainWindow()
        page._import_from_shipment()

        assert "1950" in page._un_order
        rec = page.adapter.try_get_record("1950")
        assert rec.classification_code == "5T"  # kalemdeki DOĞRU varyasyon

    def test_import_empty_shipment_shows_info(self, page):
        class FakeShipmentPage:
            items = []

        class FakeMainWindow:
            shipment_page = FakeShipmentPage()

        page.parent_window = FakeMainWindow()
        page._import_from_shipment()  # çökmemeli
        assert page._un_order == []


class TestCheckExecution:
    def test_check_requires_at_least_two(self, page, db):
        db.execute_update(
            "INSERT INTO chemicals (un_number, class_code, proper_shipping_name_tr) "
            "VALUES (?,?,?)", ("1203", "3", "BENZİN"))
        page._add_un("1203")
        page._run_check()
        assert page._results == []

    def test_class1_vs_other_forbidden(self, page, db):
        db.execute_update(
            "INSERT INTO chemicals (un_number, class_code, classification_code, "
            "hazard_labels, proper_shipping_name_tr) VALUES (?,?,?,?,?)",
            ("0335", "1", "1.3G", "1.3G", "HAVAİ FİŞEK"))
        db.execute_update(
            "INSERT INTO chemicals (un_number, class_code, proper_shipping_name_tr) "
            "VALUES (?,?,?)", ("1203", "3", "BENZİN"))
        page._add_un("0335")
        page._add_un("1203")
        page._run_check()
        assert len(page._results) == 1
        assert page._results[0].status == "NO"

    def test_results_enable_export_buttons(self, page, db):
        db.execute_update(
            "INSERT INTO chemicals (un_number, class_code, proper_shipping_name_tr) "
            "VALUES (?,?,?)", ("1203", "3", "BENZİN"))
        db.execute_update(
            "INSERT INTO chemicals (un_number, class_code, proper_shipping_name_tr) "
            "VALUES (?,?,?)", ("1830", "8", "SÜLFÜRİK ASİT"))
        page._add_un("1203")
        page._add_un("1830")
        assert not page.btn_excel.isEnabled()
        page._run_check()
        assert page.btn_excel.isEnabled() and page.btn_pdf.isEnabled()


class TestAdapterRobustness:
    def test_cv28_extracted_for_food_caution(self, db):
        db.execute_update(
            "INSERT INTO chemicals (un_number, class_code, special_provisions, "
            "proper_shipping_name_tr) VALUES (?,?,?,?)",
            ("2814", "6.2", "CV13 | CV28", "BULAŞICI MADDE"))
        adapter = M.AnaDbChemicalAdapter(db)
        adapter.register_variant("2814")
        rec = adapter.try_get_record("2814")
        assert "CV28" in rec.cv_codes

    def test_missing_un_returns_none(self, db):
        adapter = M.AnaDbChemicalAdapter(db)
        assert adapter.try_get_record("9999") is None

    def test_register_unknown_prevents_crash(self, db):
        adapter = M.AnaDbChemicalAdapter(db)
        adapter.register_unknown("9999")
        rec = adapter.try_get_record("9999")
        assert rec is not None and rec.labels == []
