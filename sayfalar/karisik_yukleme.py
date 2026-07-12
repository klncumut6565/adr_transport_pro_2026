"""Karışık Yükleme Kontrolü — masaüstündeki ADR MIX PRO'nun web karşılığı
(ADR 7.5.2). Faz 2b.

Bir sevkiyata bağlı olmadan, hızlıca "bu maddeler birlikte taşınabilir mi?"
sorusuna cevap vermek için kullanılır. Kimyasal Veritabanı'ndan madde arayıp
geçici bir listeye ekler, ADREngine.check_compatibility ile ADR 7.5.2
segregasyon kurallarına göre kontrol eder ve en kısıtlayıcı tünel kodunu
gösterir.
"""
import streamlit as st

from sayfalar._ortak import db, kimyasal_etiket
from webcore.engines import ADREngine
from webcore.models import ShipmentItem

st.title("🧯 Karışık Yükleme Kontrolü")
st.caption("ADR 7.5.2 — Birlikte taşınacak maddelerin segregasyon uyumluluğunu kontrol edin.")

if "mix_kalemler" not in st.session_state:
    st.session_state["mix_kalemler"] = []

kalemler = st.session_state["mix_kalemler"]

st.subheader("Madde Ekle")
with st.expander("➕ Kimyasal ara ve ekle", expanded=not kalemler):
    arama = st.text_input("UN numarası veya madde adı ile ara", key="mix_arama")
    bulunanlar = db().search_chemicals(arama, limit=15) if arama else []
    if bulunanlar:
        secili = st.selectbox(
            "Bulunan maddeler", bulunanlar,
            format_func=kimyasal_etiket,
            key="mix_secili")
        if st.button("Listeye ekle", type="primary"):
            zaten_var = any(
                k["un_number"] == secili.un_number
                and k["classification_code"] == secili.classification_code
                and k["packing_group"] == secili.packing_group
                for k in kalemler)
            if zaten_var:
                st.warning(f"UN{secili.un_number} (bu sınıflandırma/PG ile) zaten listede.")
            else:
                kalemler.append({
                    "un_number": secili.un_number,
                    "proper_name": secili.proper_shipping_name_tr or secili.proper_shipping_name_en,
                    "class_code": secili.class_code,
                    "packing_group": secili.packing_group,
                    "tunnel_code": secili.tunnel_code,
                    "segregation_group": secili.segregation_group,
                    "classification_code": secili.classification_code,
                    "transport_category": secili.transport_category,
                })
                st.session_state["mix_kalemler"] = kalemler
                st.rerun()
    elif arama:
        st.info("Eşleşen madde bulunamadı.")

st.divider()
st.subheader("Kontrol Edilecek Maddeler")

if kalemler:
    for i, k in enumerate(kalemler):
        c1, c2, c3, c4, c5 = st.columns([1, 3, 1.3, 1.5, 0.6])
        c1.write(f"UN{k['un_number']}")
        c2.write(k["proper_name"])
        c3.write(" / ".join(filter(None, [
            k["class_code"], k["classification_code"],
            f"PG{k['packing_group']}" if k["packing_group"] else ""])) or "—")
        c4.write(f"Tünel: {k['tunnel_code'] or '—'}")
        if c5.button("🗑️", key=f"mix_sil_{i}"):
            kalemler.pop(i)
            st.session_state["mix_kalemler"] = kalemler
            st.rerun()

    if st.button("🧹 Listeyi temizle"):
        st.session_state["mix_kalemler"] = []
        st.rerun()

    st.divider()
    if st.button("🔍 Uyumluluğu Kontrol Et", type="primary", use_container_width=True):
        if len(kalemler) < 2:
            st.info("Kontrol için en az 2 madde eklemelisiniz.")
        else:
            items = [ShipmentItem(**k) for k in kalemler]
            uyumsuzluklar = ADREngine.check_compatibility(items)
            tunel = ADREngine.calculate_tunnel_restriction(items)

            if uyumsuzluklar:
                for u in uyumsuzluklar:
                    st.error(f"⚠️ {u}")
            else:
                st.success("✅ Seçili maddeler arasında bilinen bir segregasyon "
                            "uyumsuzluğu tespit edilmedi (ADR 7.5.2).")

            st.metric("En kısıtlayıcı tünel kısıtlama kodu", tunel)
            st.caption("Not: Bu kontrol Kimyasal Veritabanı'ndaki sınıf ve "
                       "segregasyon grubu bilgisine dayanır; nihai karar için "
                       "ADR 7.5.2 tablosu ve madde SDS'i esas alınmalıdır.")
else:
    st.info("Henüz madde eklenmedi. Yukarıdan arama yaparak ekleyin.")
