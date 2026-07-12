"""Gösterge Paneli — masaüstündeki DashboardPage'in web karşılığı."""
import streamlit as st
from sayfalar._ortak import db

st.title("📊 Gösterge Paneli")

d = db()
istatistik = d.get_statistics()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Toplam Sevkiyat", istatistik.get("total_shipments", 0))
c2.metric("Taslak", istatistik.get("draft_shipments", 0))
c3.metric("Firmalar", istatistik.get("total_companies", 0))
c4.metric("Aktif Sürücüler", istatistik.get("active_drivers", 0))

st.divider()

sol, sag = st.columns(2)
with sol:
    st.subheader("⚠️ Süresi Yaklaşan Belgeler (30 gün)")
    yaklasan = d.get_expiring_documents(days=30)
    surucu, arac = yaklasan.get("drivers", []), yaklasan.get("vehicles", [])
    if not surucu and not arac:
        st.success("Önümüzdeki 30 günde süresi dolan belge yok.")
    for s in surucu:
        st.warning(f"Sürücü **{s['full_name']}** — SRC5: {s['src5_expiry']} "
                   f"({s.get('kalan', '?')} gün)")
    for a in arac:
        st.warning(f"Araç **{a['plate']}** — ADR: {a.get('adr_compliance_expiry') or '-'} "
                   f"/ Muayene: {a.get('inspection_expiry') or '-'}")
with sag:
    st.subheader("🏆 En Çok Taşınan Kimyasallar")
    enler = d.get_top_chemicals(limit=5)
    if enler:
        st.dataframe(enler, use_container_width=True, hide_index=True)
    else:
        st.info("Henüz sevkiyat kalemi yok.")
