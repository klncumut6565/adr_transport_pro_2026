"""Sayfaların ortak yardımcıları."""
import streamlit as st

from webcore.session import get_db


def db():
    return get_db()


def kullanici():
    return st.session_state.get("user", {})


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
