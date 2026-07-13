"""Sevkiyat Editörü — masaüstündeki "Taşıma Evrakı" ekranının web karşılığı.

Faz 4.5: Sağda masaüstündeki "ADR Kontrol Merkezi" panelinin canlı
karşılığı. Streamlit zaten her alan değişiminde tüm scripti yeniden
çalıştırdığı için "canlı" olmak ekstra bir mekanizma gerektirmiyor —
tek şart, hesaplamaları bir "Doğrula" butonunun ARDINDA değil, HER
rerun'da koşacak şekilde üst seviyede tutmak. Bu sürümde o yüzden
eski "🔍 Doğrula" butonu kaldırıldı; aynı hesaplar artık sağ panelde
sürekli görünür.

Akış:
- sayfalar/sevkiyatlar.py'den "Yeni Sevkiyat" veya bir satırın "Düzenle"
  butonuyla açılır; st.session_state["duzenlenecek_sevkiyat_id"] taşınır
  (None ise yeni sevkiyat).
- Ürünler session_state'te tutulur, "Kaydet" ile DB'ye yazılır.
- Sağ panel (ADR Kontrol Merkezi): 1.1.3.6 puanı, tünel kısıtlaması,
  sürücü sertifika durumu, uyarı/hata listesi, uyumsuzluk kontrolü —
  hepsi KAYDETMEDEN ÖNCE bile anlık günceldir (yalnızca session_state
  içindeki taslak veriye bakar, DB'ye yazılmış olmasını gerektirmez).
- "Canlı Evrak Önizleme": aynı ilke — taslak haldeyken bile taşıma
  evrakının biçimlendirilmiş HTML önizlemesi ekranda görünür; PDF
  üretimi (WeasyPrint) ayrı bir buton, çünkü her tuş vuruşunda PDF
  render etmek gereksiz maliyetlidir.
"""
import streamlit as st
import streamlit.components.v1 as components

from sayfalar._ortak import db, kimyasal_etiket
from webcore.models import Shipment, ShipmentItem, DocumentStatus
from webcore.engines import ADREngine
from webcore.errors import turkce_hata_metni
from webcore.pg import TABLO_A_EKSIK_ESIGI

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

# Faz 4.5 sıklaştırma: Streamlit'in varsayılan blok/başlık/ayraç boşlukları
# alan yiyor; sağdaki ADR Kontrol Merkezi paneli çok satır barındırdığı için
# hem sol form hem sağ panelde satır aralarını daraltıyoruz.
_KOMPAKT_CSS = """
<style>
div[data-testid="stVerticalBlock"] { gap: 0.45rem; }
div[data-testid="stElementContainer"] { margin-bottom: 0 !important; }
hr { margin: 0.35rem 0 !important; }
h3, h4, h5 { margin-top: 0.2rem !important; margin-bottom: 0.2rem !important;
     padding-top: 0 !important; padding-bottom: 0 !important; }
div[data-testid="stMetric"] { padding: 0.25rem 0 !important; }
div[data-testid="stExpander"] { margin-bottom: 0.3rem !important; }
</style>
"""


def _gg_aa_yyyy_to_date(metin: str):
    """document_date metnini (GG.AA.YYYY ya da ADREngine'in kabul ettiği
    diğer biçimler) st.date_input için bir date nesnesine çevirir.
    Ayrıştırılamazsa (boş/bozuk) bugüne düşer — widget hiçbir zaman
    None ile çağrılmaz."""
    from datetime import date
    d = ADREngine.parse_date_flexible(metin)
    return d.date() if d else date.today()


def _bos_sevkiyat() -> dict:
    # Masaüstü _init_new_document ile aynı: Evrak No otomatik üretilir
    # (ADR-YYYYAAGG-SSDDSS), Tarih bugüne varsayılan (kullanıcı isterse
    # geçmişe çevirebilir — st.date_input zaten serbest, min/max yok).
    from datetime import date
    return {
        "id": None, "document_no": ADREngine.format_document_number(),
        "document_date": date.today().strftime("%d.%m.%Y"),
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
        "id": s.id,
        # DÜZELTME: bazı eski kayıtlarda document_no boş yazılmıştı (Evrak No
        # otomatik doldurma özelliğinden önce oluşturulmuş sevkiyatlar).
        # Boş gelirse ekranda sessizce boş bırakmak yerine yeni bir numara
        # üretiyoruz; kayıt DB'ye ancak kullanıcı "Kaydet"e basınca yazılır,
        # yani salt görüntüleme/yükleme sırasında veri değişmez.
        "document_no": s.document_no or ADREngine.format_document_number(),
        "document_date": s.document_date, "status": s.status,
        "sender_id": s.sender_id, "receiver_id": s.receiver_id,
        "carrier_id": s.carrier_id, "driver_id": s.driver_id,
        "vehicle_id": s.vehicle_id, "exemption_type": s.exemption_type,
        "notes": s.notes,
    }
    kalemler = d.get_shipment_items(shipment_id)
    st.session_state["editor_kalemler"] = [dict(vars(k)) for k in kalemler]


def _durumu_baslat():
    hedef_id = st.session_state.get("duzenlenecek_sevkiyat_id")  # None => yeni
    yuklu_id = st.session_state.get("editor_yuklu_id", "__hic_yuklenmedi__")
    if hedef_id != yuklu_id or "editor_sevkiyat" not in st.session_state:
        if hedef_id:
            _yukle(hedef_id)
        else:
            st.session_state["editor_sevkiyat"] = _bos_sevkiyat()
            st.session_state["editor_kalemler"] = []
        st.session_state["editor_yuklu_id"] = hedef_id


_durumu_baslat()
sev = st.session_state["editor_sevkiyat"]
kalemler = st.session_state["editor_kalemler"]

st.markdown(_KOMPAKT_CSS, unsafe_allow_html=True)

st.title("📝 Taşıma Evrakı")
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


def _item_nesneleri():
    return [ShipmentItem(**{k: v for k, v in k_dict.items()}) for k_dict in kalemler]


# Seçili firma/sürücü/araç nesneleri: form ve sağ panel ikisi de kullanır,
# tek seferde çekilir (her rerun'da tekrar tekrar sorgulanmasın diye).
_secili_sender = d.get_company(sev["sender_id"]) if sev["sender_id"] else None
_secili_receiver = d.get_company(sev["receiver_id"]) if sev["receiver_id"] else None
_secili_carrier = d.get_company(sev["carrier_id"]) if sev["carrier_id"] else None
_secili_driver = d.get_driver(sev["driver_id"]) if sev["driver_id"] else None
_secili_vehicle = d.get_vehicle(sev["vehicle_id"]) if sev["vehicle_id"] else None


sol, sag = st.columns([2.3, 1], gap="large")

# =========================================================================
# SOL: Belge Bilgileri / Firma-Sürücü-Araç / Ürünler / Kayıt
# =========================================================================
with sol:
    st.markdown("##### Evrak Bilgileri")
    c1, c2, c3 = st.columns(3)
    sev["document_no"] = c1.text_input("Evrak No", value=sev["document_no"])
    sev["document_date"] = c2.date_input(
        "Tarih", value=_gg_aa_yyyy_to_date(sev["document_date"]),
        format="DD.MM.YYYY").strftime("%d.%m.%Y")
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
    st.markdown("##### Taşınan Ürünler")

    with st.expander("➕ Ürün ekle", expanded=not kalemler):
        if db().count_chemicals() < TABLO_A_EKSIK_ESIGI:
            bilgi = getattr(db(), "seed_bilgisi", {})
            if bilgi.get("denendi") and not bilgi.get("basarili"):
                st.error("ADR Tablo A yüklü değil — otomatik yükleme "
                         f"başarısız oldu: {bilgi.get('hata', '?')}")
            else:
                st.warning("ADR Tablo A henüz yüklenmemiş, arama sonuç "
                          "vermeyecektir.")
            if st.button("🔄 Tablo A'yı şimdi yükle", key="tabloa_hizli_yukle"):
                import os
                if os.path.exists("ADR_A_TABLOSU.xlsx"):
                    try:
                        with st.spinner("Yükleniyor..."):
                            n = db().import_table_a_excel("ADR_A_TABLOSU.xlsx")
                        st.success(f"{n} kayıt yüklendi.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Yükleme başarısız: {turkce_hata_metni(exc)}")
                else:
                    st.error("ADR_A_TABLOSU.xlsx dosyası bulunamadı.")
        # DÜZELTME 2: st.dataframe + yerleşik arama araç çubuğu yaklaşımı
        # da yanlış çıktı — TÜM Tablo A'yı (binlerce satır) varsayılan
        # olarak ekrana döküyordu, oysa istenen tam tersiydi: yazana kadar
        # HİÇBİR ŞEY görünmesin, yazınca YALNIZCA eşleşenler (ör. "1993"
        # için ~6 sonuç) listelensin. Streamlit'in kendi text_input'u bunu
        # yapamıyor (Enter/blur gerektirir). Bunun için özel olarak
        # tasarlanmış streamlit-searchbox bileşenine geçildi: her tuş
        # vuruşunda arka planda search_chemicals()'ı çağırır, dönen
        # eşleşmeleri açılır bir liste olarak gösterir — Enter YOK,
        # tüm tablo YOK, yalnızca o anki eşleşmeler.
        from streamlit_searchbox import st_searchbox

        def _kimyasal_ara(terim: str):
            if not terim or len(terim) < 2:
                return []
            return [(kimyasal_etiket(k), k)
                   for k in db().search_chemicals(terim, limit=20)]

        secili = st_searchbox(
            _kimyasal_ara,
            key="urun_arama_kutusu",
            placeholder="UN numarası veya madde adı yazın (ör. 1993 veya benzin)...",
            clear_on_submit=True,
            default=None,
        )
        bulunanlar = [secili] if secili else []
        if bulunanlar:
            st.success(f"Seçili: {kimyasal_etiket(secili)}")
            ic1, ic2, ic3 = st.columns(3)
            paket_turu = ic1.selectbox("Ambalaj türü", PAKET_TURLERI, key="yeni_paket_turu")
            paket_adet = ic2.number_input("Ambalaj adeti", min_value=0, step=1, key="yeni_paket_adet")
            net_miktar = ic3.number_input("Net miktar", min_value=0.0, step=1.0, key="yeni_net_miktar")
            ic4, ic5, ic6 = st.columns(3)
            birim = ic4.selectbox("Birim", ["kg", "lt", "adet"], key="yeni_birim")
            is_lq = ic5.checkbox("LQ (Sınırlı Miktar)", key="yeni_lq")
            is_eq = ic6.checkbox("EQ (İstisnai Miktar)", key="yeni_eq")
            if st.button("Ürünü ekle", type="primary"):
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
        elif secili is None:
            st.caption("Aramak için en az 2 karakter yazın.")

    if kalemler:
        hc1, hc2, hc3, hc4, hc5 = st.columns([1, 3, 1.2, 2, 0.6])
        hc1.caption("UN No"); hc2.caption("Teknik İsim"); hc3.caption("Sınıf/PG")
        hc4.caption("Ambalaj / Miktar"); hc5.caption("")
        for i, k in enumerate(kalemler):
            c1, c2, c3, c4, c5 = st.columns([1, 3, 1.2, 2, 0.6])
            c1.write(f"UN{k['un_number']}")
            c2.write(k["proper_name"])
            c3.write(f"{k['class_code']}{' PG' + k['packing_group'] if k['packing_group'] else ''}")
            c4.write(f"{k['packaging_type']} · {k['packaging_count']} adet · "
                     f"{k['net_quantity']} {k['unit']}"
                     + (" · LQ" if k["is_lq"] else "") + (" · EQ" if k["is_eq"] else ""))
            if c5.button("🗑️", key=f"kalem_sil_{i}"):
                kalemler.pop(i)
                st.session_state["editor_kalemler"] = kalemler
                st.rerun()
    else:
        st.info("Henüz ürün eklenmedi.")

    st.divider()
    st.markdown("##### Kayıt")

    if st.button("💾 Kaydet", type="primary", use_container_width=True):
        if not sev["document_no"].strip():
            st.error("Evrak No zorunlu (veritabanında benzersiz olmalı).")
        elif not kalemler:
            st.error("En az bir kimyasal ürünü eklemeden kaydedilemez.")
        else:
            # Kayıt anında motor sonuçları da hesaplanıp sevkiyata yazılır
            # (monolit davranışı: liste ekranındaki Puan/Plaka/Tünel kolonları
            # kalıcı veriden gelir, yalnız anlık görünen bilgi değildir).
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
                    st.error(f"Bu Evrak No ('{sev['document_no']}') zaten kayıtlı. "
                             "Lütfen farklı bir evrak numarası girin.")
                else:
                    st.error(f"Kaydetme sırasında hata oluştu: {turkce_hata_metni(exc)}")


# =========================================================================
# SAĞ: ADR Kontrol Merkezi — Canlı Uyumluluk Analizi (Faz 4.5)
# Bu blok hiçbir butona bağlı DEĞİL: her alan değişiminde (Streamlit'in
# doğal rerun döngüsüyle) otomatik yeniden hesaplanır.
# =========================================================================
with sag:
    st.markdown("### 🛡️ ADR Kontrol Merkezi")
    st.caption("Canlı Uyumluluk Analizi")

    items = _item_nesneleri()

    # ---- 1.1.3.6 Miktar Muafiyeti ----------------------------------------
    if items:
        puan, plaka_gerekli, _detay = ADREngine.calculate_1136_points(items)
        tunel = ADREngine.calculate_tunnel_restriction(items)
    else:
        puan, plaka_gerekli, tunel = 0.0, False, "—"

    st.markdown("**1.1.3.6 — Miktar Muafiyeti**")
    oran = min(puan / 1000, 1.0) if puan else 0.0
    st.progress(oran, text=f"{puan:.0f} / 1000 puan ({oran*100:.0f}%)")
    if plaka_gerekli:
        st.error("🔶 Turuncu plaka ZORUNLU")
    else:
        st.success("✅ Turuncu plaka gerekmez (1.1.3.6 muafiyeti)")

    st.divider()

    # ---- Canlı Evrak Önizleme ---------------------------------------------
    st.markdown("**📄 Canlı Evrak Önizleme**")
    if not items:
        st.info("Önizleme ve PDF için en az bir ürün ekleyin ↓")
    else:
        try:
            from webcore.transport_doc import build_transport_document_html
            _onizleme_html = build_transport_document_html(
                db=d, items=items,
                document_no=sev["document_no"] or "(taslak)",
                document_date_str=str(sev["document_date"]),
                sender=_secili_sender, receiver=_secili_receiver,
                driver=_secili_driver, vehicle=_secili_vehicle,
                status_text=sev["status"], notes=sev["notes"] or "")
            with st.expander("Önizlemeyi göster/gizle", expanded=False):
                from webcore.pdf import wrap_for_screen_preview
                components.html(wrap_for_screen_preview(_onizleme_html),
                               height=850, scrolling=True)

            if st.button("📄 PDF oluştur ve indir", use_container_width=True):
                try:
                    from webcore.pdf import html_to_pdf_bytes
                    st.session_state["tasima_evraki_pdf"] = html_to_pdf_bytes(_onizleme_html)
                except ImportError:
                    st.info("PDF için WeasyPrint gerekli (Cloud'da otomatik kurulur).")
                except Exception as exc:
                    st.error(f"PDF üretilemedi: {turkce_hata_metni(exc)}")

            if st.session_state.get("tasima_evraki_pdf"):
                st.download_button(
                    "⬇️ İndir", data=st.session_state["tasima_evraki_pdf"],
                    file_name=f"tasima_evraki_{sev['document_no'] or 'taslak'}.pdf",
                    mime="application/pdf", use_container_width=True)
        except Exception as exc:
            st.warning(f"Önizleme oluşturulamadı: {turkce_hata_metni(exc)}")

    # ---- Durum Göstergeleri ----------------------------------------------
    st.markdown("**Durum Göstergeleri**")
    dg1, dg2 = st.columns(2)
    dg1.metric("Ürün Sayısı", len(kalemler))
    dg2.metric("Tünel Kodu", tunel)

    st.divider()

    # ---- Sürücü Sertifika Durumu ------------------------------------------
    st.markdown("**Sürücü Sertifika Durumu**")
    if _secili_driver is None:
        st.caption("Sürücü seçilmedi")
    else:
        def _sertifika_satiri(etiket: str, tarih_metni: str):
            if not (tarih_metni or "").strip():
                st.warning(f"{etiket}: tarih girilmemiş")
                return
            tarih = ADREngine.parse_date_flexible(tarih_metni)
            if tarih is None:
                st.error(f"{etiket}: tarih okunamadı ('{tarih_metni}')")
                return
            from datetime import datetime
            kalan = (tarih - datetime.now()).days
            if kalan < 0:
                st.error(f"{etiket}: SÜRESİ DOLMUŞ ({tarih.strftime('%d.%m.%Y')})")
            elif kalan <= 30:
                st.warning(f"{etiket}: {kalan} gün içinde doluyor ({tarih.strftime('%d.%m.%Y')})")
            else:
                st.success(f"{etiket}: geçerli ({tarih.strftime('%d.%m.%Y')})")

        st.caption(_secili_driver.full_name)
        _sertifika_satiri("ADR Belgesi", _secili_driver.adr_certificate_expiry)
        _sertifika_satiri("SRC5", _secili_driver.src5_expiry)

    st.divider()

    # ---- Uyarı ve Hatalar ---------------------------------------------------
    st.markdown("**Uyarı ve Hatalar**")
    sonuc = ADREngine.validate_shipment(items, sender=_secili_sender, receiver=_secili_receiver,
                                         driver=_secili_driver, vehicle=_secili_vehicle)
    uyumsuzluklar = ADREngine.check_compatibility(items) if items else []

    if not sonuc.errors and not sonuc.warnings and not uyumsuzluklar:
        st.success("Sorun tespit edilmedi.")
    else:
        for _, mesaj in sonuc.errors:
            st.error(mesaj)
        for u in uyumsuzluklar:
            st.error(f"Uyumsuzluk: {u}")
        for _, mesaj in sonuc.warnings:
            st.warning(mesaj)

    st.divider()

