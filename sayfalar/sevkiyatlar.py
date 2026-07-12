"""Sevkiyatlar — liste görünümü + editöre yönlendirme (Faz 2b)."""
import streamlit as st
from sayfalar._ortak import db
from webcore.models import DocumentStatus

st.title("🚛 Sevkiyatlar")

# [DÜZELTİLDİ] Süzgeç seçenekleri artık DocumentStatus enum'ının gerçek
# (ASCII) DB değerleriyle eşleşiyor; önceki Türkçe karakterli seçenekler
# ("Onaylandı" vb.) veritabanındaki "Onaylandi" ile hiç eşleşmiyordu.
DURUM_ETIKET = {
    "Taslak": "Taslak",
    "Onaylandi": "Onaylandı",
    "Yazdirildi": "Yazdırıldı",
    "Arsivlendi": "Arşivlendi",
    "Iptal Edildi": "İptal Edildi",
}
SECENEKLER = ["Tümü"] + [s.value for s in DocumentStatus]

if st.button("➕ Yeni Sevkiyat"):
    st.session_state["duzenlenecek_sevkiyat_id"] = None
    st.switch_page("sayfalar/sevkiyat_editor.py")

d = db()
durum = st.selectbox("Durum süzgeci", SECENEKLER,
                     format_func=lambda v: DURUM_ETIKET.get(v, v))
kayitlar = d.get_shipments_with_details(
    status=None if durum == "Tümü" else durum)
st.caption(f"{len(kayitlar)} sevkiyat")

if kayitlar:
    for r in kayitlar:
        c1, c2, c3, c4, c5, c6 = st.columns([1.2, 1, 1, 1.5, 1.5, 0.8])
        c1.write(r.get("document_no") or "—")
        c2.write(r.get("document_date") or "—")
        c3.write(DURUM_ETIKET.get(r.get("status"), r.get("status")))
        c4.write(r.get("sender_name") or "—")
        c5.write(r.get("receiver_name") or "—")
        if c6.button("Aç", key=f"ac_{r.get('id')}"):
            st.session_state["duzenlenecek_sevkiyat_id"] = r.get("id")
            st.switch_page("sayfalar/sevkiyat_editor.py")
else:
    st.info("Bu süzgeçle sevkiyat bulunamadı.")
