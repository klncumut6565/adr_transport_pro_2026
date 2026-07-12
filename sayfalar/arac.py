"""Araçlar — ADR onaylı araç/dorse yönetimi (Faz 2b)."""
import streamlit as st
from sayfalar._ortak import db
from webcore.models import Vehicle

st.title("🚚 Araçlar")

d = db()


def _bos_form_state():
    st.session_state["arac_duzenle_id"] = None
    for alan in ("plate", "trailer_plate", "adr_compliance_cert_no",
                 "adr_compliance_expiry", "inspection_date",
                 "inspection_expiry", "tank_info", "vehicle_type",
                 "max_capacity"):
        st.session_state.pop(f"arac_{alan}", None)


if "arac_duzenle_id" not in st.session_state:
    _bos_form_state()
if "arac_form_ac" not in st.session_state:
    st.session_state["arac_form_ac"] = False

c1, c2, c3 = st.columns([3, 1, 1])
arama = c1.text_input("Ara (plaka)")
sadece_aktif = c2.checkbox("Sadece aktif", value=True)
if c3.button("➕ Yeni Araç", use_container_width=True):
    _bos_form_state()
    st.session_state["arac_form_ac"] = True
    st.rerun()

araclar = d.get_vehicles(search=arama or None, active_only=sadece_aktif)
st.caption(f"{len(araclar)} araç")

if araclar:
    for a in araclar:
        c1, c2, c3, c4, c5 = st.columns([1.5, 1.5, 1.5, 0.8, 0.8])
        c1.write(a.plate + ("" if a.is_active else " (pasif)"))
        c2.write(f"ADR: {a.adr_compliance_expiry or '—'}")
        c3.write(f"Muayene: {a.inspection_expiry or '—'}")
        if c4.button("Düzenle", key=f"arac_duz_{a.id}"):
            st.session_state["arac_duzenle_id"] = a.id
            st.session_state["arac_plate"] = a.plate
            st.session_state["arac_trailer_plate"] = a.trailer_plate
            st.session_state["arac_adr_compliance_cert_no"] = a.adr_compliance_cert_no
            st.session_state["arac_adr_compliance_expiry"] = a.adr_compliance_expiry
            st.session_state["arac_inspection_date"] = a.inspection_date
            st.session_state["arac_inspection_expiry"] = a.inspection_expiry
            st.session_state["arac_tank_info"] = a.tank_info
            st.session_state["arac_vehicle_type"] = a.vehicle_type
            st.session_state["arac_max_capacity"] = a.max_capacity
            st.session_state["arac_form_ac"] = True
            st.rerun()
        durum_etiketi = "Pasifleştir" if a.is_active else "Aktifleştir"
        if c5.button(durum_etiketi, key=f"arac_durum_{a.id}"):
            a.is_active = not a.is_active
            d.update_vehicle(a)
            st.rerun()
else:
    st.info("Kayıtlı araç yok.")

if not st.session_state["arac_form_ac"]:
    st.stop()

st.divider()
duzenlenen_id = st.session_state["arac_duzenle_id"]
st.subheader("Araç Düzenle" if duzenlenen_id else "➕ Yeni Araç")

with st.form("arac_formu"):
    c1, c2 = st.columns(2)
    plaka = c1.text_input("Plaka", value=st.session_state.get("arac_plate", ""))
    dorse_plaka = c2.text_input("Dorse Plakası", value=st.session_state.get("arac_trailer_plate", ""))

    c3, c4 = st.columns(2)
    adr_no = c3.text_input("ADR Uygunluk Belge No", value=st.session_state.get("arac_adr_compliance_cert_no", ""))
    adr_tarih = c4.text_input("ADR Bitiş (GG.AA.YYYY)", value=st.session_state.get("arac_adr_compliance_expiry", ""))

    c5, c6 = st.columns(2)
    muayene_tarih = c5.text_input("Muayene Tarihi (GG.AA.YYYY)", value=st.session_state.get("arac_inspection_date", ""))
    muayene_bitis = c6.text_input("Muayene Bitiş (GG.AA.YYYY)", value=st.session_state.get("arac_inspection_expiry", ""))

    c7, c8 = st.columns(2)
    arac_tipi = c7.text_input("Araç Tipi", value=st.session_state.get("arac_vehicle_type", ""))
    kapasite = c8.number_input("Maks. Kapasite (kg)", min_value=0.0, step=100.0,
                               value=float(st.session_state.get("arac_max_capacity", 0.0)))

    tank_bilgisi = st.text_area("Tank Bilgisi", value=st.session_state.get("arac_tank_info", ""))

    bc1, bc2 = st.columns(2)
    kaydet = bc1.form_submit_button("💾 Kaydet", type="primary", use_container_width=True)
    iptal = bc2.form_submit_button("İptal", use_container_width=True)

if kaydet:
    if not plaka.strip():
        st.error("Plaka zorunlu.")
    else:
        arac = Vehicle(id=duzenlenen_id, plate=plaka, trailer_plate=dorse_plaka,
                       adr_compliance_cert_no=adr_no, adr_compliance_expiry=adr_tarih,
                       inspection_date=muayene_tarih, inspection_expiry=muayene_bitis,
                       tank_info=tank_bilgisi, vehicle_type=arac_tipi,
                       max_capacity=kapasite)
        if duzenlenen_id:
            d.update_vehicle(arac)
            st.success("Araç güncellendi.")
        else:
            d.add_vehicle(arac)
            st.success("Araç eklendi.")
        st.session_state["arac_form_ac"] = False
        _bos_form_state()
        st.rerun()

if iptal:
    st.session_state["arac_form_ac"] = False
    _bos_form_state()
    st.rerun()
