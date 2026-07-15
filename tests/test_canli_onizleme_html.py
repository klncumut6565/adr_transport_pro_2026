"""Masaüstü — Canlı Evrak Önizleme artık düz metin değil, gerçek HTML.

Umut'un tespiti: canlı önizleme (ADR Kontrol Merkezi paneli, sağ alt)
yalnızca düz metin bir özet gösteriyordu (UN numaraları, puan, plaka
durumu satır satır) — "bu program için çok amatör duruyor" dedi.

Düzeltme: self.preview_text artık QPlainTextEdit değil QTextEdit;
_update_preview() artık elle metin satırları biriktirmek yerine
GERÇEK belge HTML'ini (_build_print_html() — PDF üretiminde kullanılan
AYNI fonksiyon) setHtml() ile render ediyor. Önizleme artık gerçek
çıktıyla birebir tutarlı (aynı HTML, aynı QTextDocument motoru).
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

from PyQt6.QtWidgets import QApplication, QTextEdit


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def db():
    yol = os.path.join(tempfile.mkdtemp(), "test.db")
    d = M.DatabaseManager(yol)
    d.import_table_a_excel(str(ROOT / "ADR_A_TABLOSU.xlsx"))
    return d


class TestCanliOnizlemeGercekHtml:
    def test_kaynak_kodda_qplaintextedit_yerine_qtextedit_kullaniliyor(self):
        """Statik kontrol: preview_text tanımı artık QTextEdit olmalı."""
        src = open(ROOT / "adr_transport_pro_2026.py", encoding="utf-8").read()
        assert "self.preview_text = QTextEdit()" in src
        assert "self.preview_text = QPlainTextEdit()" not in src

    def test_update_preview_artik_sethtml_kullaniyor(self):
        """Statik kontrol: _update_preview artık setPlainText değil
        setHtml çağırmalı ve gerçek _build_print_html() sonucunu kullanmalı."""
        src = open(ROOT / "adr_transport_pro_2026.py", encoding="utf-8").read()
        i = src.index("def _update_preview")
        j = src.index("def _new_shipment")
        govde = src[i:j]
        assert "self.preview_text.setHtml(" in govde
        assert "self.shipment_page._build_print_html()" in govde
        assert "self.preview_text.setPlainText(" not in govde

    def test_qtextedit_gercek_belge_htmlini_cokmeden_render_eder(self, qapp, db):
        """Fonksiyonel kanıt: gerçek (44K+ karakterlik) belge HTML'i
        QTextEdit'e verildiğinde çökme olmuyor ve içerik doğru geliyor."""
        sender = M.Company(type="sender", name="TEST GONDEREN AS")
        db.add_company(sender)
        receiver = M.Company(type="receiver", name="TEST ALICI AS")
        db.add_company(receiver)

        sayfa = M.ShipmentEditorPage(db, None)
        kimyasal = db.search_chemicals("1203")[0]
        item = M.ShipmentItem(
            un_number="1203", proper_name=kimyasal.proper_shipping_name_tr,
            class_code="3", packing_group="II", packaging_type="Varil",
            packaging_count=4, net_quantity=200, unit="L",
            transport_category="2", tunnel_code="D/E")
        sayfa.items = [item]

        html = sayfa._build_print_html()
        assert len(html) > 1000, "belge HTML'i beklenenden çok kısa"

        onizleme = QTextEdit()
        onizleme.setReadOnly(True)
        onizleme.setHtml(html)  # çökmemeli
        duz = onizleme.toPlainText()
        assert duz.strip(), "render edilen içerik boş kaldı"
        assert "BENZİN" in duz.upper() or "BENZIN" in duz.upper()

    def test_eski_metin_ozeti_basliklari_artik_uretilmiyor(self):
        """Eski düz-metin özetine özgü sabit başlıklar kaynak kodda
        (_update_preview gövdesinde) artık olmamalı."""
        src = open(ROOT / "adr_transport_pro_2026.py", encoding="utf-8").read()
        i = src.index("def _update_preview")
        j = src.index("def _new_shipment")
        govde = src[i:j]
        assert "ADR TEHLIKELI MADDE TASIMA EVRAKI" not in govde
        assert "ADR KONTROL OZETI" not in govde
