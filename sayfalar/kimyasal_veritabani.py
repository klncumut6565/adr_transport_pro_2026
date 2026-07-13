"""Kimyasal Veritabanı — ADR Tablo A tarama.

DÜZELTME (Umut'un tercihi): önceki sürüm text_input+dataframe ile
varsayılan olarak tüm Tablo A'yı (ilk 200 satır) listeliyordu — Ürün
Ekle'deki aynı hataydı, buradan da kaldırıldı. Artık sevkiyat_editor.py
ile birebir aynı desen: streamlit-searchbox ile canlı arama (Enter
gerekmez, yalnızca eşleşenler önerilir), bir sonuç seçilince TÜM
alanları gösteren bir detay kartı açılır.
"""
import streamlit as st
from streamlit_searchbox import st_searchbox

from sayfalar._ortak import db, kimyasal_etiket
from webcore.pg import TABLO_A_EKSIK_ESIGI

st.title("🧪 Kimyasal Veritabanı")

d = db()

if d.count_chemicals() < TABLO_A_EKSIK_ESIGI:
    bilgi = getattr(d, "seed_bilgisi", {})
    if bilgi.get("denendi") and not bilgi.get("basarili"):
        st.error("ADR Tablo A yüklü değil — otomatik yükleme başarısız "
                 f"oldu: {bilgi.get('hata', '?')}")
    else:
        st.warning("ADR Tablo A henüz yüklenmemiş, arama sonuç vermeyecektir.")
    if st.button("🔄 Tablo A'yı şimdi yükle (embedded dosyadan)"):
        import os
        if os.path.exists("ADR_A_TABLOSU.xlsx"):
            try:
                with st.spinner("Yükleniyor..."):
                    n = d.import_table_a_excel("ADR_A_TABLOSU.xlsx")
                st.success(f"{n} kayıt yüklendi.")
                st.rerun()
            except Exception as exc:
                from webcore.errors import turkce_hata_metni
                st.error(f"Yükleme başarısız: {turkce_hata_metni(exc)}")
        else:
            st.error("ADR_A_TABLOSU.xlsx dosyası bulunamadı.")
    st.stop()

st.caption(f"Veritabanında **{d.count_chemicals()}** kayıt var. "
           "UN numarası veya madde adı yazarak arayın.")


def _kimyasal_ara(terim: str):
    if not terim or len(terim) < 2:
        return []
    return [(kimyasal_etiket(k), k) for k in d.search_chemicals(terim, limit=20)]


secili = st_searchbox(
    _kimyasal_ara,
    key="kimyasal_veritabani_arama",
    placeholder="UN numarası veya madde adı yazın (ör. 1993 veya benzin)...",
    clear_on_submit=False,
    default=None,
)

if secili is None:
    st.info("Aramak için en az 2 karakter yazın.")
else:
    st.divider()
    st.subheader(f"UN {secili.un_number}")
    st.markdown(f"**{secili.proper_shipping_name_tr or secili.proper_shipping_name_en}**")
    if secili.proper_shipping_name_en and secili.proper_shipping_name_en != secili.proper_shipping_name_tr:
        st.caption(f"EN: {secili.proper_shipping_name_en}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sınıf", secili.class_code or "—")
    c2.metric("Ambalaj Grubu", secili.packing_group or "—")
    c3.metric("Tünel Kodu", secili.tunnel_code or "—")
    c4.metric("Taşıma Kategorisi", secili.transport_category or "—")

    c5, c6 = st.columns(2)
    with c5:
        st.markdown("**Sınıflandırma Kodu**")
        st.write(secili.classification_code or "—")
        st.markdown("**Tali Tehlike Etiketleri**")
        st.write(secili.hazard_labels or "—")
        st.markdown("**Ayrışma Grubu**")
        st.write(secili.segregation_group or "—")
    with c6:
        st.markdown("**Sınırlı Miktar (LQ)**")
        st.write(f"{secili.limited_quantity or '—'} "
                f"({'izinli' if secili.lq_allowed else 'izinli değil'})")
        st.markdown("**İstisnai Miktar (EQ)**")
        st.write(f"{secili.excepted_quantity or '—'} "
                f"({'izinli' if secili.eq_allowed else 'izinli değil'})")

    if secili.special_provisions:
        st.markdown("**Özel Hükümler**")
        st.write(secili.special_provisions)

    st.caption("Not: aynı UN numarası + ad ile birden fazla Tablo A satırı "
               "olabilir — bunlar sınıflandırma kodu, PG, tali tehlike "
               "etiketi veya özel hükümle (ör. 640C/640D) ayrışan GERÇEKTEN "
               "FARKLI girdilerdir. Farklı bir varyant için tekrar arayın.")
