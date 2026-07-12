"""Firmalar — gönderici/alıcı/taşıyıcı firma yönetimi (Faz 2b)."""
import streamlit as st
from sayfalar._ortak import db
from webcore.models import Company

FIRMA_TURLERI = {"sender": "Gönderici", "receiver": "Alıcı", "carrier": "Taşıyıcı"}

st.title("🏢 Firmalar")

d = db()


def _bos_form_state():
    st.session_state["firma_duzenle_id"] = None
    for alan in ("type", "name", "tax_number", "tax_office", "mersis_no",
                 "address", "city", "district", "phone", "email",
                 "contact_person"):
        st.session_state.pop(f"firma_{alan}", None)


if "firma_duzenle_id" not in st.session_state:
    _bos_form_state()
if "firma_form_ac" not in st.session_state:
    st.session_state["firma_form_ac"] = False

arama_col, buton_col = st.columns([4, 1])
arama = arama_col.text_input("Ara (isim)")
if buton_col.button("➕ Yeni Firma", use_container_width=True):
    _bos_form_state()
    st.session_state["firma_form_ac"] = True
    st.rerun()

firmalar = d.get_companies(search=arama or None)
st.caption(f"{len(firmalar)} firma")

if firmalar:
    for f in firmalar:
        c1, c2, c3, c4 = st.columns([2, 1, 2, 0.8])
        c1.write(f.name)
        c2.write(FIRMA_TURLERI.get(f.type, f.type))
        c3.write(f.city or "—")
        if c4.button("Düzenle", key=f"firma_duz_{f.id}"):
            st.session_state["firma_duzenle_id"] = f.id
            st.session_state["firma_type"] = f.type
            st.session_state["firma_name"] = f.name
            st.session_state["firma_tax_number"] = f.tax_number
            st.session_state["firma_tax_office"] = f.tax_office
            st.session_state["firma_mersis_no"] = f.mersis_no
            st.session_state["firma_address"] = f.address
            st.session_state["firma_city"] = f.city
            st.session_state["firma_district"] = f.district
            st.session_state["firma_phone"] = f.phone
            st.session_state["firma_email"] = f.email
            st.session_state["firma_contact_person"] = f.contact_person
            st.session_state["firma_form_ac"] = True
            st.rerun()
else:
    st.info("Kayıtlı firma yok.")

if not st.session_state["firma_form_ac"]:
    st.stop()

st.divider()
duzenlenen_id = st.session_state["firma_duzenle_id"]
st.subheader("Firma Düzenle" if duzenlenen_id else "➕ Yeni Firma")

with st.form("firma_formu", clear_on_submit=False):
    c1, c2 = st.columns(2)
    tip = c1.selectbox("Tür", list(FIRMA_TURLERI), format_func=lambda k: FIRMA_TURLERI[k],
                       index=list(FIRMA_TURLERI).index(st.session_state.get("firma_type", "sender")))
    ad = c2.text_input("Firma adı", value=st.session_state.get("firma_name", ""))

    c3, c4 = st.columns(2)
    vergi_no = c3.text_input("Vergi No", value=st.session_state.get("firma_tax_number", ""))
    vergi_dairesi = c4.text_input("Vergi Dairesi", value=st.session_state.get("firma_tax_office", ""))

    mersis = st.text_input("Mersis No", value=st.session_state.get("firma_mersis_no", ""))
    adres = st.text_area("Adres", value=st.session_state.get("firma_address", ""))

    c5, c6 = st.columns(2)
    sehir = c5.text_input("Şehir", value=st.session_state.get("firma_city", ""))
    ilce = c6.text_input("İlçe", value=st.session_state.get("firma_district", ""))

    c7, c8 = st.columns(2)
    telefon = c7.text_input("Telefon", value=st.session_state.get("firma_phone", ""))
    eposta = c8.text_input("E-posta", value=st.session_state.get("firma_email", ""))

    yetkili = st.text_input("Yetkili Kişi", value=st.session_state.get("firma_contact_person", ""))

    bc1, bc2, bc3 = st.columns(3)
    kaydet = bc1.form_submit_button("💾 Kaydet", type="primary", use_container_width=True)
    iptal = bc2.form_submit_button("İptal", use_container_width=True)
    sil = bc3.form_submit_button("🗑️ Sil", use_container_width=True, disabled=not duzenlenen_id)

if kaydet:
    if not ad.strip():
        st.error("Firma adı zorunlu.")
    else:
        firma = Company(id=duzenlenen_id, type=tip, name=ad, tax_number=vergi_no,
                        tax_office=vergi_dairesi, mersis_no=mersis, address=adres,
                        city=sehir, district=ilce, phone=telefon, email=eposta,
                        contact_person=yetkili)
        if duzenlenen_id:
            d.update_company(firma)
            st.success("Firma güncellendi.")
        else:
            d.add_company(firma)
            st.success("Firma eklendi.")
        st.session_state["firma_form_ac"] = False
        _bos_form_state()
        st.rerun()

if iptal:
    st.session_state["firma_form_ac"] = False
    _bos_form_state()
    st.rerun()

if sil and duzenlenen_id:
    d.delete_company(duzenlenen_id)
    st.success("Firma silindi.")
    st.session_state["firma_form_ac"] = False
    _bos_form_state()
    st.rerun()
