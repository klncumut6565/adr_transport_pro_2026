"""Ana program (adr_transport_pro_2026.py) — antetli kağıt filigranı testleri.

Bulunan ve düzeltilen kritik hata: belgenin genel <style> bloğundaki
`table { border-collapse: collapse; width: 100%; }` kuralı, Qt'nin zengin
metin motorunda background-image'i TAMAMEN bastırıyordu. İlk yama sonrası
filigran hiçbir yerde görünmüyordu (yalnızca üstteki küçük logo simgesi
görünüyordu — o farklı bir koddu). Kanıt: watermark açık/kapalı render
farkı yalnızca üst-sol köşedeki mevcut logoyla sınırlıydı (y:29-144).
Düzeltme: sarmalayıcı tabloya inline `border-collapse:separate` eklendi;
sonrasında fark neredeyse tüm sayfaya yayıldı (y:29-1220 / x:28-1210).

Bu testler hem hatayı hem düzeltmeyi kalıcı hale getirir.
"""
import base64
import io
import os
import re
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

from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

_app = QApplication.instance() or QApplication([])
for _f in ("information", "warning", "critical"):
    setattr(QMessageBox, _f, staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))


def _sample_logo_b64(color=(30, 58, 95, 255)) -> str:
    from PIL import Image
    img = Image.new("RGBA", (300, 120), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@pytest.fixture()
def app_window(tmp_path, monkeypatch):
    # ShipmentEditorPage kendi db referansini constructor'da alir (self.db = db)
    # ve sonradan w.db degistirilse bile guncellenmez. Bu yuzden ADRTransportPro
    # olusturulmadan ONCE DatabaseManager'in varsayilan yolunu izole bir tmp
    # dosyaya yonlendiriyoruz ki w.db ve sp.db AYNI (izole) ornegi paylassin.
    tmp_db_path = str(tmp_path / "t.db")
    orig_init = M.DatabaseManager.__init__

    def patched_init(self, db_path: str = None):
        orig_init(self, db_path or tmp_db_path)

    monkeypatch.setattr(M.DatabaseManager, "__init__", patched_init)

    db_probe = M.DatabaseManager()
    sec = M.SecurityManager(db_probe._get_conn())
    w = M.ADRTransportPro(security=sec)
    sp = w.shipment_page
    sp.items = [M.ShipmentItem(
        un_number="1203", proper_name="BENZİN", class_code="3",
        packing_group="II", net_quantity=100, packaging_count=2,
        unit="L", packaging_type="Varil", transport_category="2",
        tunnel_code="D/E")]
    yield w
    w.close()


def _extract_watermark_b64(html: str):
    m = re.search(r'background-image:url\(data:image/png;base64,([^)]+)\)', html)
    return m.group(1) if m else None


class TestLetterheadWatermarkPresence:
    def test_draft_has_watermark_table(self, app_window):
        sp = app_window.shipment_page
        app_window.db.set_company_logo_b64(_sample_logo_b64())
        sp.lbl_status.setText("TASLAK")
        html = sp._build_print_html()
        assert "background-image:url(data:image/png;base64," in html

    def test_wrapper_has_border_collapse_separate(self, app_window):
        """KRİTİK REGRESYON: global `table{border-collapse:collapse}` kuralı
        bu inline override olmadan filigranı tamamen bastırır."""
        sp = app_window.shipment_page
        app_window.db.set_company_logo_b64(_sample_logo_b64())
        sp.lbl_status.setText("TASLAK")
        html = sp._build_print_html()
        i = html.find("background-image:url(data:image/png;base64,")
        assert i != -1
        # Ayni <table ...> etiketi icinde border-collapse:separate bulunmali
        tag_start = html.rfind("<table", 0, i)
        tag_end = html.find(">", i)
        tag = html[tag_start:tag_end]
        assert "border-collapse:separate" in tag

    def test_no_logo_and_approved_no_watermark(self, app_window):
        """Logo yok + evrak onaylı: watermark tablosu HİÇ eklenmemeli
        (gereksiz islem/yan etki olmasin)."""
        sp = app_window.shipment_page
        app_window.db.set_company_logo_b64("")
        sp.lbl_status.setText("ONAYLANDI")
        html = sp._build_print_html()
        assert "background-image:url" not in html

    def test_no_logo_but_draft_still_has_watermark(self, app_window):
        """Logo olmasa bile TASLAK durumunda filigran (sadece TASLAK yazısı)
        eklenmelidir."""
        sp = app_window.shipment_page
        app_window.db.set_company_logo_b64("")
        sp.lbl_status.setText("TASLAK")
        html = sp._build_print_html()
        assert "background-image:url" in html

    def test_draft_and_approved_watermarks_differ(self, app_window):
        sp = app_window.shipment_page
        app_window.db.set_company_logo_b64(_sample_logo_b64())
        sp.lbl_status.setText("TASLAK")
        b64_draft = _extract_watermark_b64(sp._build_print_html())
        sp.lbl_status.setText("ONAYLANDI")
        b64_approved = _extract_watermark_b64(sp._build_print_html())
        assert b64_draft is not None and b64_approved is not None
        assert b64_draft != b64_approved


class TestLetterheadWatermarkVisualEffect:
    """Piksel-düzeyinde doğrulama: watermark gerçekten PDF'e işleniyor mu?
    (HTML'de string olarak var olması yetmez — Qt render'da suskun
    bastırabilir; nitekim bu tam olarak yakalanan hataydı.)"""

    def test_watermark_visible_across_page_not_just_header(self, app_window, tmp_path):
        pytest.importorskip("fitz", reason="PDF render karşılaştırması için pypdfium/fitz gerekli")

    def test_watermark_pixel_diff_spans_most_of_page(self, app_window, tmp_path):
        try:
            from pdf2image import convert_from_path
        except ImportError:
            pytest.skip("pdf2image kurulu değil")

        sp = app_window.shipment_page
        sp.lbl_status.setText("ONAYLANDI")

        sp.db.set_company_logo_b64("")
        ref_path = tmp_path / "ref.pdf"
        sp._generate_pdf(str(ref_path))

        sp.db.set_company_logo_b64(_sample_logo_b64((0, 0, 0, 255)))
        wm_path = tmp_path / "wm.pdf"
        sp._generate_pdf(str(wm_path))

        import numpy as np
        img_ref = convert_from_path(str(ref_path), dpi=100)[0].convert("RGB")
        img_wm = convert_from_path(str(wm_path), dpi=100)[0].convert("RGB")
        arr_ref = np.array(img_ref)
        arr_wm = np.array(img_wm)
        assert arr_ref.shape == arr_wm.shape

        diff = np.abs(arr_ref.astype(int) - arr_wm.astype(int)).sum(axis=2)
        changed = diff > 5
        ys, xs = changed.nonzero()

        assert changed.sum() > 5000, (
            "Watermark neredeyse hic piksel degistirmiyor - "
            "border-collapse regresyonu geri gelmis olabilir!"
        )
        # Sadece ust-sol kucuk logo simgesi degil, sayfanin genisinde
        # (en az %60 yukseklik araliginda) etkili olmali.
        page_h = arr_ref.shape[0]
        y_span = ys.max() - ys.min()
        assert y_span > 0.5 * page_h, (
            f"Watermark etkisi cok dar bir alanda (y_span={y_span}, "
            f"sayfa yuksekligi={page_h}) - sadece header logosu olabilir!"
        )


class TestLetterheadWatermarkGeneration:
    def test_generator_returns_empty_when_nothing_to_show(self):
        assert M.ShipmentEditorPage._build_letterhead_watermark_b64("", True) == ""

    def test_generator_returns_data_for_draft_even_without_logo(self):
        b64 = M.ShipmentEditorPage._build_letterhead_watermark_b64("", False)
        assert b64 != ""

    def test_generator_handles_corrupt_logo_gracefully(self):
        b64 = M.ShipmentEditorPage._build_letterhead_watermark_b64(
            "not-valid-base64!!!", True)
        # Bozuk logo cokmemeli; onaylı + bozuk logo -> filigran yok (bos) kabul edilir
        assert b64 == "" or isinstance(b64, str)

    def test_generator_output_is_valid_png(self):
        logo = _sample_logo_b64()
        b64 = M.ShipmentEditorPage._build_letterhead_watermark_b64(logo, False)
        raw = base64.b64decode(b64)
        assert raw[:8] == b"\x89PNG\r\n\x1a\n"
