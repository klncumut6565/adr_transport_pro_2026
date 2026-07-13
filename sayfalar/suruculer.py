"""Sürücüler — ADR sürücü yönetimi (Faz 2b)."""
import streamlit as st
from sayfalar._ortak import db, onbellek_temizle
from webcore.models import Driver

st.title("🧑‍✈️ Sürücüler")

d = db()


def _bos_form_state():
    st.session_state["surucu_duzenle_id"] = None
    for alan in ("full_name", "tc_no", "phone", "adr_certificate_no",
                 "adr_certificate_expiry", "src5_no", "src5_expiry",
                 "license_class", "license_expiry"):
        st.session_state.pop(f"surucu_{alan}", None)


if "surucu_duzenle_id" not in st.session_state:
    _bos_form_state()
if "surucu_form_ac" not in st.session_state:
    st.session_state["surucu_form_ac"] = False

c1, c2, c3 = st.columns([3, 1, 1])
arama = c1.text_input("Ara (ad)")
sadece_aktif = c2.checkbox("Sadece aktif", value=True)
if c3.button("➕ Yeni Sürücü", use_container_width=True):
    _bos_form_state()
    st.session_state["surucu_form_ac"] = True
    st.rerun()

suruculer = d.get_drivers(search=arama or None, active_only=sadece_aktif)
st.caption(f"{len(suruculer)} sürücü")

if suruculer:
    for s in suruculer:
        c1, c2, c3, c4, c5 = st.columns([2, 1.5, 1.5, 0.8, 0.8])
        c1.write(s.full_name + ("" if s.is_active else " (pasif)"))
        c2.write(f"SRC5: {s.src5_expiry or '—'}")
        c3.write(f"ADR: {s.adr_certificate_expiry or '—'}")
        if c4.button("Düzenle", key=f"surucu_duz_{s.id}"):
            st.session_state["surucu_duzenle_id"] = s.id
            st.session_state["surucu_full_name"] = s.full_name
            st.session_state["surucu_tc_no"] = s.tc_no
            st.session_state["surucu_phone"] = s.phone
            st.session_state["surucu_adr_certificate_no"] = s.adr_certificate_no
            st.session_state["surucu_adr_certificate_expiry"] = s.adr_certificate_expiry
            st.session_state["surucu_src5_no"] = s.src5_no
            st.session_state["surucu_src5_expiry"] = s.src5_expiry
            st.session_state["surucu_license_class"] = s.license_class
            st.session_state["surucu_license_expiry"] = s.license_expiry
            st.session_state["surucu_form_ac"] = True
            st.rerun()
        durum_etiketi = "Pasifleştir" if s.is_active else "Aktifleştir"
        if c5.button(durum_etiketi, key=f"surucu_durum_{s.id}"):
            s.is_active = not s.is_active
            d.update_driver(s)
            onbellek_temizle()  # DÜZELTME: veri değişti, önbellek bayat kalmasın
            st.rerun()
else:
    st.info("Kayıtlı sürücü yok.")

if not st.session_state["surucu_form_ac"]:
    st.stop()

st.divider()
duzenlenen_id = st.session_state["surucu_duzenle_id"]
st.subheader("Sürücü Düzenle" if duzenlenen_id else "➕ Yeni Sürücü")

with st.form("surucu_formu"):
    c1, c2 = st.columns(2)
    ad = c1.text_input("Ad Soyad", value=st.session_state.get("surucu_full_name", ""))
    tc = c2.text_input("TC No", value=st.session_state.get("surucu_tc_no", ""))

    telefon = st.text_input("Telefon", value=st.session_state.get("surucu_phone", ""))

    c3, c4 = st.columns(2)
    adr_no = c3.text_input("ADR Belge No", value=st.session_state.get("surucu_adr_certificate_no", ""))
    adr_tarih = c4.text_input("ADR Bitiş (GG.AA.YYYY)", value=st.session_state.get("surucu_adr_certificate_expiry", ""))

    c5, c6 = st.columns(2)
    src5_no = c5.text_input("SRC5 Belge No", value=st.session_state.get("surucu_src5_no", ""))
    src5_tarih = c6.text_input("SRC5 Bitiş (GG.AA.YYYY)", value=st.session_state.get("surucu_src5_expiry", ""))

    c7, c8 = st.columns(2)
    ehliyet_sinifi = c7.text_input("Ehliyet Sınıfı", value=st.session_state.get("surucu_license_class", ""))
    ehliyet_tarih = c8.text_input("Ehliyet Bitiş (GG.AA.YYYY)", value=st.session_state.get("surucu_license_expiry", ""))

    bc1, bc2 = st.columns(2)
    kaydet = bc1.form_submit_button("💾 Kaydet", type="primary", use_container_width=True)
    iptal = bc2.form_submit_button("İptal", use_container_width=True)

if kaydet:
    if not ad.strip():
        st.error("Ad Soyad zorunlu.")
    else:
        # DÜZELTME (Umut'un talebi): SRC5 belgesi form kaydında ZORUNLU
        # TUTULMUYOR artık — sürücü SRC5 bilgisi olmadan da eklenebilir/
        # düzenlenebilir (ör. belge sonradan temin edilecekse). Gerçek
        # ADR uyumluluk kontrolü (sevkiyat sırasında SRC5 gerekliliği)
        # webcore/engines.py'deki mevzuat motorunda hâlâ duruyor ve
        # DEĞİŞTİRİLMEDİ — yalnızca bu form-seviyesi engel kaldırıldı.
        surucu = Driver(id=duzenlenen_id, full_name=ad, tc_no=tc, phone=telefon,
                        adr_certificate_no=adr_no, adr_certificate_expiry=adr_tarih,
                        src5_no=src5_no, src5_expiry=src5_tarih,
                        license_class=ehliyet_sinifi, license_expiry=ehliyet_tarih)
        if duzenlenen_id:
            d.update_driver(surucu)
            onbellek_temizle()  # DÜZELTME: veri değişti, önbellek bayat kalmasın
            st.success("Sürücü güncellendi.")
        else:
            d.add_driver(surucu)
            onbellek_temizle()  # DÜZELTME: veri değişti, önbellek bayat kalmasın
            st.success("Sürücü eklendi.")
        st.session_state["surucu_form_ac"] = False
        _bos_form_state()
        st.rerun()

if iptal:
    st.session_state["surucu_form_ac"] = False
    _bos_form_state()
    st.rerun()
