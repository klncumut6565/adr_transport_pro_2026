"""Güvenlik (Emniyet) Planı — masaüstündeki SafetyPlansPage'in web karşılığı
(ADR 1.10.3). Faz 2b.

Kayıtlı bir sevkiyat seçilir; kalemleri SecurityPlanEngine ile
değerlendirilerek emniyet planı gerekip gerekmediği, gerekçeleri ve
kalem bazlı detaylar gösterilir.
"""
import streamlit as st

from sayfalar._ortak import db
from webcore.engines import ADREngine, SecurityPlanEngine
from webcore.models import ShipmentItem

st.title("🛡 Güvenlik Planı — ADR 1.10.3")
st.caption("Seçilen sevkiyatın kalemlerini ADR Madde 1.10.3 (Tablo 1.10.3.1.2 / "
           "1.10.3.1.3) hükümlerine göre değerlendirir.")

d = db()
sevkiyatlar = d.get_shipments_with_details(limit=500)

if not sevkiyatlar:
    st.info("Henüz kayıtlı sevkiyat yok. Önce Sevkiyatlar sayfasından bir "
            "sevkiyat oluşturun.")
    st.stop()

secenekler = {s["id"]: f"{s.get('document_no') or '(belge no yok)'} — "
                        f"{s.get('sender_name') or '—'} → {s.get('receiver_name') or '—'}"
              for s in sevkiyatlar}

secili_id = st.selectbox("Değerlendirilecek sevkiyat", list(secenekler),
                          format_func=lambda i: secenekler[i])

TRANSPORT_MODES = {"ambalaj": "Ambalaj", "tank": "Tank (litre)", "dokme": "Dökme Yük (kg)"}
secili_mod = st.selectbox(
    "Sınıf 7 (radyoaktif) modu", list(TRANSPORT_MODES),
    format_func=lambda k: TRANSPORT_MODES[k],
    help="Yalnızca Sınıf 7 kalemler için geçerlidir. Diğer tüm kalemlerin "
         "taşıma modu kendi ambalaj türünden (Tank/Dökme/Ambalaj) otomatik belirlenir.")

kalem_dictler = d.get_shipment_items(secili_id)
items = [ShipmentItem(**dict(vars(k))) for k in kalem_dictler]

if not items:
    st.warning("Bu sevkiyatta henüz kimyasal kalemi yok — değerlendirme yapılamaz.")
    st.stop()

st.divider()
st.subheader("Sevkiyat Kalemleri")
for k in items:
    st.write(f"• UN{k.un_number} — {k.proper_name} "
             f"(Sınıf {k.class_code or '—'}, PG{k.packing_group or '—'}, "
             f"{k.packaging_type or '—'}, {k.net_quantity} {k.unit})")

st.divider()

if st.button("🔍 Emniyet Planı Gereksinimini Hesapla", type="primary", use_container_width=True):
    puan, plaka_gerekli, _detay = ADREngine.calculate_1136_points(items)
    sonuc = SecurityPlanEngine.check(items, transport_mode=secili_mod,
                                      total_1136_points=puan)
    st.session_state["gp_sonuc"] = (puan, sonuc)

if "gp_sonuc" in st.session_state:
    puan, sonuc = st.session_state["gp_sonuc"]

    st.metric("Toplam 1.1.3.6 Puanı", f"{puan:.0f}")

    if sonuc["required"]:
        st.error("🛡 EMNİYET PLANI GEREKLİ (ADR 1.10.3)")
    elif sonuc["exempt"]:
        st.success("✅ Emniyet planı gerekmiyor (1.10.4 / eşik altı muafiyeti)")
    else:
        st.warning("Durum net değil — detayları inceleyin.")

    if sonuc["reasons"]:
        st.markdown("**Gereklilik sebepleri:**")
        for r in sonuc["reasons"]:
            st.error(f"• {r}")

    if sonuc.get("class7_ratio") is not None:
        st.caption(f"Sınıf 7 radyoaktif eşik oranı (∑Ai/Ti): {sonuc['class7_ratio']:.3f}")

    if sonuc["details"]:
        with st.expander("Kalem bazlı değerlendirme detayı", expanded=False):
            for det in sonuc["details"]:
                st.text(det)


    st.divider()
    st.subheader("📄 PDF Raporu")
    from webcore.pdf import html_to_pdf_bytes  # hook'u da kurar
    from sayfalar._ortak import kullanici

    logo_b64 = d.get_setting("antet_logo_b64") or ""
    hazirlayan = kullanici().get("full_name") or kullanici().get("username", "")
    try:
        html = SecurityPlanEngine.generate_inventory_review_html(
            company_name=d.get_setting("firma_adi") or "",
            prepared_by=hazirlayan, approved_by=hazirlayan,
            screen_result=sonuc, logo_b64=logo_b64)
        pdf = html_to_pdf_bytes(html)
        st.download_button("⬇️ Emniyet Değerlendirme PDF'ini indir", data=pdf,
                           file_name="emniyet_plani_degerlendirme.pdf",
                           mime="application/pdf", use_container_width=True)
    except ImportError:
        st.info("PDF üretimi için sunucuda WeasyPrint gerekli "
                "(requirements.txt + packages.txt ile Cloud'da otomatik kurulur).")
    except Exception as exc:
        st.error(f"PDF üretilemedi: {exc}")
