# FAZ 4 TAŞIMA NOTU: monolit test_letterhead_ana_program.py'den yalnız
# STATİK filigran üretim testleri taşındı (saf Pillow — artık
# webcore.pdf.build_letterhead_watermark_b64). Sayfa/pencere düzeyindeki
# TestLetterheadWatermarkPresence ve ...VisualEffect sınıfları Qt'ye bağlı
# olduğundan masaüstünde (tests/) kaldı.
import base64
import io

import pytest

PIL_Image = pytest.importorskip("PIL.Image")

from webcore.pdf import build_letterhead_watermark_b64  # noqa: E402


def _logo_b64(renk=(200, 30, 30, 255), boyut=(200, 80)) -> str:
    img = PIL_Image.new("RGBA", boyut, renk)
    buf = io.BytesIO(); img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


class TestLetterheadWatermarkGeneration:
    def test_generator_returns_empty_when_nothing_to_show(self):
        assert build_letterhead_watermark_b64("", True) == ""

    def test_generator_returns_data_for_draft_even_without_logo(self):
        b64 = build_letterhead_watermark_b64("", False)
        assert b64 != ""

    def test_generator_handles_corrupt_logo_gracefully(self):
        b64 = build_letterhead_watermark_b64(
            "not-valid-base64!!!", True)
        # Bozuk logo cokmemeli; onaylı + bozuk logo -> filigran yok (bos) kabul edilir
        assert b64 == "" or isinstance(b64, str)

    def test_generator_output_is_valid_png(self):
        logo = _logo_b64()
        b64 = build_letterhead_watermark_b64(logo, False)
        raw = base64.b64decode(b64)
        assert raw[:8] == b"\x89PNG\r\n\x1a\n"
