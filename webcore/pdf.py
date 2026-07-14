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


def wrap_for_screen_preview(html: str) -> str:
    """A4 evrak şablonunu TARAYICIDA gerçek çıktıya benzer gösterir.

    Sorun 1: şablonun `@page {{ size: A4; margin: 8mm 10mm; }}` kuralı
    yalnızca yazdırma/PDF motorlarında (WeasyPrint dahil) uygulanır —
    tarayıcılar bunu EKRANDA tamamen yok sayar. Bu yüzden aynı HTML,
    Canlı Önizleme'de (components.html, normal ekran render'ı) sayfa
    genişliği/kenar boşluğu olmadan dağınık akıyor, PDF'te ise düzgün
    A4 çıkıyor — "önizleme çıktıya hiç benzemiyor" şikâyetinin sebebi.

    Sorun 2 (Umut'un tespiti — "tam sığmadı"): sabit `width: 210mm`
    (~794px), ADR Kontrol Merkezi panelinin DAR sağ sütununda (toplam
    genişliğin ~%30'u) yatay taşmaya/kırpılmaya yol açıyordu.

    Sorun 3 (Umut'un 2. tespiti): ilk düzeltme JS'i `window.addEventListener
    ('load', ...)` + birkaç setTimeout ile tetikliyordu — bu, Streamlit'in
    components.html'inin içeriği bir iframe'e `srcdoc` ile yazma biçimiyle
    ZAMANLAMA AÇISINDAN güvenilir çalışmadı. `ResizeObserver` ile
    değiştirildi.

    Sorun 4 (Umut'un 3. tespiti): `ResizeObserver`, `document.body`'yi
    izliyordu — AMA `olcekle()` fonksiyonunun KENDİSİ `sarici.style.
    height`'i DEĞİŞTİRİYORDU, bu da body'nin yüksekliğini değiştirip
    ResizeObserver'ı TEKRAR tetikliyordu (kendi kendini besleyen bir
    döngü). Küçük bir yuvarlama sapması bile bu döngüde birikip
    yüksekliğin sürekli büyümesine yol açabiliyordu — "yükseklik alanı
    çok büyük oldu, önizleme görünmüyor" şikâyetinin sebebi buydu.
    Ayrıca `margin: 0 auto` (ortalama) panel genişledikçe içeriğin sağa
    kayıyormuş HİSSİ veriyordu; artık sol kenara sabitleniyor (`margin: 0`).

    Çözüm: ResizeObserver artık `document.body` yerine `window` boyut
    değişikliğini (`resize` olayı) izliyor — bu, İÇERİĞİN KENDİ
    değişikliklerinden ASLA tetiklenmez, yalnızca panelin/pencerenin
    GERÇEKTEN yeniden boyutlandığı durumlarda tetiklenir; kendi kendini
    besleyen döngü riski yapısal olarak ortadan kalktı. Ayrıca yalnızca
    ölçek GERÇEKTEN değiştiğinde DOM'a yazılıyor (gereksiz tekrar yok).

    Çözüm (genel): sayfa A4 oranlarında (210mm) SABİT genişlikte inşa
    edilir, `transform: scale()` ile orantılı küçültülüp SOL kenara
    sabitlenir — hangi panelde gösterilirse gösterilsin (dar sağ sütun,
    tam genişlik modal, pencere yeniden boyutlandırma, vb.) her zaman
    TAMAMEN sığar ve öngörülebilir konumda kalır. PDF üretimi bu
    fonksiyonu ÇAĞIRMAZ, dolayısıyla hiç etkilenmez — html_to_pdf_bytes
    hâlâ orijinal (sarmalanmamış) HTML'i alır ve WeasyPrint @page
    kuralını olduğu gibi, tam A4 ölçeğinde uygular.
    """
    ekran_css = """
<style>
  html, body { margin: 0; padding: 0; background: #e2e2e2; overflow-x: hidden; }
  #__a4_sarici {
    width: 210mm; min-height: 10mm; margin: 0;
    transform-origin: top left;
    transform: scale(0.5);   /* JS çalışana kadar (veya hiç çalışmazsa)
                                 GÜVENLİ VARSAYILAN — hiç sığmama riski
                                 olmasın diye baştan makul bir küçültme */
    height: 149mm;            /* 0.5 ölçekte ~297mm'nin tuttuğu alan */
  }
  #__a4_sayfa {
    width: 210mm;
    min-height: 297mm;
    margin: 12px 0;
    padding: 8mm 10mm;
    box-shadow: 0 1px 8px rgba(0,0,0,.28);
    background: #ffffff;
    box-sizing: border-box;
  }
</style>
<script>
(function() {
  var sonOlcek = null;
  function olcekle() {
    var sarici = document.getElementById('__a4_sarici');
    var sayfa = document.getElementById('__a4_sayfa');
    if (!sarici || !sayfa) return;
    var mevcutGenislik = document.body.clientWidth
                        || document.documentElement.clientWidth
                        || window.innerWidth || 794;
    var dogalGenislik = sayfa.offsetWidth || 794;  // 210mm ~= 794px @96dpi
    var olcek = Math.max(0.15, Math.min(1, (mevcutGenislik - 4) / dogalGenislik));
    // DÜZELTME: ölçek gerçekten değişmediyse DOM'a hiç dokunma — bu,
    // olası bir geri besleme döngüsünü daha en baştan imkansız kılar.
    if (sonOlcek !== null && Math.abs(olcek - sonOlcek) < 0.01) return;
    sonOlcek = olcek;
    sarici.style.transform = 'scale(' + olcek + ')';
    sarici.style.height = (sayfa.offsetHeight * olcek) + 'px';
  }
  // KRİTİK: document.body'yi DEĞİL, yalnızca 'window' boyut değişikliğini
  // izliyoruz. body'yi izlemek, olcekle()'nin KENDİ height ayarının
  // body'yi değiştirip gözlemciyi TEKRAR tetiklemesine (kendi kendini
  // besleyen döngü) yol açıyordu — "yükseklik çok büyüdü" hatasının
  // asıl sebebi buydu. window resize, İÇERİK değişikliklerinden ASLA
  // tetiklenmez, yalnızca panel/pencere GERÇEKTEN yeniden boyutlanınca.
  window.addEventListener('load', olcekle);
  window.addEventListener('resize', olcekle);
  [0, 50, 150, 300, 600, 1200].forEach(function(ms) {
    setTimeout(olcekle, ms);
  });
})();
</script>
<div id="__a4_sarici"><div id="__a4_sayfa">"""
    kapanis = "</div></div>"
    if "<body" in html:
        # <body ...> etiketinin AÇILIŞINDAN SONRAKİ ilk noktaya sarıcıyı ekle,
        # gövde içeriğinin SONUNA (</body>'den önce) kapanışı ekle
        i = html.index(">", html.index("<body")) + 1
        html = html[:i] + ekran_css + html[i:]
        j = html.rindex("</body>")
        html = html[:j] + kapanis + html[j:]
        return html
    return ekran_css + html + kapanis


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
