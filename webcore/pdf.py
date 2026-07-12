"""PDF üretim katmanı — Faz 3a (QTextDocument+QPrinter → WeasyPrint).

İçerik:
  * html_to_pdf_bytes(html): A4 PDF baytları üretir (WeasyPrint).
  * build_letterhead_watermark_b64(...): monolitteki Pillow tabanlı antet
    filigranı, ShipmentEditorPage'den SATIRI SATIRINA taşındı (saf Pillow,
    Qt bağımlılığı yoktu; yalnız fonksiyon adı başındaki alt çizgi kalktı).
  * Filigran HOOK'u: webcore/engines.py içindeki SecurityPlanEngine,
    filigranı `ShipmentEditorPage._build_letterhead_watermark_b64` üzerinden
    try/except ile arar (monolit mirası). Motora dokunmadan bağlamak için
    bu modül import edildiğinde webcore.engines modülüne aynı ada sahip
    küçük bir vekil (shim) sınıf enjekte edilir — Faz 0a'dan beri "web'de
    filigran bilinçli boş" notunun kapanışıdır.

Streamlit Cloud notu: WeasyPrint sistem kitaplıkları ister; repo kökündeki
packages.txt (libpango...) bu yüzden vardır.
"""

from __future__ import annotations

import logging


def html_to_pdf_bytes(html: str, base_url: str | None = None) -> bytes:
    """HTML'i A4 PDF baytlarına çevirir. WeasyPrint yoksa ImportError."""
    from weasyprint import HTML  # geç import: masaüstü ortamını zorlamasın
    return HTML(string=html, base_url=base_url).write_pdf()


def build_letterhead_watermark_b64(logo_b64: str, is_approved: bool,
                                    w: int = 794, h: int = 1120) -> str:
    """Antetli kagit gorunumu icin tek bir arka plan PNG'i uretir:
      - Firma logosu, sayfa ortasinda cok soluk (%8 opaklik) filigran.
      - Onaylanmamis evrakta (TASLAK/DOGRULAMA HATALI) kirmizi, 30 derece
        egik "TASLAK" yazisi ayni goruntuye bindirilir.
    Qt'nin zengin metin motoru CSS opacity/transform desteklemedigi icin
    (test edildi: yalnizca <table>/<td> uzerinde background-image calisir,
    opacity/rotate calismaz) efekt onceden Pillow ile goruntuye islenir.
    Logo yoksa ve evrak onayliysa None doner (arka plan eklenmez)."""
    if not logo_b64 and is_approved:
        return ""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import base64 as _b64, io as _io
    except ImportError:
        return ""  # Pillow kurulu degilse filigransiz devam et

    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    if logo_b64:
        try:
            raw = _b64.b64decode(logo_b64)
            logo = Image.open(_io.BytesIO(raw)).convert("RGBA")
            target_w = int(w * 0.55)
            ratio = target_w / logo.width if logo.width else 1
            target_h = max(1, int(logo.height * ratio))
            logo = logo.resize((target_w, target_h), Image.LANCZOS)
            r, g, b, a = logo.split()
            a = a.point(lambda px: int(px * 0.08))  # %8 opaklik
            logo.putalpha(a)
            pos = ((w - target_w) // 2, (h - target_h) // 2)
            canvas.alpha_composite(logo, pos)
        except Exception:
            logging.getLogger(__name__).warning(
                "Antet logosu islenemedi", exc_info=True)

    if not is_approved:
        txt_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(txt_layer)
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 90)
        except Exception:
            font = ImageFont.load_default()
        text = "TASLAK"
        bbox = d.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text(((w - tw) / 2 - bbox[0], (h - th) / 2 - bbox[1]),
               text, font=font, fill=(200, 30, 30, 70))
        txt_layer = txt_layer.rotate(30, expand=False, resample=Image.BICUBIC)
        canvas.alpha_composite(txt_layer)

    buf = _io.BytesIO()
    canvas.save(buf, format="PNG")
    return _b64.b64encode(buf.getvalue()).decode()


class _ShipmentEditorPageShim:
    """SecurityPlanEngine'in monolit-mirası filigran çağrısı için vekil.
    (bkz. modül docstring — motor kodu değişmeden hook bağlanır)"""
    _build_letterhead_watermark_b64 = staticmethod(build_letterhead_watermark_b64)


def _install_watermark_hook() -> None:
    import webcore.engines as _eng
    if not hasattr(_eng, "ShipmentEditorPage"):
        _eng.ShipmentEditorPage = _ShipmentEditorPageShim


_install_watermark_hook()
