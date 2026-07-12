"""ADR Taşıma Evrakı HTML şablonu — Faz 3b.

Monolit ShipmentEditorPage._build_print_html'den (579 satır) SATIRI SATIRINA
taşındı. Tek dönüşüm: self.* erişimleri parametrelere eşlendi (envanter:
db, items[ShipmentItem], document_no/date, sender/receiver/driver/vehicle,
status_text, notes). HTML/CSS şablonunun kendisi ve alan yerleşimi
DEĞİŞMEDİ — masaüstünün ürettiği evrakla görsel eşitlik hedeflenir.
PDF'e çevirmek için: webcore.pdf.html_to_pdf_bytes(html).
"""

from __future__ import annotations

import base64
import logging

from datetime import datetime, timedelta

from .constants import APP_VERSION, MAX_1136_POINTS
from .models import ExemptionType
from .engines import ADREngine, SecurityPlanEngine
from .pdf import build_letterhead_watermark_b64


def build_transport_document_html(*, db, items, document_no: str,
                                  document_date_str: str, sender=None,
                                  receiver=None, driver=None, vehicle=None,
                                  status_text: str = "", notes: str = "") -> str:
    """
    Profesyonel A4 tek sayfa ADR taşıma evrakı.
    - Gönderici ve Alıcı: ayrı çerçeveli kutucuklar (yan yana)
    - İmza/Kaşe: Gönderici + Sürücü (2 kutu, yalnızca Ad Soyad)
    - ADR uyumluluk özeti compact tek satır şerit
    - Ürün tablosu compact — A4'e sığacak şekilde
    - vehicle.carrier_name hatası düzeltildi (hasattr güvenli)
    - Gözü yormayan beyaz/gri ton, minimal çizgi
    """
    import html as _h
    from datetime import timedelta
    import qrcode  # <--- BURADA OLMALI
    import io      # <--- BURADA OLMALI
    import base64
    
    
    def esc(v):
        return _h.escape(str(v)) if v else ""

    sender   = sender
    receiver = receiver
    driver   = driver
    vehicle  = vehicle
    packaging_types = [item.packaging_type for item in items]
    report   = ADREngine.generate_adr_report(items, driver, vehicle, packaging_types)
    doc_info = {'document_no': document_no, 'date': document_date_str}
    
   


    logo_b64 = db.get_company_logo_b64()
    show_qr = db.get_setting("doc_show_qr") == "1" # QR ayarını çektik

    # [v4.2] Antetli kagit filigrani: firma logosu (soluk) + onaylanmamis
    # evrakta capraz TASLAK yazisi. Tek PNG olarak onceden islenir.
    # monolitteki hasattr(self, "lbl_status") savunması parametreye çevrildi
    _status_text = status_text.upper() if status_text else ""
    is_approved = "ONAYLANDI" in _status_text
    letterhead_b64 = build_letterhead_watermark_b64(logo_b64, is_approved)

    logo_html = ""
    if logo_b64:
        logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="max-width:100px; max-height:45px; object-fit:contain;">'

    qr_html = ""
    if show_qr:
        # ── vCard kartvizit verisi oluştur ──────────────────────────────
        co_name  = db.get_setting("doc_company_name")  or ""
        co_addr  = db.get_setting("doc_company_address") or ""
        co_phone = db.get_setting("doc_company_phone") or ""
        co_email = db.get_setting("doc_company_email") or ""
        co_web   = db.get_setting("doc_company_website") or ""

        vcard_lines = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"FN:{co_name}",
            f"ORG:{co_name}",
        ]
        if co_addr:
            vcard_lines.append(f"ADR;TYPE=WORK:;;{co_addr};;;;TR")
        # Birden fazla numara varsa (örn. "0850 515 0000 - 0543 271 63 77") her birini ekle
        phone_parts = [p.strip() for p in co_phone.replace("–", "-").split("-") if p.strip()]
        for ph in phone_parts:
            vcard_lines.append(f"TEL;TYPE=WORK,VOICE:{ph}")
        if co_email:
            vcard_lines.append(f"EMAIL;TYPE=WORK:{co_email}")
        if co_web:
            vcard_lines.append(f"URL:{co_web}")
        vcard_lines.append("NOTE:ADR Tehlikeli Madde Danışmanlık")
        vcard_lines.append("END:VCARD")
        vcard_data = "\r\n".join(vcard_lines)

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=1,
        )
        qr.add_data(vcard_data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        qr_img.save(buffer, format="PNG")
        qr_b64 = base64.b64encode(buffer.getvalue()).decode()
        qr_html = (
            f'<img src="data:image/png;base64,{qr_b64}" '
            f'width="55" height="55" '
            f'style="width:55px;height:55px;display:block;" '
            f'title="Firma Kartviziti">'
        )
        
    logo_html = ""

    if logo_b64:
        # max-width ve max-height ile logonun alanı aşması engellenir
        logo_html = f'''
        <img src="data:image/png;base64,{logo_b64}" 
             style="max-width:60px; max-height:20px; width:auto; height:auto; object-fit:contain;">
        '''
        logo_html = f"""
        <img src="data:image/png;base64,{logo_b64}"
            style="
                max-width:100px;
                max-height:45px;
                object-fit:contain;
            ">
        """

    # ── Renk sabitleri (minimal, gözü yormayan palet) ─────────────────
    NAVY      = "#1C3557"
    NAVY_LITE = "#EEF3FA"
    STEEL     = "#4A6FA5"
    RULE      = "#C8D6E8"
    TXT_MAIN  = "#1A1A2E"
    TXT_MUTED = "#5A6478"
    TXT_LITE  = "#8A94A6"
    ROW_ALT   = "#F7F9FC"
    GREEN     = "#0A6B2E"
    GREEN_BG  = "#E8F5EE"
    RED       = "#B91C1C"
    RED_BG    = "#FEF2F2"
    AMBER     = "#92400E"
    AMBER_BG  = "#FFFBEB"
    WARN_BG   = "#FEF3C7"

    # ── Muafiyet / puan şeridi hesaplamaları ─────────────────────────
    aktif_html = [i for i in items if (i.net_quantity or 0) > 0]
    tc4_only = aktif_html and all(
        str(getattr(i, "transport_category", "")).strip().split()[0:1] == ["4"]
        or i.is_lq or i.is_eq
        for i in aktif_html
    )
    has_exemption = (report.exemption_type != ExemptionType.NONE.value) or tc4_only

    # Puan şeridi gösterimi: TC=4/LQ/EQ → "Sınırsız"
    # pts > 1000 → şerit tamamen gizlenir (has_exemption=False)
    if tc4_only:
        pts_display = "Sınırsız"
        pts_sub     = "ADR 3.4 — Miktar Muafiyeti Sınırsız"
        bar_pct     = 0
        bar_color   = GREEN
    elif report.total_points > MAX_1136_POINTS:
        # 1000 puan aşıldı → şeridi gizle
        has_exemption = False
        pts_display = ""
        pts_sub     = ""
        bar_pct     = 0
        bar_color   = TXT_MUTED
    elif report.total_points > 0:
        pts_display = f"{report.total_points:.0f}"
        pts_sub     = f"{report.total_points:.0f} / {MAX_1136_POINTS} puan"
        bar_pct     = min(100, int(report.total_points / MAX_1136_POINTS * 100))
        bar_color   = RED if report.orange_plate_required else GREEN
    else:
        pts_display = "—"
        pts_sub     = "Taşıma Kategorisi girilmemiş"
        bar_pct     = 0
        bar_color   = TXT_MUTED

    # ── Emniyet planı gerekli mi? ──────────────────────────────────────
    try:
        _sp_items = [i for i in items if (i.net_quantity or 0) > 0]
        if not _sp_items:
            security_plan_required = False
            security_plan_reasons  = []
        else:
            _sp_pts, _, _ = ADREngine.calculate_1136_points(_sp_items)
            _sp_result = SecurityPlanEngine.check(_sp_items, total_1136_points=_sp_pts)
            security_plan_required = _sp_result.get("required", False)
            security_plan_reasons  = _sp_result.get("reasons", [])
    except Exception:
        security_plan_required = False
        security_plan_reasons  = []

    # ── ADR özet değerleri ────────────────────────────────────────────
    op_color = RED    if report.orange_plate_required else GREEN
    op_bg    = RED_BG if report.orange_plate_required else GREEN_BG
    op_text  = "ZORUNLU ⚠" if report.orange_plate_required else "GEREKMEZ ✓"

    wi_color = AMBER    if report.written_instructions_required else GREEN
    wi_bg    = AMBER_BG if report.written_instructions_required else GREEN_BG
    wi_text  = "ZORUNLU" if report.written_instructions_required else "GEREKMEZ ✓"

    ac_color = AMBER    if report.driver_adr_required else GREEN
    ac_bg    = AMBER_BG if report.driver_adr_required else GREEN_BG
    ac_text  = "ZORUNLU" if report.driver_adr_required else "GEREKMEZ ✓"

    bar_pct   = min(100, int(report.total_points / MAX_1136_POINTS * 100))
    bar_color = RED if report.orange_plate_required else GREEN

    # ── SRC5 durumu ───────────────────────────────────────────────────
    src5_text  = "Sürücü seçilmemiş"
    src5_color = TXT_MUTED
    if driver:
        has_src5 = bool(getattr(driver, 'src5_no', None) and driver.src5_no.strip())
        if has_src5:
            try:
                exp = datetime.strptime(driver.src5_expiry, "%Y-%m-%d")
                if exp < datetime.now():
                    src5_text  = f"GEÇERSİZ — Süre Dolmuş ({driver.src5_expiry})"
                    src5_color = RED
                elif exp < datetime.now() + timedelta(days=60):
                    src5_text  = f"UYARI — {(exp - datetime.now()).days} gün kaldı ({driver.src5_expiry})"
                    src5_color = AMBER
                else:
                    all_lq_eq  = all(i.is_lq or i.is_eq for i in items) if items else False
                    below_1136 = report.total_points <= MAX_1136_POINTS
                    if all_lq_eq:
                        src5_text = f"GEÇERLİ — LQ/EQ muafiyeti (ADR 3.4/3.5)"
                    elif below_1136 and not report.orange_plate_required:
                        src5_text = f"GEÇERLİ — 1.1.3.6 muafiyeti kapsamında ADR belgesi gerekmez"
                    else:
                        src5_text = f"GEÇERLİ — Tam ADR: Sürücü ADR sertifikası zorunlu"
                    src5_color = GREEN
            except Exception:
                src5_text  = f"GEÇERLİ — SRC5: {getattr(driver, 'src5_no', '')}"
                src5_color = GREEN
        else:
            src5_text  = "SRC5 belgesi girilmemiş"
            src5_color = RED

    # ── Ürün satırları (compact) ──────────────────────────────────────
    item_rows = ""
    for idx, item in enumerate(items, 1):
        bg = "#FFFFFF" if idx % 2 == 1 else ROW_ALT
        class_bg, class_fg = ADREngine.get_class_color(item.class_code)
        badges = ""
        if item.is_lq:
            badges += ('<span style="border:1px solid #166534;color:#166534;padding:1px 4px;'
                       'border-radius:2px;font-size:6.5pt;margin-left:3px;">LQ</span>')
        if item.is_eq:
            badges += ('<span style="border:1px solid #1e3a8a;color:#1e3a8a;padding:1px 4px;'
                       'border-radius:2px;font-size:6.5pt;margin-left:2px;">EQ</span>')
        item_rows += f"""
        <tr style="background:{bg};">
          <td style="text-align:center;color:{TXT_LITE};font-size:7.5pt;width:3%;">{idx}</td>
          <td style="color:{NAVY};white-space:nowrap;width:8%;font-size:8pt;">UN&nbsp;{esc(item.un_number)}</td>
          <td style="word-break:break-word;width:28%;font-size:8pt;">{esc(item.proper_name)}{badges}</td>
          <td style="text-align:center;width:6%;">
            <span style="border:1px solid {class_fg};color:{class_fg};padding:1px 5px;
              border-radius:2px;font-size:7.5pt;">{esc(item.class_code)}</span>
          </td>
          <td style="text-align:center;width:4%;font-size:8pt;">{esc(item.packing_group) or "—"}</td>
          <td style="text-align:center;width:5%;font-size:8pt;color:{NAVY};">{esc(item.tunnel_code) or "—"}</td>
          <td style="font-size:7.5pt;width:14%;color:{TXT_MUTED};">{esc(item.packaging_type) or "—"}</td>
          <td style="text-align:center;width:5%;font-size:8pt;">{item.packaging_count}</td>
          <td style="text-align:right;white-space:nowrap;width:9%;font-size:8pt;">{item.net_quantity}&nbsp;{esc(item.unit)}</td>
        </tr>"""

    if not item_rows:
        item_rows = (f'<tr><td colspan="9" style="text-align:center;color:{TXT_LITE};'
                     f'padding:14px;font-size:8.5pt;">Ürün eklenmemiş</td></tr>')

    # ── Uyumsuzluk uyarısı (varsa) ────────────────────────────────────
    compat_html = ""
    if report.compatibility_errors:
        errs = "".join(f'<li style="margin:2px 0;font-size:8pt;">{esc(e)}</li>'
                       for e in report.compatibility_errors)
        compat_html = f"""
        <div style="margin:6px 0 0;padding:6px 10px;
          border-left:3px solid {RED};border-radius:0 3px 3px 0;">
          <span style="color:{RED};font-size:7.5pt;">⚠ UYUMSUZLUK UYARILARI</span>
          <ul style="margin:3px 0 0 14px;padding:0;color:{RED};">{errs}</ul>
        </div>"""

    # ── Notlar ────────────────────────────────────────────────────────
    notes_html = ""
    notes_text = notes.strip()
    if notes_text:
        notes_html = f"""
        <div style="margin-top:8px;padding:6px 10px;
          border-left:3px solid #D97706;border-radius:0 3px 3px 0;page-break-inside:avoid;">
          <span style="color:#92400E;font-size:7.5pt;">NOT:</span>
          <span style="color:{TXT_MUTED};font-size:8pt;"> {esc(notes_text)}</span>
        </div>"""

    # ── İmza / Kaşe — 2 kutu: Gönderici + Sürücü ────────────────────
    sender_name  = esc(sender.name)  if sender  else "—"
    driver_name  = esc(driver.full_name) if driver else "—"

    signature_section = f"""
    <table style="width:100%;border-collapse:separate;border-spacing:8px 0;
      margin-top:5px;page-break-inside:avoid;">
      <tr>
        <!-- GÖNDERİCİ İMZA KUTUSU -->
        <td style="width:50%;vertical-align:top;">
          <div style="border:1px solid {RULE};border-radius:4px;overflow:hidden;">
            <div style="border-bottom:1px solid {RULE};padding:4px 8px;
              font-size:6.5pt;letter-spacing:0.8px;color:{NAVY};">
              GÖNDERİCİ / YÜKLETEN
            </div>
            <div style="padding:8px 10px;">
              <div style="font-size:7pt;color:{TXT_LITE};margin-bottom:1px;">Firma:</div>
              <div style="font-size:8.5pt;color:{TXT_MAIN};margin-bottom:10px;">
                {sender_name}
              </div>
              <div style="font-size:7pt;color:{TXT_LITE};margin-bottom:2px;">Ad Soyad:</div>
              <div style="border-bottom:1px solid {RULE};min-height:22px;margin-bottom:10px;"></div>
              <div style="font-size:7pt;color:{TXT_LITE};margin-bottom:2px;">İmza / Kaşe:</div>
              <div style="border:1px solid {RULE};min-height:80px;border-radius:2px;margin-bottom:10px;"></div>
              <div style="font-size:6pt;color:{TXT_LITE};line-height:1.4;border-top:1px solid {RULE};padding-top:4px;">
                Tehlikeli maddelerin sınıflandırılması, paketlenmesi ve etiketlenmesinin
                ADR hükümlerine uygun olduğunu beyan ederim. (ADR 5.4.1.1.1/f)
              </div>
            </div>
          </div>
        </td>
        <!-- SÜRÜCÜ İMZA KUTUSU -->
        <td style="width:50%;vertical-align:top;">
          <div style="border:1px solid {RULE};border-radius:4px;overflow:hidden;">
            <div style="border-bottom:1px solid {RULE};padding:4px 8px;
              font-size:6.5pt;letter-spacing:0.8px;color:{NAVY};">
              SÜRÜCÜ
            </div>
            <div style="padding:8px 10px;">
              <div style="font-size:7pt;color:{TXT_LITE};margin-bottom:1px;">Sürücü:</div>
              <div style="font-size:8.5pt;color:{TXT_MAIN};margin-bottom:10px;">
                {driver_name}
              </div>
              <div style="font-size:7pt;color:{TXT_LITE};margin-bottom:2px;">Ad Soyad:</div>
              <div style="border-bottom:1px solid {RULE};min-height:22px;margin-bottom:10px;"></div>
              <div style="font-size:7pt;color:{TXT_LITE};margin-bottom:2px;">İmza:</div>
              <div style="border:1px solid {RULE};min-height:80px;border-radius:2px;margin-bottom:10px;"></div>
              <div style="font-size:6pt;color:{TXT_LITE};line-height:1.4;border-top:1px solid {RULE};padding-top:4px;">
                Yükü teslim aldığımı ve taşımanın ADR hükümlerine uygun olarak
                gerçekleştirileceğini kabul ederim.
              </div>
            </div>
          </div>
        </td>
      </tr>
    </table>"""

    # ── HTML belgesi ──────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<style>
  @page {{ size: A4 portrait; margin: 8mm 10mm; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
font-family: 'Segoe UI', Arial, Helvetica, sans-serif;
font-size: 7.5pt;
color: {TXT_MAIN};
background: #ffffff;
line-height: 1.3;
  }}
  table {{ border-collapse: collapse; width: 100%; }}
  .rule {{ border-top: 1px solid {RULE}; margin: 5px 0; }}
  .sec-head {{
font-size: 6.5pt;
font-weight: normal;
letter-spacing: 1.2px;
text-transform: uppercase;
color: {NAVY};
border-bottom: 1.5px solid {NAVY};
padding-bottom: 2px;
margin: 5px 0 4px;
  }}
  .items-table th {{
background: #ffffff;
color: {NAVY};
border-bottom: 1.5px solid {NAVY};
font-size: 6.5pt;
text-align: center;
padding: 3px 4px;
white-space: nowrap;
font-weight: normal;
letter-spacing: 0.3px;
  }}
  .items-table td {{
border-bottom: 1px solid {RULE};
padding: 2px 4px;
vertical-align: middle;
font-weight: normal;
  }}
  .badge {{
display: inline-block;
padding: 1px 5px;
border-radius: 3px;
font-weight: normal;
font-size: 7pt;
  }}
  .no-break {{ page-break-inside: avoid; }}
  strong {{ font-weight: normal; }}
  b {{ font-weight: normal; }}
  i, em {{ font-style: normal; }}
</style>
</head>
<body>
{'<table width="100%" style="border-collapse:separate;background-image:url(data:image/png;base64,' + letterhead_b64 + ');background-repeat:no-repeat;background-position:center top;"><tr><td style="padding:0;">' if letterhead_b64 else ''}

<!-- ══════════════════════════ BAŞLIK ══════════════════════════════════ -->
<table style="margin-bottom:5px;border-bottom:2px solid {NAVY};padding-bottom:5px; width:100%; table-layout:fixed;">
  <tr>
<td style="width:20%; text-align:left; vertical-align:middle; padding:5px;">
    <div style="max-width:80px; overflow:hidden;">
        {logo_html}
    </div>
</td>

<td style="width:60%; text-align:center; padding-bottom:2px; vertical-align:middle;">
  <div style="font-size:12pt;color:{NAVY};letter-spacing:0.8px;">ADR TEHLİKELİ MADDE TAŞIMA EVRAKI</div>
  <div style="font-size:7pt;color:{TXT_MUTED};margin-top:2px;">Karayolu İle Tehlikeli Madde Taşıma Belgesi &nbsp;·&nbsp; ADR 5.4.1</div>
  <div style="font-size:7pt;color:{TXT_MUTED};margin-top:2px;">Tarih: {esc(doc_info.get('date',''))} &nbsp;|&nbsp; Evrak No: {esc(doc_info.get('document_no',''))}</div>
</td>

<td style="width:20%; text-align:right; vertical-align:middle; padding:5px;">
    <div style="display:inline-block; max-width:60px;">
        {qr_html}
    </div>
</td>
  </tr>
</table>

<!-- ══════════════════════ GÖNDERİCİ / ALICI ══════════════════════════ -->
<div class="no-break">
<div class="sec-head">Gönderici ve Alıcı Bilgileri</div>
<table style="border-collapse:separate;border-spacing:6px 0;width:100%;">
  <tr>
<!-- GÖNDERİCİ -->
<td style="width:49%;vertical-align:top;border:1px solid {RULE};border-radius:4px;padding:0;overflow:hidden;">
  <div style="border-bottom:1px solid {RULE};padding:4px 8px;font-size:6.5pt;letter-spacing:0.8px;color:{NAVY};">
    GÖNDERİCİ
  </div>
  <div style="padding:6px 8px;">
    <div style="font-size:8.5pt;color:{TXT_MAIN};">
      {esc(sender.name) if sender else '—'}
    </div>
    <div style="font-size:7pt;color:{TXT_MUTED};margin-top:2px;">
      {esc(sender.address) if sender else ''}
      {(' &nbsp;·&nbsp; ' + esc(sender.city)) if sender and sender.city else ''}
      {(' / ' + esc(sender.district)) if sender and getattr(sender,'district','') else ''}
    </div>
    {('<div style="font-size:7pt;color:' + TXT_MUTED + ';margin-top:2px;">Tel: ' + esc(getattr(sender,'phone','')) + '</div>') if sender and getattr(sender,'phone','') else ''}
  </div>
</td>
<!-- ALICI -->
<td style="width:49%;vertical-align:top;border:1px solid {RULE};border-radius:4px;padding:0;overflow:hidden;">
  <div style="border-bottom:1px solid {RULE};padding:4px 8px;font-size:6.5pt;letter-spacing:0.8px;color:{NAVY};">
    ALICI
  </div>
  <div style="padding:6px 8px;">
    <div style="font-size:8.5pt;color:{TXT_MAIN};">
      {esc(receiver.name) if receiver else '—'}
    </div>
    <div style="font-size:7pt;color:{TXT_MUTED};margin-top:2px;">
      {esc(receiver.address) if receiver else ''}
      {(' &nbsp;·&nbsp; ' + esc(receiver.city)) if receiver and receiver.city else ''}
      {(' / ' + esc(receiver.district)) if receiver and getattr(receiver,'district','') else ''}
    </div>
    {('<div style="font-size:7pt;color:' + TXT_MUTED + ';margin-top:2px;">Tel: ' + esc(getattr(receiver,'phone','')) + '</div>') if receiver and getattr(receiver,'phone','') else ''}
  </div>
</td>
  </tr>
</table>
</div>

<!-- ══════════════════════ ARAÇ VE SÜRÜCÜ ══════════════════════════════ -->
<div class="no-break">
<div class="sec-head">Araç ve Sürücü Bilgileri</div>
<table style="border:1px solid {RULE};">
  <tr>
<td style="padding:4px 8px;font-size:6.5pt;color:{NAVY};border-right:1px solid {RULE};width:10%;white-space:nowrap;">SÜRÜCÜ</td>
<td style="padding:4px 8px;width:40%;font-size:8pt;border-right:1px solid {RULE};">
  {esc(driver.full_name) if driver else '—'}
  {(' &nbsp;·&nbsp; SRC5: ' + esc(driver.src5_no)) if driver and getattr(driver,'src5_no','') else ''}
</td>
<td style="padding:4px 8px;font-size:6.5pt;color:{NAVY};border-right:1px solid {RULE};width:10%;white-space:nowrap;">ARAÇ</td>
<td style="padding:4px 8px;width:40%;font-size:8pt;">
  {esc(vehicle.plate) if vehicle else '—'}
</td>
  </tr>
</table>
</div>

<!-- ══════════════════════ TAŞINAN MADDELER ════════════════════════════ -->
<div class="sec-head">Taşınan Tehlikeli Maddeler</div>
<table class="items-table">
  <thead>
<tr>
  <th style="width:3%;">#</th>
  <th style="width:8%;">UN No</th>
  <th style="text-align:left;width:28%;">Uygun Sevkiyat Adı</th>
  <th style="width:6%;">Sınıf</th>
  <th style="width:4%;">PG</th>
  <th style="width:5%;">Tünel</th>
  <th style="width:13%;">Ambalaj Türü</th>
  <th style="width:5%;">Adet</th>
  <th style="width:13%;">Net Mik.</th>
</tr>
  </thead>
  <tbody>
{item_rows}
  </tbody>
</table>
{compat_html}

<!-- ══════════════════════ ADR UYUMLULUK ŞERİDİ (sadece muafiyet varsa) ═══════ -->
{"" if not has_exemption else f"""
<div class='no-break' style='margin-top:5px;'>
<table style='border:1px solid {RULE};border-radius:3px;overflow:hidden;'>
  <tr>
<td style='padding:4px 8px;border-right:1px solid {RULE};width:22%;vertical-align:top;'>
  <div style='font-size:6pt;color:{NAVY};letter-spacing:0.5px;'>1.1.3.6 MİKTAR MUAFİYETİ</div>
  <div style='font-size:10pt;color:{bar_color};line-height:1.1;margin-top:1px;'>
    {pts_display}
  </div>
  <div style='font-size:6pt;color:{TXT_MUTED};margin-top:1px;'>{pts_sub}</div>
  <div style='background:#E4EAF2;border-radius:3px;height:4px;margin-top:3px;'>
    <div style='background:{bar_color};width:{bar_pct}%;height:4px;border-radius:3px;'></div>
  </div>
</td>
<td style='padding:4px 8px;border-right:1px solid {RULE};width:19%;vertical-align:top;'>
  <div style='font-size:6pt;color:{TXT_MUTED};'>TURUNCU PLAKA</div>
  <span class='badge' style='border:1px solid {op_color};color:{op_color};margin-top:2px;
    display:inline-block;font-size:7pt;'>{op_text}</span>
</td>
<td style='padding:4px 8px;border-right:1px solid {RULE};width:19%;vertical-align:top;'>
  <div style='font-size:6pt;color:{TXT_MUTED};'>YAZILI TALİMAT</div>
  <span class='badge' style='border:1px solid {wi_color};color:{wi_color};margin-top:2px;
    display:inline-block;font-size:7pt;'>{wi_text}</span>
</td>
<td style='padding:4px 8px;border-right:1px solid {RULE};width:19%;vertical-align:top;'>
  <div style='font-size:6pt;color:{TXT_MUTED};'>ADR SERTİFİKA</div>
  <span class='badge' style='border:1px solid {ac_color};color:{ac_color};margin-top:2px;
    display:inline-block;font-size:7pt;'>{ac_text}</span>
</td>
<td style='padding:4px 8px;width:21%;vertical-align:top;'>
  <div style='font-size:6pt;color:{TXT_MUTED};'>SRC5 / MUAFİYET</div>
  <div style='font-size:7pt;color:{src5_color};margin-top:2px;line-height:1.3;'>{esc(src5_text)}</div>
</td>
  </tr>
  <tr>
<td colspan='5' style='padding:3px 8px;border-top:1px solid {RULE};font-size:7pt;color:{TXT_MUTED};'>
  Muafiyet: {esc(report.exemption_type)}
</td>
  </tr>
</table>
</div>
"""}

{notes_html}

<!-- ══════════════════════ EMNİYET PLANI UYARISI (koşullu) ═══════════ -->
{"" if not security_plan_required else f'''
<div class='no-break' style='margin-top:6px;padding:8px 12px;
  border-left:4px solid #B91C1C;border-radius:0 4px 4px 0;'>
  <div style='font-size:8pt;color:#B91C1C;margin-bottom:4px;'>
ADR 1.10.3 — EMNİYET PLANI ZORUNLU
  </div>
  <div style='font-size:7.5pt;color:#7F1D1D;'>''' + ' &nbsp;·&nbsp; '.join(security_plan_reasons[:3]) + '''
  </div>
</div><br>
'''}

<!-- ══════════════════════ İMZA / KAŞE ════════════════════════════════ -->
<div class="sec-head" style="margin-top:6px;">İmza ve Kaşe</div>
{signature_section}

<!-- ══════════════════════ ALT BİLGİ ══════════════════════════════════ -->
<div style="margin-top:5px;padding:4px 10px;border:1px solid {RULE};
  border-radius:3px;font-size:6pt;color:{TXT_MUTED};text-align:center;">
  <br>
  Bu belge ADR Yönetmeliği Madde 5.4.1 kapsamında düzenlenmiştir.
  <br>
  <span style="font-size:5.5pt;color:{TXT_LITE};">
ADR Transport Pro {APP_VERSION} &nbsp;|&nbsp; Oluşturma: {datetime.now().strftime('%d.%m.%Y %H:%M')}
  </span>
</div>

{'</td></tr></table>' if letterhead_b64 else ''}
</body>
</html>"""
    return html

# --- DIALOGS ---
