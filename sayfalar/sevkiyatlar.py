"""Sevkiyatlar — liste görünümü (Faz 2 iskeleti; editör Faz 2b'de)."""
import streamlit as st
from sayfalar._ortak import db

st.title("🚛 Sevkiyatlar")

d = db()
durum = st.selectbox("Durum süzgeci",
                     ["Tümü", "Taslak", "Onaylandı", "Yazdırıldı",
                      "Arşivlendi", "İptal Edildi"])
kayitlar = d.get_shipments_with_details(
    status=None if durum == "Tümü" else durum)
st.caption(f"{len(kayitlar)} sevkiyat")
if kayitlar:
    st.dataframe(
        [{"Belge No": r.get("document_no"), "Tarih": r.get("document_date"),
          "Durum": r.get("status"), "Gönderen": r.get("sender_name"),
          "Alıcı": r.get("receiver_name"), "Plaka": r.get("plate"),
          "Puan": r.get("total_points")}
         for r in kayitlar],
        use_container_width=True, hide_index=True)
else:
    st.info("Bu süzgeçle sevkiyat bulunamadı.")
st.button("➕ Yeni Sevkiyat (Faz 2b'de eklenecek)", disabled=True)
