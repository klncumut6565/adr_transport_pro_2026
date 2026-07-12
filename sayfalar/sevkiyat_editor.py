"""Sevkiyat Editörü — masaüstündeki ShipmentEditorPage'in web karşılığı (Faz 2b).

Akış:
- sayfalar/sevkiyatlar.py'den "Yeni Sevkiyat" veya bir satırın "Düzenle"
  butonuyla açılır; st.session_state["duzenlenecek_sevkiyat_id"] taşınır
  (None ise yeni sevkiyat).
- Kalemler session_state'te tutulur, "Kaydet" ile DB'ye yazılır
  (add_shipment/update_shipment + delete_shipment_items + add_shipment_item).
- "Doğrula" butonu ADREngine.validate_shipment / calculate_1136_points /
  calculate_tunnel_restriction / check_compatibility'yi çalıştırır.
"""
import streamlit as st

from sayfalar._ortak import db
from webcore.models import Shipment, ShipmentItem, DocumentStatus
from webcore.engines import ADREngine

PAKET_TURLERI = ["IBC", "Varil", "Bidon", "Kutu", "Çuval",
                  "Kompozit Ambalaj", "Tank", "Dökme"]

# DocumentStatus enum değerleri ASCII (DB'de bu şekilde saklanıyor);
# ekranda Türkçe karakterli göstermek için ayrı bir etiket haritası.
DURUM_ETIKET = {
    "Taslak": "Taslak",
    "Onaylandi": "Onaylandı",
    "Yazdirildi": "Yazdırıldı",
    "Arsivlendi": "Arşivlendi",
    "Iptal Edildi": "İptal Edildi",
}
DURUM_DEGERLERI = [s.value for s in DocumentStatus]


def _bos_sevkiyat() -> dict:
    return {
        "id": None, "document_no": "", "document_date": "",
        "status": "Taslak", "sender_id": 0, "receiver_id": 0,
        "carrier_id": 0, "driver_id": 0, "vehicle_id": 0,
        "exemption_type": "Yok", "notes": "",
    }


def _yukle(shipment_id: int):
    d = db()
    s = d.get_shipment(shipment_id)
    if s is None:
        st.error("Sevkiyat bulunamadı.")
        st.session_state["editor_sevkiyat"] = _bos_sevkiyat()
        st.session_state["editor_kalemler"] = []
        return
    st.session_state["editor_sevkiyat"] = {
        "id": s.id, "document_no": s.document_no,
        "document_date": s.document_date, "status": s.status,
        "sender_id": s.sender_id, "receiver_id": s.receiver_id,
        "carrier_id": s.carrier_id, "driver_id": s.driver_id,
        "vehicle_id": s.vehicle_id, "exemption_type": s.exemption_type,
        "notes": s.notes,
    }
    kalemler = d.get_shipment_items(shipment_id)
    st.session_state["editor_kalemler"] = [dict(vars(k)) for k in kalemler]


def _durumu_baslat():
    hedef_id = st.session_state.get("duzenlenecek_sevkiyat_id", "__ilk__")
    yuklu_id = st.session_state.get("editor_yuklu_id", "__ilk__")
    if hedef_id != yuklu_id:
        if hedef_id:
            _yukle(hedef_id)
        else:
            st.session_state["editor_sevkiyat"] = _bos_sevkiyat()
            st.session_state["editor_kalemler"] = []
        st.session_state["editor_yuklu_id"] = hedef_id


_durumu_baslat()
sev = st.session_state["editor_sevkiyat"]
kalemler = st.session_state["editor_kalemler"]

st.title("📝 Sevkiyat Editörü" + (f" — #{sev['id']}" if sev["id"] else " — Yeni"))
if st.button("← Sevkiyatlar listesine dön"):
    st.session_state["duzenlenecek_sevkiyat_id"] = None
    st.switch_page("sayfalar/sevkiyatlar.py")

d = db()
firmalar = d.get_companies()
firma_secenekleri = {0: "— Seçilmedi —"} | {c.id: c.name for c in firmalar}
suruculer = d.get_drivers(active_only=True)
surucu_secenekleri = {0: "— Seçilmedi —"} | {s.id: s.full_name for s in suruculer}
araclar = d.get_vehicles(active_only=True)
arac_secenekleri = {0: "— Seçilmedi —"} | {a.id: a.plate for a in araclar}

st.subheader("Belge Bilgileri")
c1, c2, c3 = st.columns(3)
sev["document_no"] = c1.text_input("Belge No", value=sev["document_no"])
sev["document_date"] = c2.text_input("Tarih (GG.AA.YYYY)", value=sev["document_date"])
sev["status"] = c3.selectbox(
    "Durum", DURUM_DEGERLERI,
    index=DURUM_DEGERLERI.index(sev["status"]) if sev["status"] in DURUM_DEGERLERI else 0,
    format_func=lambda v: DURUM_ETIKET.get(v, v))

c4, c5, c6 = st.columns(3)
sev["sender_id"] = c4.selectbox("Gönderici", list(firma_secenekleri),
                                 index=list(firma_secenekleri).index(sev["sender_id"])
                                 if sev["sender_id"] in firma_secenekleri else 0,
                                 format_func=lambda i: firma_secenekleri[i])
sev["receiver_id"] = c5.selectbox("Alıcı", list(firma_secenekleri),
                                   index=list(firma_secenekleri).index(sev["receiver_id"])
                                   if sev["receiver_id"] in firma_secenekleri else 0,
                                   format_func=lambda i: firma_secenekleri[i])
sev["carrier_id"] = c6.selectbox("Taşıyıcı", list(firma_secenekleri),
                                  index=list(firma_secenekleri).index(sev["carrier_id"])
                                  if sev["carrier_id"] in firma_secenekleri else 0,
                                  format_func=lambda i: firma_secenekleri[i])

c7, c8 = st.columns(2)
sev["driver_id"] = c7.selectbox("Sürücü", list(surucu_secenekleri),
                                 index=list(surucu_secenekleri).index(sev["driver_id"])
                                 if sev["driver_id"] in surucu_secenekleri else 0,
                                 format_func=lambda i: surucu_secenekleri[i])
sev["vehicle_id"] = c8.selectbox("Araç", list(arac_secenekleri),
                                  index=list(arac_secenekleri).index(sev["vehicle_id"])
                                  if sev["vehicle_id"] in arac_secenekleri else 0,
                                  format_func=lambda i: arac_secenekleri[i])

sev["notes"] = st.text_area("Notlar", value=sev["notes"])

st.divider()
st.subheader("Kimyasal Kalemleri")

with st.expander("➕ Kalem ekle", expanded=not kalemler):
    arama = st.text_input("UN numarası veya madde adı ile ara")
    bulunanlar = db().search_chemicals(arama, limit=15) if arama else []
    if bulunanlar:
        secili = st.selectbox(
            "Bulunan maddeler", bulunanlar,
            format_func=lambda c: f"UN{c.un_number} — {c.proper_shipping_name_tr or c.proper_shipping_name_en}")
        ic1, ic2, ic3 = st.columns(3)
        paket_turu = ic1.selectbox("Ambalaj türü", PAKET_TURLERI, key="yeni_paket_turu")
        paket_adet = ic2.number_input("Ambalaj adeti", min_value=0, step=1, key="yeni_paket_adet")
        net_miktar = ic3.number_input("Net miktar", min_value=0.0, step=1.0, key="yeni_net_miktar")
        ic4, ic5, ic6 = st.columns(3)
        birim = ic4.selectbox("Birim", ["kg", "lt", "adet"], key="yeni_birim")
        is_lq = ic5.checkbox("LQ (Sınırlı Miktar)", key="yeni_lq")
        is_eq = ic6.checkbox("EQ (İstisnai Miktar)", key="yeni_eq")
        if st.button("Kalemi ekle", type="primary"):
            kalemler.append({
                "id": None, "shipment_id": sev["id"],
                "chemical_id": secili.id, "un_number": secili.un_number,
                "proper_name": secili.proper_shipping_name_tr or secili.proper_shipping_name_en,
                "class_code": secili.class_code, "packing_group": secili.packing_group,
                "packaging_type": paket_turu, "packaging_count": int(paket_adet),
                "net_quantity": float(net_miktar), "gross_quantity": float(net_miktar),
                "unit": birim, "is_lq": is_lq, "is_eq": is_eq,
                "lq_max_per_package": 0.0, "eq_max_per_package": 0.0, "notes": "",
                "tunnel_code": secili.tunnel_code, "segregation_group": secili.segregation_group,
                "classification_code": secili.classification_code,
                "transport_category": secili.transport_category,
                "special_provisions": secili.special_provisions,
            })
            st.session_state["editor_kalemler"] = kalemler
            st.rerun()
    elif arama:
        st.info("Eşleşen madde bulunamadı.")

if kalemler:
    for i, k in enumerate(kalemler):
        c1, c2, c3, c4, c5 = st.columns([1, 3, 1.2, 2, 0.6])
        c1.write(f"UN{k['un_number']}")
        c2.write(k["proper_name"])
        c3.write(k["class_code"])
        c4.write(f"{k['packaging_type']} · {k['packaging_count']} adet · "
                 f"{k['net_quantity']} {k['unit']}"
                 + (" · LQ" if k["is_lq"] else "") + (" · EQ" if k["is_eq"] else ""))
        if c5.button("🗑️", key=f"kalem_sil_{i}"):
            kalemler.pop(i)
            st.session_state["editor_kalemler"] = kalemler
            st.rerun()
else:
    st.info("Henüz kalem eklenmedi.")

st.divider()
st.subheader("Doğrulama ve Kayıt")


def _item_nesneleri():
    return [ShipmentItem(**{k: v for k, v in k_dict.items()}) for k_dict in kalemler]


bc1, bc2 = st.columns(2)
if bc1.button("🔍 Doğrula", use_container_width=True):
    items = _item_nesneleri()
    sender = d.get_company(sev["sender_id"]) if sev["sender_id"] else None
    receiver = d.get_company(sev["receiver_id"]) if sev["receiver_id"] else None
    driver = d.get_driver(sev["driver_id"]) if sev["driver_id"] else None
    vehicle = d.get_vehicle(sev["vehicle_id"]) if sev["vehicle_id"] else None

    sonuc = ADREngine.validate_shipment(items, sender=sender, receiver=receiver,
                                         driver=driver, vehicle=vehicle)
    for seviye, mesaj in sonuc.errors:
        st.error(mesaj)
    for seviye, mesaj in sonuc.warnings:
        st.warning(mesaj)
    if not sonuc.errors:
        st.success("Zorunlu alan kontrolleri geçti.")

    if items:
        puan, plaka_gerekli, detay = ADREngine.calculate_1136_points(items)
        tunel = ADREngine.calculate_tunnel_restriction(items)
        uyumsuzluklar = ADREngine.check_compatibility(items)
        st.metric("1.1.3.6 Puanı", f"{puan:.0f}", "Turuncu plaka zorunlu" if plaka_gerekli else "Turuncu plaka gerekmez")
        st.caption(f"Tünel kısıtlama kodu: **{tunel}**")
        if uyumsuzluklar:
            for u in uyumsuzluklar:
                st.error(f"Uyumsuzluk: {u}")
        with st.expander("Puan hesaplama detayı"):
            st.code(detay)

if bc2.button("💾 Kaydet", type="primary", use_container_width=True):
    if not sev["document_no"].strip():
        st.error("Belge No zorunlu (veritabanında benzersiz olmalı).")
    elif not kalemler:
        st.error("En az bir kimyasal kalemi eklemeden kaydedilemez.")
    else:
        # Kayıt anında motor sonuçları da hesaplanıp sevkiyata yazılır
        # (monolit davranışı: liste ekranındaki Puan/Plaka/Tünel kolonları
        # kalıcı veriden gelir, yalnız Doğrula anında görünen bilgi değildir).
        _items = _item_nesneleri()
        _puan, _plaka, _ = ADREngine.calculate_1136_points(_items)
        _tunel = ADREngine.calculate_tunnel_restriction(_items)
        shipment = Shipment(
            id=sev["id"], document_no=sev["document_no"], document_date=sev["document_date"],
            status=sev["status"], sender_id=sev["sender_id"], receiver_id=sev["receiver_id"],
            carrier_id=sev["carrier_id"], driver_id=sev["driver_id"], vehicle_id=sev["vehicle_id"],
            exemption_type=sev["exemption_type"], notes=sev["notes"],
            total_points=_puan, orange_plate_required=_plaka,
            tunnel_restriction_code=_tunel if isinstance(_tunel, str) else str(_tunel),
            is_validated=True,
        )
        try:
            if shipment.id:
                d.update_shipment(shipment)
                yeni_id = shipment.id
                d.delete_shipment_items(yeni_id)
            else:
                yeni_id = d.add_shipment(shipment)

            for k_dict in kalemler:
                k_dict["shipment_id"] = yeni_id
                k_dict.pop("id", None)
                d.add_shipment_item(ShipmentItem(**k_dict))

            st.session_state["duzenlenecek_sevkiyat_id"] = yeni_id
            st.session_state["editor_yuklu_id"] = "__ilk__"  # yeniden yüklemeye zorla
            st.success(f"Sevkiyat kaydedildi (#{yeni_id}).")
            st.rerun()
        except Exception as exc:
            if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
                st.error(f"Bu Belge No ('{sev['document_no']}') zaten kayıtlı. "
                         "Lütfen farklı bir belge numarası girin.")
            else:
                st.error(f"Kaydetme sırasında hata oluştu: {exc}")
