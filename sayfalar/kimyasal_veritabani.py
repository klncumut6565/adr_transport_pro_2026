"""Kimyasal Veritabanı — ADR Tablo A tarama/arama."""
import streamlit as st
from sayfalar._ortak import db

st.title("🧪 Kimyasal Veritabanı")

d = db()
c1, c2 = st.columns([3, 1])
arama = c1.text_input("Ara (UN no / ad / sınıf)", placeholder="örn. 1203 veya benzin")
sinif = c2.text_input("Sınıf süzgeci", placeholder="örn. 3")

kayitlar = d.get_all_chemicals(search=arama or None,
                               class_filter=sinif or None, limit=200)
st.caption(f"{len(kayitlar)} kayıt görüntüleniyor (toplam {d.count_chemicals()})")
if kayitlar:
    st.dataframe(
        [{"UN": k.un_number, "Ad (TR)": k.proper_shipping_name_tr,
          "Sınıf": k.class_code, "PG": k.packing_group,
          "Tünel": k.tunnel_code, "TK": k.transport_category,
          "LQ": k.limited_quantity, "EQ": k.excepted_quantity}
         for k in kayitlar],
        use_container_width=True, hide_index=True)
else:
    st.info("Kayıt bulunamadı. ADR Tablo A henüz yüklenmediyse, yönetici "
            "olarak Ayarlar'dan içe aktarabilirsiniz (Faz 6'da).")
