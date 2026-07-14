"""Karışık Yükleme Kontrolü — masaüstündeki GERÇEK ADR Mix Checker Pro
motorunun web karşılığı (ADR 7.5.2 / 7.5.4).

DÜZELTME (Umut'un tespiti): önceki sürüm webcore.engines.ADREngine.
check_compatibility kullanıyordu — segregation_group + sabit bir
sözlüğe dayanan BASİTLEŞTİRİLMİŞ bir kontroldü. Artık masaüstünün
kullandığı GERÇEK motor (adr_mix_pro — 71 birim testli segregasyon
kural motoru + Sınıf 1 patlayıcı dipnotları a/b/c/d + CV28 gıda ayrımı)
webcore/mix_adapter.py üzerinden buraya bağlandı; sonuçlar masaüstüyle
birebir aynı, aynı ADR gerekçesiyle üretiliyor. Arama da diğer
sayfalarla tutarlı hâle getirildi: streamlit-searchbox (canlı, Enter
gerektirmeyen arama).
"""
import streamlit as st
from streamlit_searchbox import st_searchbox

from sayfalar._ortak import db, kimyasal_etiket
from webcore.mix_adapter import gercek_mix_checker
from webcore.errors import turkce_hata_metni

st.title("🧯 Karışık Yükleme Kontrolü")
st.caption("ADR 7.5.2 / 7.5.4 — Birlikte taşınacak maddelerin segregasyon "
           "uyumluluğunu GERÇEK ADR Mix Checker motoruyla kontrol edin.")

if "mix_kalemler" not in st.session_state:
    st.session_state["mix_kalemler"] = []
kalemler = st.session_state["mix_kalemler"]

st.subheader("Madde Ekle")


def _kimyasal_ara(terim: str):
    if not terim or len(terim) < 2:
        return []
    return [(kimyasal_etiket(k), k) for k in db().search_chemicals(terim, limit=20)]


secili = st_searchbox(
    _kimyasal_ara,
    key=f"mix_arama_kutusu_{len(kalemler)}",  # her ekleme sonrası tazelenir
    placeholder="UN numarası veya madde adı yazın (ör. 1993 veya benzin)...",
    clear_on_submit=True,
    default=None,
)
if secili is not None:
    zaten_var = any(
        k["un_number"] == secili.un_number
        and k["classification_code"] == secili.classification_code
        and k["packing_group"] == secili.packing_group
        for k in kalemler)
    if zaten_var:
        st.warning(f"UN{secili.un_number} (bu sınıflandırma/PG ile) zaten listede.")
    else:
        kalemler.append({
            "un_number": secili.un_number,
            "proper_name": secili.proper_shipping_name_tr or secili.proper_shipping_name_en,
            "class_code": secili.class_code,
            "packing_group": secili.packing_group,
            "tunnel_code": secili.tunnel_code,
            "classification_code": secili.classification_code,
            "transport_category": secili.transport_category,
        })
        st.session_state["mix_kalemler"] = kalemler
        st.success(f"UN{secili.un_number} listeye eklendi.")
        st.rerun()

st.divider()
st.subheader("Kontrol Edilecek Maddeler")

if kalemler:
    for i, k in enumerate(kalemler):
        c1, c2, c3, c4, c5 = st.columns([1, 3, 1.3, 1.5, 0.6])
        c1.write(f"UN{k['un_number']}")
        c2.write(k["proper_name"])
        c3.write(" / ".join(filter(None, [
            k["class_code"], k["classification_code"],
            f"PG{k['packing_group']}" if k["packing_group"] else ""])) or "—")
        c4.write(f"Tünel: {k['tunnel_code'] or '—'}")
        if c5.button("🗑️", key=f"mix_sil_{i}"):
            kalemler.pop(i)
            st.session_state["mix_kalemler"] = kalemler
            st.rerun()

    if st.button("🧹 Listeyi temizle"):
        st.session_state["mix_kalemler"] = []
        st.rerun()

    st.divider()
    if len(kalemler) < 2:
        st.info("Kontrol için en az 2 madde eklemelisiniz.")
    else:
        try:
            _mc_sonuc = gercek_mix_checker(db())
            if _mc_sonuc is None:
                st.error("Karışık yükleme kural dosyası bulunamadı "
                         "(resources/data/segregation_rules.csv).")
            else:
                _checker, _adapter = _mc_sonuc
                for k in kalemler:
                    _adapter.register_variant(k["un_number"], k["classification_code"],
                                              k["packing_group"])
                _sonuclar, _eksikler = _checker.check_all([k["un_number"] for k in kalemler])

                _renk = {"OK": "success", "NO": "error",
                        "EXPLOSIVE_SPECIAL": "error", "FOOD_CAUTION": "warning",
                        "UNKNOWN": "warning"}
                _sorunlu = [r for r in _sonuclar if r.status != "OK"]

                if not _sorunlu:
                    st.success("✅ Seçili maddeler arasında GERÇEK ADR Mix Checker "
                              "motoruna göre bilinen bir uyumsuzluk tespit edilmedi.")
                else:
                    for r in _sorunlu:
                        gosterim = getattr(st, _renk.get(r.status, "warning"))
                        gosterim(f"**UN{r.un1} ({r.name1}) + UN{r.un2} ({r.name2})**\n\n"
                                f"{r.reason}\n\n"
                                f"*ADR referansı: {r.adr_reference} · Risk puanı: {r.risk_score}*")
                        if r.notes:
                            for not_ in r.notes:
                                st.caption(f"↳ {not_}")

                # OK olan ikilileri de bilgi amaçlı göster (kaç ikili tam
                # uyumlu, masaüstündeki sonuç tablosuyla tutarlı bütünlük)
                _uyumlu_sayisi = len(_sonuclar) - len(_sorunlu)
                if _sonuclar:
                    st.caption(f"Toplam {len(_sonuclar)} ikili kontrol edildi — "
                              f"{_uyumlu_sayisi} uyumlu, {len(_sorunlu)} sorunlu.")
                if _eksikler:
                    st.warning(f"Tablo A'da bulunamayan UN'ler: {', '.join(_eksikler)}")
        except Exception as exc:
            st.error(f"Kontrol çalıştırılamadı: {turkce_hata_metni(exc)}")

        st.caption("Bu kontrol, masaüstündeki ADR Mix Checker Pro ile AYNI "
                   "segregasyon kural motorunu kullanır (ADR 7.5.2 tam tablo "
                   "+ Sınıf 1 dipnotları a/b/c/d + CV28 gıda ayrımı). Nihai "
                   "karar için güncel ADR mevzuatı ve madde SDS'i esas alınmalıdır.")
else:
    st.info("Henüz madde eklenmedi. Yukarıdan arama yaparak ekleyin.")
