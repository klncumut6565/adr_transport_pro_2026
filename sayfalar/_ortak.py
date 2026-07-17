"""Sayfaların ortak yardımcıları."""
import time

import streamlit as st

from webcore.session import get_db


def db():
    return get_db()


def kullanici():
    return st.session_state.get("user", {})


# ── Önbellekli listeler (performans) ────────────────────────────────
# DÜZELTME (2. tur): st.cache_data DENENDİ ama Streamlit Cloud'daki Python
# 3.14'te UnserializableReturnValueError ile patlıyordu — st.cache_data
# önbelleğe yazarken değeri PICKLE'lıyor (CachedResult sarmalayıcısı
# içinde) ve bu, yerelde (3.12, AppTest ile bile) yeniden üretilemeyen
# bir sürüme özgü pickle sorunuydu. Peşinden koşmak yerine PICKLE'A HİÇ
# BAĞIMLI OLMAYAN bir yola geçildi: st.session_state tabanlı elle
# önbellekleme. Bu, session_state'in zaten canlı Python nesnelerini
# doğrudan bellekte tuttuğu (serileştirme YOK) için hem daha basit hem
# daha güvenli. Ayrıca mimariyle de tutarlı: her Streamlit oturumunun
# zaten kendi DB bağlantısı var (bkz. webcore/session.py), bu yüzden
# oturum başına önbellek de doğal bir sınır — kiracılar arası sızıntı
# riski YOK (bir oturum aynı anda yalnızca bir kiracıya bağlı).
_ONBELLEK_ANAHTAR_ONEKI = "_ob_"


def _onbellekli(anahtar: str, sure_saniye: float, uretici):
    tam_anahtar = _ONBELLEK_ANAHTAR_ONEKI + anahtar
    kayit = st.session_state.get(tam_anahtar)
    simdi = time.time()
    if kayit is not None and (simdi - kayit["zaman"]) < sure_saniye:
        return kayit["veri"]
    veri = uretici()
    st.session_state[tam_anahtar] = {"veri": veri, "zaman": simdi}
    return veri


def firmalar_listesi():
    d = db()
    return _onbellekli(f"firmalar_{d.tenant_id}", 60, d.get_companies)


def suruculer_listesi(active_only: bool = True):
    d = db()
    return _onbellekli(f"suruculer_{d.tenant_id}_{active_only}", 60,
                       lambda: d.get_drivers(active_only=active_only))


def araclar_listesi(active_only: bool = True):
    d = db()
    return _onbellekli(f"araclar_{d.tenant_id}_{active_only}", 60,
                       lambda: d.get_vehicles(active_only=active_only))


def tablo_a_sayisi():
    d = db()
    return _onbellekli("tablo_a_sayisi", 300, d.count_chemicals)


def onbellek_temizle():
    """Bir firma/sürücü/araç eklendiğinde, düzenlendiğinde veya
    silindiğinde ÇAĞRILMALI — aksi hâlde değişiklik en fazla 60 saniye
    (TTL) boyunca bu OTURUMDA görünmez kalır (diğer oturumlar zaten
    kendi TTL'lerine göre bağımsız tazelenir)."""
    for k in list(st.session_state.keys()):
        if k.startswith(_ONBELLEK_ANAHTAR_ONEKI + "firmalar_") or \
           k.startswith(_ONBELLEK_ANAHTAR_ONEKI + "suruculer_") or \
           k.startswith(_ONBELLEK_ANAHTAR_ONEKI + "araclar_"):
            del st.session_state[k]


def tablo_a_onbellek_temizle():
    st.session_state.pop(_ONBELLEK_ANAHTAR_ONEKI + "tablo_a_sayisi", None)


def sayfaya_taze_girildi(sayfa_adi: str) -> bool:
    """DÜZELTME: 'Yeni Ekle' formlarının açık/kapalı durumu
    (ör. surucu_form_ac) st.session_state'te tutuluyor — bu OTURUM
    boyunca kalıcıdır. Kullanıcı formu açıp BAŞKA bir sayfaya geçtiğinde
    (kaydetmeden/iptal etmeden), form_ac bayrağı True kalmaya devam
    eder; sayfaya tekrar dönüldüğünde form hâlâ açık görünür ve içerik
    olarak yer kaplar — "düzeltme yapılmamış" hissi veren asıl sebep
    buydu (form KAPALI-VARSAYILAN mantığı doğruydu, ama önceki bir
    ziyaretten kalma AÇIK durumu ez iyordu).

    Bu fonksiyon, kullanıcının BAŞKA bir sayfadan bu sayfaya YENİ geçip
    geçmediğini tespit eder; öyleyse çağıran sayfa form_ac bayrağını
    zorla False'a çekmelidir — böylece her taze girişte form kapalı
    başlar, yalnızca AYNI sayfa içindeki gerçek etkileşimler (Kaydet/
    İptal butonlarına basma gibi) durumunu korur."""
    onceki = st.session_state.get("_aktif_sayfa")
    st.session_state["_aktif_sayfa"] = sayfa_adi
    return onceki != sayfa_adi


def kimyasal_etiket(c) -> str:
    """Bir Chemical kaydini secim listelerinde AYIRT EDICI sekilde gosterir.

    Resmi ADR Tablo A'da ayni UN numarasi + ayni ad ile birden fazla satir
    olabilir; bunlar siniflandirma kodu, paketleme grubu veya ozellikle ozel
    hukum (orn. 640C / 640D) ile ayrisir. Sadece 'UN{no} - {ad}' gostermek
    boyle durumlarda BIREBIR AYNI GORUNEN, farkli LQ/EQ/tunel/kategori
    tasiyan secenekleri kullanicidan gizler -- yanlis varyantin secilmesine
    yol acabilir. Bu yuzden sinif/PG/ozel hukum burada ayirt edici olarak
    eklenir."""
    ad = c.proper_shipping_name_tr or c.proper_shipping_name_en or ""
    parcalar = [f"UN{c.un_number} — {ad}"]
    sinif_pg = " / ".join(filter(None, [
        c.class_code,
        c.classification_code,
        f"PG {c.packing_group}" if c.packing_group else "",
    ]))
    if sinif_pg:
        parcalar.append(f"[{sinif_pg}]")
    if c.special_provisions:
        parcalar.append(f"ÖH: {c.special_provisions[:40]}")
    return " ".join(parcalar)


# ── Tarih seçici yardımcıları (Sürücüler/Araçlar — Umut'un talebi) ────
# DÜZELTME: masaüstü uygulamasında tarih alanları QDateEdit (takvim
# açılır pencereli) kullanıyordu; web'de bunlar düz metin kutusu
# ("GG.AA.YYYY" ipucuyla) olarak kalmıştı — kullanıcı hatalı biçimde
# yazabilir, format tutarsızlığı riski vardı. Artık st.date_input ile
# gerçek bir takvimden seçiliyor, masaüstüyle tutarlı deneyim.
def metin_to_tarih(metin: str):
    """Veritabanında saklanan esnek biçimli tarih metnini (ISO, TR nokta/
    slash) bir datetime.date nesnesine çevirir; ayrıştırılamazsa veya
    boşsa None döner (st.date_input'ta boş/varsayılan alan)."""
    from webcore.engines import ADREngine
    dt = ADREngine.parse_date_flexible(metin)
    return dt.date() if dt else None


def tarih_to_metin(tarih) -> str:
    """date_input'tan dönen date/None nesnesini veritabanına yazılacak
    ISO (YYYY-MM-DD) metne çevirir — masaüstünün kullandığı AYNI biçim
    (QDate "yyyy-MM-dd"), iki sistem arası veri tutarlılığı için."""
    return tarih.strftime("%Y-%m-%d") if tarih else ""


# Masaüstündeki VehicleEditDialog'un (asıl Araçlar sayfası) kullandığı
# BİREBİR AYNI liste — sayfalar/arac.py burada da kullanılıyor.
ARAC_TIPLERI = ["", "Tenteli", "Kapalı Kasa", "Tanker", "Konteyner", "Flatbed", "Diğer"]
