"""Kimyasal Veritabanı — ADR Tablo A tarama/arama."""
import streamlit as st
from sayfalar._ortak import db
from webcore.pg import TABLO_A_EKSIK_ESIGI

st.title("🧪 Kimyasal Veritabanı")

d = db()
c1, c2 = st.columns([3, 1])
arama = c1.text_input("Ara (UN no / ad / sınıf)", placeholder="örn. 1203 veya benzin")
sinif = c2.text_input("Sınıf süzgeci", placeholder="örn. 3")

kayitlar = d.get_all_chemicals(search=arama or None,
                               class_filter=sinif or None, limit=200)
kayitlar = sorted(kayitlar, key=lambda k: (k.un_number, k.classification_code or "",
                                            k.packing_group or ""))
st.caption(f"{len(kayitlar)} kayıt görüntüleniyor (toplam {d.count_chemicals()})")
st.caption("Not: aynı UN numarası + ad ile birden fazla satır olabilir — bunlar "
           "sınıflandırma kodu, PG, tali tehlike etiketi veya özel hükümle "
           "(ör. 640C/640D) ayrışan GERÇEKTEN FARKLI Tablo A girdileridir.")
if kayitlar:
    st.dataframe(
        [{"UN": k.un_number, "Ad (TR)": k.proper_shipping_name_tr,
          "Sınıf": k.class_code, "Sınıflandırma Kodu": k.classification_code,
          "PG": k.packing_group, "Tali Tehlike": k.hazard_labels,
          "Özel Hükümler": k.special_provisions,
          "Tünel": k.tunnel_code, "TK": k.transport_category,
          "LQ": k.limited_quantity, "EQ": k.excepted_quantity}
         for k in kayitlar],
        use_container_width=True, hide_index=True)
else:
    if d.count_chemicals() >= TABLO_A_EKSIK_ESIGI:
        st.info("Bu süzgeçle eşleşen kayıt yok.")
    else:
        # Tablo A tamamen boş: otomatik-tohumlamanın SESSİZCE başarısız
        # olup olmadığını göster (dosya bulunamadı / DB izin hatası vb.) —
        # arka planda yalnızca log'a yazmak, Cloud'da "neden boş?"
        # sorusunu yanıtsız bırakıyordu.
        bilgi = getattr(d, "seed_bilgisi", {})
        if bilgi.get("denendi") and not bilgi.get("basarili"):
            st.error("Tablo A otomatik yüklemesi başarısız oldu: "
                     f"{bilgi.get('hata', 'bilinmeyen hata')}")
            st.caption(f"Aranan dosya: {bilgi.get('yol', '—')}")
        else:
            st.info("Kayıt bulunamadı.")

        if st.button("🔄 Tablo A'yı şimdi yükle (embedded dosyadan)"):
            import os
            yol = "ADR_A_TABLOSU.xlsx"
            if not os.path.exists(yol):
                st.error(f"'{yol}' bulunamadı (çalışma dizini: {os.getcwd()}).")
            else:
                try:
                    with st.spinner("Yükleniyor..."):
                        n = d.import_table_a_excel(yol)
                    st.success(f"{n} kayıt yüklendi. Sayfayı yenileyin.")
                    st.rerun()
                except Exception as exc:
                    from webcore.errors import turkce_hata_metni
                    st.error(f"Yükleme başarısız: {turkce_hata_metni(exc)}")
