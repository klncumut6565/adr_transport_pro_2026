"""ADREngine + SecurityPlanEngine (monolitten satırı satırına).

BİLİNÇLİ SAPMA (Faz 2b, tek nokta): check_compatibility içindeki uyumsuzluk
listesi monolitte `list(set(errors))` ile döndürülüyordu — bu hem sırayı
belirsizleştiriyor hem A+B / B+A ayna kopyalarını bırakıyordu. Web'de sırasız
çift bazında tekilleştirme + kararlı sıra kullanılır. Mesaj İÇERİKLERİ ve
kural mantığı DEĞİŞMEMİŞTİR; yalnızca tekrar/sıralama davranışı düzeltildi.
Masaüstü (donmuş) sürümde eski davranış sürer. Bu sapma
tests_webcore/test_webcore_smoke.py::TestCompatibilityDedup ile kilitlidir."""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import shutil
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False

from .constants import *  # noqa: F403
from .models import *  # noqa: F403

class SecurityPlanEngine:
    """
    ADR 1.10.3 kapsamında emniyet planı gereksinimi hesaplar.

    Karar hiyerarşisi (ADR 2023 Bölüm 1.10):
    ┌─────────────────────────────────────────────────────────────────┐
    │ 1. Madde 1.10.4 listesinde mi?                                 │
    │    EVET → 1.1.3.6 muafiyeti KULLANAMAZ, devam et              │
    │    HAYIR → Toplam puan < 1000 ise (1.1.3.6) emniyet planı YOK │
    ├─────────────────────────────────────────────────────────────────┤
    │ 2. Sınıf 7 radyoaktif? → Tablo 1.10.3.1.3 eşik hesabı         │
    ├─────────────────────────────────────────────────────────────────┤
    │ 3. Diğer sınıflar → Tablo 1.10.3.1.2 eşik karşılaştırması     │
    │    'a' = Bu taşıma modu için uygulanamaz (muaf sayılır)        │
    │    'b' = Miktar ne olursa olsun muaf                           │
    │    0   = Herhangi bir miktarda EMNİYET PLANI GEREKLİ           │
    │    N   = Miktar > N litre/kg → EMNİYET PLANI GEREKLİ          │
    └─────────────────────────────────────────────────────────────────┘
    """

    # ── ADR 1.10.4: Bu UN numaraları 1.1.3.6 muafiyetini KULLANAMAZ ──────
    # Kaynak: ADR 2023, Madde 1.10.4 (açıkça sayılan UN numaraları)
    EXCLUDED_FROM_1136: frozenset = frozenset({
        29, 30, 59, 65, 73, 104, 237, 255, 267, 288, 289, 290,
        360, 361, 364, 365, 366, 439, 440, 441, 455, 456, 500
    })

    # ── Tablo 1.10.3.1.2 ─────────────────────────────────────────────────
    # key: (sinif, kosul)
    # value: (tank_litre, dokme_kg, ambalaj_kg)
    # None = 'a' (uygulanamaz), -1 = 'b' (muaf)
    THRESHOLDS: dict = {
        # Sınıf 1
        ("1", "1.1"):              (None, None, 0),
        ("1", "1.2"):              (None, None, 0),
        ("1", "1.3C"):             (None, None, 0),
        ("1", "1.4_special"):      (None, None, 0),   # özel UN listesi (aşağıda)
        ("1", "1.5"):              (0,    None, 0),
        # Sınıf 2 — alevlenebilir gazlar (F, FC sınıf kodu)
        ("2", "F"):                (3000, None, -1),
        ("2", "FC"):               (3000, None, -1),
        # Sınıf 2 — zehirli gazlar (T, TF, TC, TO, TFC, TOC)
        ("2", "T"):                (0,    None, 0),
        ("2", "TF"):               (0,    None, 0),
        ("2", "TC"):               (0,    None, 0),
        ("2", "TO"):               (0,    None, 0),
        ("2", "TFC"):              (0,    None, 0),
        ("2", "TOC"):              (0,    None, 0),
        # Sınıf 3
        ("3", "PGI"):              (3000, None, -1),
        ("3", "PGII"):             (3000, None, -1),
        ("3", "desensitized"):     (0,    None, 0),
        # Sınıf 4.1
        ("4.1", "desensitized"):   (None, None, 0),
        # Sınıf 4.2
        ("4.2", "PGI"):            (3000, None, -1),
        # Sınıf 4.3
        ("4.3", "PGI"):            (3000, None, -1),
        # Sınıf 5.1
        ("5.1", "PGI_liquid"):     (3000, None, -1),
        ("5.1", "perchlorate_AN"): (3000, 3000, -1),
        # Sınıf 6.1
        ("6.1", "PGI"):            (0,    None, 0),
        # Sınıf 6.2
        ("6.2", "catA"):           (None, 0,    0),
        # Sınıf 8
        ("8", "PGI"):              (3000, None, -1),
    }

    # UN 1.4'teki özel tehlikeli numara listesi (ADR Tablo 1.10.3.1.2: 0104,0237,0255,0267,0289,0361,0365,0366,0440,0441,0455,0456,0500,0512,0513)
    CLASS14_HIGH_CONSEQUENCE: frozenset = frozenset({
        104, 237, 255, 267, 289, 361, 365, 366, 440, 441, 455, 456, 500, 512, 513
    })

    # Amonyum nitrat / perklorat UN numaraları (5.1 özel satır)
    PERCHLORATE_AN_UN: frozenset = frozenset({
        1942, 2067, 2068, 2069, 2070, 2426, 3375,   # AN / AN gübre
        1481, 1482, 1483, 3506,                       # Perklorat
    })

    # UN 6.2 Kategori A: UN 2814 (insan pat.), UN 2900 (hayvansal pat.), UN 3549 (tibbi atik Kat.A)
    UN_6_2_CAT_A: frozenset = frozenset({2814, 2900, 3549})

    # ── Tablo 1.10.3.1.3 — Radyonüklid eşik değerleri (TBq) ─────────────
    RADIONUCLIDE_THRESHOLDS: dict = {
        "Am-241": 0.6,  "Au-198": 2,    "Cd-109": 200,  "Cf-252": 0.2,
        "Cm-244": 0.5,  "Co-57":  7,    "Co-60":  0.3,  "Cs-137": 1,
        "Fe-55":  8000, "Ge-68":  7,    "Gd-153": 10,   "Ir-192": 0.8,
        "Ni-63":  600,  "Pd-103": 900,  "Pm-147": 400,  "Po-210": 0.6,
        "Pu-238": 0.6,  "Pu-239": 0.6,  "Ra-226": 0.4,  "Ru-106": 3,
        "Se-75":  2,    "Sr-90":  10,   "Tl-204": 200,  "Tm-170": 200,
        "Yb-169": 3,
    }
    CLASS7_GENERIC_THRESHOLD_TBq: float = 3000.0   # Tabloda olmayan nüklidler

    # ─────────────────────────────────────────────────────────────────────
    # YARDIMCI: Bir ShipmentItem için Tablo 1.10.3.1.2 anahtarını çıkar
    # ─────────────────────────────────────────────────────────────────────
    @classmethod
    def _get_table_key(cls, item: "ShipmentItem") -> str:
        """
        ShipmentItem bilgilerinden Tablo 1.10.3.1.2 satır anahtarını üretir.
        Döndürülen değer THRESHOLDS dict'indeki 'kosul' parçasıdır.
        """
        cls_raw_parts = (item.class_code or "").strip().split()
        cls_raw = cls_raw_parts[0] if cls_raw_parts else ""
        # [GUVENLIK] Bazı içe aktarılan kayıtlarda paketleme grubu Arap
        # rakamıyla ("1","2","3") gelebiliyor; PG karşılaştırmaları güvenlik
        # planı kararını etkilediğinden Roma rakamına normalize edilir.
        pg_raw  = (item.packing_group or "").strip().upper()
        pg      = {"1": "I", "2": "II", "3": "III"}.get(pg_raw, pg_raw)
        un_int  = 0
        try:
            un_int = int((item.un_number or "").strip().lstrip("0") or "0")
        except ValueError:
            pass

        # Sınıf 1 alt grupları
        # ADR Tablo 1.10.3.1.2: "Sınıf" sütununda 1, "Sınıflandırma kodu" sütununda 1.4S / 1.3C vb.
        # class_code: "1", "1.1"…"1.6" | classification_code: "1.4S", "1.3C", "1.1A" vb.
        if cls_raw.startswith("1.") or cls_raw == "1":
            import re as _re
            cc_full = (getattr(item, "classification_code", "") or "").strip().upper()
            # classification_code doluysa alt sınıf + uyumluluk grubunu buradan al
            if cc_full:
                m = _re.match(r"(1\.[0-9])([A-Z]*)$", cc_full)
                if m:
                    sub_cc = m.group(1)   # "1.4"
                    compat = m.group(2)   # "S", "B", "G", "C", ""
                    if sub_cc == "1.4":
                        if compat == "S":
                            return None       # 1.4S → emniyet planı gerektirmez
                        if un_int in cls.CLASS14_HIGH_CONSEQUENCE:
                            return "1.4_special"
                        return None           # diğer 1.4 → muaf
                    if sub_cc == "1.3":
                        return "1.3C" if compat == "C" else None   # sadece 1.3C kapsam içi
                    if sub_cc in ("1.1", "1.2"):
                        return sub_cc
                    if sub_cc == "1.5":
                        return "1.5"
                    return None
            # classification_code boşsa class_code'a göre değerlendir (eski kayıtlar)
            sub = cls_raw
            if sub == "1.4":
                if un_int in cls.CLASS14_HIGH_CONSEQUENCE:
                    return "1.4_special"
                return None
            if sub in ("1.1", "1.2"):
                return sub
            if sub == "1.3":
                return "1.3C"   # muhafazakâr: tüm 1.3 kapsam içi sayılır
            if sub == "1.5":
                return "1.5"
            return None   # 1.6 ve diğerleri → muaf

        # Sınıf 2
        if cls_raw == "2":
            # classification_code alanı yoksa class_code'da bazen yazıyor
            # önce special_provisions/notes içinde ara, yoksa default F
            cc = getattr(item, "classification_code", "").strip().upper()
            if not cc:
                # notes veya proper_name içinde geçen harf kombinasyonu
                search_in = (item.notes or "") + " " + (item.proper_name or "")
                for code in ("TOC","TFC","TF","TC","TO","FC","T","F"):
                    if code in search_in.upper():
                        cc = code
                        break
            # Aerosol muafiyeti: ADR 1.10.3.1.2 — sınıflandırma kodunda A harfi olan gazlar kapsam dışı
            if "A" in cc:
                return None   # aerosol → tablo dışı
            if cc in ("T","TF","TC","TO","TFC","TOC"):
                return cc
            # Alevlenebilir (F, FC) veya bilinmiyor → muhafazakâr: F
            return cc if cc in ("F","FC") else "F"

        # Sınıf 3
        if cls_raw == "3":
            # Duyarsızlaştırılmış patlayıcı UN numaraları (seçili liste)
            desens = {2852,3343,3357,3379,3380,3474,3475,3476,3477,3478,3479}
            if un_int in desens:
                return "desensitized"
            # ADR Tablo 1.10.3.1.2: Sınıf 3 için yalnızca PGI ve PGII yer alır.
            # PG III ürünler (örn. UN 1202 mazot) tablo kapsamı dışındadır → muaf.
            if pg == "I":
                return "PGI"
            if pg == "II":
                return "PGII"
            return None   # PG III veya belirsiz → tabloda yok → muaf

        # Sınıf 4.1
        if cls_raw == "4.1":
            # Duyarsızlaştırılmış patlayıcılar (bazı 4.1 maddeleri)
            desens_41 = {2555,2556,2557,3317,3319,3344,3380,3474,3475,3476,3477}
            if un_int in desens_41:
                return "desensitized"
            return None   # diğer 4.1 → tabloda yok

        # Sınıf 4.2
        if cls_raw == "4.2":
            return "PGI" if pg == "I" else None

        # Sınıf 4.3
        if cls_raw == "4.3":
            return "PGI" if pg == "I" else None

        # Sınıf 5.1
        if cls_raw == "5.1":
            if un_int in cls.PERCHLORATE_AN_UN:
                return "perchlorate_AN"
            return "PGI_liquid" if pg == "I" else None

        # Sınıf 6.1
        if cls_raw == "6.1":
            return "PGI" if pg == "I" else None

        # Sınıf 6.2
        if cls_raw == "6.2":
            if un_int == 2900:
                # UN 2900: hayvansal patojenlerde Kategori A → kapsam içi.
                # Kullanici "hayvansal malzeme hariç" istisnasini bilmeli;
                # kod muhafazakar davranarak catA döndürür.
                return "catA"
            if un_int in cls.UN_6_2_CAT_A:   # 2814, 3549
                return "catA"
            return None

        # Sınıf 8
        if cls_raw == "8":
            return "PGI" if pg == "I" else None

        return None

    # ─────────────────────────────────────────────────────────────────────
    # ANA HESAPLAMA FONKSİYONU
    # ─────────────────────────────────────────────────────────────────────
    @classmethod
    def check(
        cls,
        items: List["ShipmentItem"],
        transport_mode: str = "ambalaj",       # "tank" | "dokme" | "ambalaj"
        total_1136_points: float = None,       # zaten hesaplanmışsa ver
        radionuclides: dict = None,            # {nüklid: Ai_TBq} Sınıf 7 için
    ) -> dict:
        """
        ADR 1.10.3 emniyet planı gereksinim sonucu döndürür.

        Dönüş:
        {
          "required":   bool,
          "exempt":     bool,          # 1.10.4 / 1.1.3.6 muafiyeti
          "reasons":    [str],         # gereklilik sebepleri
          "details":    [str],         # tüm kalem detayları
          "class7_ratio": float|None,  # ∑(Ai/Ti) Sınıf 7 için
        }
        """
        result = {
            "required": False, "exempt": False,
            "reasons": [], "details": [], "class7_ratio": None
        }
        if not items:
            result["details"].append("Sevkiyat boş — değerlendirme yapılamadı.")
            return result

        mode_idx = {"tank": 0, "dokme": 1, "ambalaj": 2}.get(transport_mode, 2)

        # Ambalaj türü → taşıma modu eşleme yardımcısı
        # Her kalemin kendi packaging_type'ından mode_idx otomatik belirlenir.
        def _mode_idx_for_item(item) -> int:
            pt = (getattr(item, "packaging_type", "") or "").strip().lower()
            if pt == "tank":
                return 0   # tank sütunu
            if pt in ("dökme", "dokme"):
                return 1   # dökme sütunu
            return 2       # ambalaj sütunu (IBC, Varil, Bidon, Kutu, Çuval, Kompozit …)

        # ── 1. 1.1.3.6 Muafiyet Kontrolü (1.10.4) ────────────────────────
        # Eğer hiçbir kalem 1.10.4 listesindeyse VE toplam puan < 1000 ise → muaf
        has_excluded_un = any(
            cls._un_int(item) in cls.EXCLUDED_FROM_1136 for item in items
        )
        pts = total_1136_points if total_1136_points is not None else 0.0
        if not has_excluded_un and pts < 1000:
            result["exempt"] = True
            result["details"].append(
                f"✅ ADR 1.10.4 muafiyeti: Toplam 1.1.3.6 puanı {pts:.0f} < 1000 "
                f"ve listede kısıtlı UN yok → Emniyet planı GEREKMİYOR."
            )
            return result

        if has_excluded_un:
            result["details"].append(
                "⚠ 1.10.4 özel liste: Bazı UN numaraları 1.1.3.6 muafiyetinden yararlanamaz."
            )

        # ── 2. Sınıf 7 — Radyonüklid eşik hesabı ─────────────────────────
        class7_items = [i for i in items if (i.class_code or "").startswith("7")]
        if class7_items:
            ratio = cls._calc_class7_ratio(radionuclides or {})
            result["class7_ratio"] = ratio
            if ratio >= 1.0:
                result["required"] = True
                result["reasons"].append(
                    f"Sınıf 7: Radyoaktif eşik aşıldı (∑Ai/Ti = {ratio:.3f} ≥ 1)"
                )
            else:
                result["details"].append(
                    f"Sınıf 7: Eşik altında (∑Ai/Ti = {ratio:.3f} < 1) → bu sınıf için muaf"
                )

        # ── 3. Tablo 1.10.3.1.2 — Sınıf 1-8 ─────────────────────────────
        for item in items:
            _cls_parts = (item.class_code or "").strip().split()
            cls_raw = _cls_parts[0] if _cls_parts else ""
            if cls_raw.startswith("7"):
                continue   # Sınıf 7 zaten üstte işlendi

            un_str  = item.un_number or "—"
            qty_kg  = float(item.net_quantity or 0)
            # litre → kg dönüşüm gerektiren birimler için yaklaşık 1:1
            qty_l   = qty_kg   # tanklar litreyle kısıtlanır; basitlik için eşit

            # Her kalemin ambalaj türünden taşıma modu belirlenir
            item_mode_idx = _mode_idx_for_item(item)
            item_mode_str = {0: "Tank", 1: "Dökme", 2: "Ambalaj"}[item_mode_idx]

            key = cls._get_table_key(item)
            if key is None:
                result["details"].append(
                    f"  UN{un_str} ({cls_raw} PG{item.packing_group}) [{item_mode_str}]: "
                    f"Tablo 1.10.3.1.2 kapsamı dışında → muaf"
                )
                continue

            # Patlayicilar icin THRESHOLDS anahtari ("1", alt_grup) seklinde
            # cls_raw "1.1", "1.2" vb. olabilir → ana sinif "1" olarak normalize et
            threshold_cls = "1" if cls_raw.startswith("1.") else cls_raw
            threshold_row = cls.THRESHOLDS.get((threshold_cls, key))
            if threshold_row is None:
                result["details"].append(
                    f"  UN{un_str} [{item_mode_str}]: Tablo satırı bulunamadı → muaf kabul edildi"
                )
                continue

            limit = threshold_row[item_mode_idx]

            if limit is None:           # 'a': bu mod için uygulanamaz
                result["details"].append(
                    f"  UN{un_str} ({cls_raw}): {item_mode_str} modu için uygulanamaz (a) → muaf"
                )
            elif limit == -1:           # 'b': miktar ne olursa muaf
                result["details"].append(
                    f"  UN{un_str} ({cls_raw}): Miktar ne olursa olsun muaf (b) [{item_mode_str}]"
                )
            elif limit == 0:            # Her miktarda gerekli
                result["required"] = True
                result["reasons"].append(
                    f"UN{un_str} ({cls_raw} PG{item.packing_group}) [{item_mode_str}]: "
                    f"Herhangi bir miktarda emniyet planı gerekli (limit=0)"
                )
            else:                       # Eşik karşılaştırması
                val = qty_l if item_mode_idx == 0 else qty_kg
                unit_str = "litre" if item_mode_idx == 0 else "kg"
                if val > limit:
                    result["required"] = True
                    result["reasons"].append(
                        f"UN{un_str} ({cls_raw} PG{item.packing_group}) [{item_mode_str}]: "
                        f"{val:.0f} {unit_str} > {limit} {unit_str} eşiği aşıldı"
                    )
                else:
                    result["details"].append(
                        f"  UN{un_str} [{item_mode_str}]: {val:.0f} {unit_str} ≤ {limit} {unit_str} → muaf"
                    )

        if not result["required"] and not result["exempt"]:
            result["exempt"] = True
            result["details"].append("✅ Tüm kalemler eşik altında — Emniyet planı GEREKMİYOR.")

        return result

    # ─────────────────────────────────────────────────────────────────────
    # YARDIMCI METODlar
    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    def _un_int(item: "ShipmentItem") -> int:
        try:
            return int((item.un_number or "").strip().lstrip("0") or "0")
        except ValueError:
            return 0

    @classmethod
    def _calc_class7_ratio(cls, radionuclides: dict) -> float:
        """
        ADR 1.10.3.1.4 formülü: ∑(Ai / Ti)
        radionuclides = {"Cs-137": 1.5, "Co-60": 0.4, ...}  (TBq cinsinden)
        """
        total = 0.0
        for nuclide, activity_tbq in radionuclides.items():
            threshold = cls.RADIONUCLIDE_THRESHOLDS.get(nuclide,
                            cls.CLASS7_GENERIC_THRESHOLD_TBq)
            total += activity_tbq / threshold
        return total

    @classmethod
    def generate_plan_template(cls, shipment: "Shipment" = None,
                                items: List["ShipmentItem"] = None,
                                sample: bool = False) -> str:
        """
        ADR 1.10.3.2.2 gereksinimlerine uygun emniyet planı HTML şablonu üretir.
        sample=True → gerçekçi doldurulmuş örnek döner.
        """
        from datetime import datetime as _dt
        now    = _dt.now().strftime("%d.%m.%Y")
        doc_no = getattr(shipment, "document_no", "—") if shipment else "—"

        if sample:
            # ── Doldurulmuş örnek (TMGD perspektifli, UN 1203 Benzin / Tank taşıma) ──
            ep_no = "EP-" + _dt.now().strftime("%Y") + "-001"
            return f"""<!DOCTYPE html><html lang="tr"><head>
<meta charset="UTF-8">
<style>
  body{{font-family:Arial,Helvetica,sans-serif;font-size:10pt;margin:20mm;color:#1a1a1a;line-height:1.5;}}
  h1{{font-size:14pt;border-bottom:2pt solid #1E3A5F;color:#1E3A5F;padding-bottom:4px;margin-bottom:6px;}}
  h2{{font-size:11pt;color:#1E3A5F;margin-top:14px;margin-bottom:4px;}}
  table{{border-collapse:collapse;width:100%;margin:8px 0;}}
  th{{background:#1E3A5F;color:#fff;padding:5px 8px;text-align:left;font-size:9pt;}}
  td{{border:1px solid #ccc;padding:5px 8px;font-size:9pt;vertical-align:top;}}
  .section{{border:1px solid #1E3A5F;border-radius:3px;padding:8px 12px;margin-bottom:12px;}}
  .note{{font-size:8pt;color:#555;font-style:italic;}}
  .sig-box{{border:1px solid #aaa;min-height:80px;padding:8px;}}
  ol{{margin:6px 0 0 16px;padding:0;}} li{{margin-bottom:4px;}}
</style>
</head><body>

<h1>ADR EMNİYET PLANI — ADR 1.10.3.2</h1>
<p style="font-size:9pt;color:#555;">
  <strong>Belge No: {ep_no}</strong> &nbsp;|&nbsp; Düzenleme Tarihi: <strong>{now}</strong>
  &nbsp;|&nbsp; ADR Yönetmeliği Madde 1.10.3.2.2 kapsamında hazırlanmıştır.
</p>
<p class="note" style="background:#FEF9E7;padding:6px 10px;border-left:3px solid #F4D03F;border-radius:0 3px 3px 0;">
  ⚠ Bu belge gerçekçi bir örnek şablondur. Lütfen kendi firma, kişi ve güzergah
  bilgilerinizle güncelleyiniz.
</p>

<div class="section">
<h2>(a) Emniyet Sorumluluğu Dağılımı</h2>
<table>
  <tr><th>Görev</th><th>Sorumlu Kişi / Birim</th><th>İletişim</th></tr>
  <tr><td><strong>Emniyet Koordinatörü</strong></td><td>Selim Kaya</td><td>0532 XXX XX 01 · skaya@firma.com.tr</td></tr>
  <tr><td><strong>Gönderici Yetkilisi</strong></td><td>Mustafa Usta</td><td>0533 XXX XX 02 · musta@firma.com.tr</td></tr>
  <tr><td><strong>Taşıyıcı Yetkilisi</strong></td><td>Nizamettin Üstündağ</td><td>0530 XXX XX 03 · nizamettin@lojistik.com</td></tr>
  <tr><td><strong>Alıcı Yetkilisi</strong></td><td>Cem Sever</td><td>0555 XXX XX 04 · csever@alici.com.tr</td></tr>
</table>
</div>

<div class="section">
<h2>(b) Taşınan Tehlikeli Mal Kayıtları</h2>
<table>
  <tr><th>UN No</th><th>Uygun Sevkiyat Adı</th><th>Sınıf</th><th>PG</th><th>Miktar</th></tr>
  <tr><td><strong>UN 1203</strong></td><td>BENZİN veya GAZOLİN veya PETROL</td><td>3</td><td>II</td><td>3 050 litre</td></tr>
</table>
</div>

<div class="section">
<h2>(c) Emniyet Riski Değerlendirmesi</h2>
<p class="note">Duraklamalar, depolama, aktarma noktaları ve güzergah riskleri:</p>
<ul style="margin:6px 0 0 16px;padding:0;font-size:9pt;">
  <li><strong>Malzeme Karakteristiği:</strong> UN 1203, düşük parlama noktasına sahip, yüksek derecede yanıcı bir sıvıdır.
      Sabotaj veya terör eylemleri durumunda kitle yangın çıkarma aracı olarak kötüye kullanılma riski yüksektir (Yüksek Ciddi Risk).</li>
  <li><strong>Güzergah Riskleri:</strong> Şehir içi yoğun trafik, tünel ve köprü geçişlerinde saldırı ya da gasp girişimleri.</li>
  <li><strong>Duraklama / Mola Riskleri:</strong> Sürücünün zorunlu molaları esnasında (takograf süreleri), güvenliği sağlanmamış
      tesislerde aracın gözetimsiz kalması ve vana kapaklarının zorlanması riski.</li>
  <li><strong>Aktarma Noktaları:</strong> Dolum ve boşaltım tesislerinde yetkisiz personelin sahaya girmesi ve operasyona müdahalesi.</li>
</ul>
</div>

<div class="section">
<h2>(d) Riski Azaltma Önlemleri</h2>
<table>
  <tr><th style="width:22%;">Önlem</th><th>Uygulama Detayı</th></tr>
  <tr>
    <td><strong>Eğitim (ADR 1.3)</strong></td>
    <td>Tüm personel ADR Bölüm 1.3 ve 1.10 kapsamında Emniyet Farkındalık Eğitimi almıştır.
    Eğitim kayıtları İK departmanında saklanmaktadır. Sürücü geçerli SRC-5 (Tank) belgesine sahiptir.</td>
  </tr>
  <tr>
    <td><strong>Emniyet Politikası</strong></td>
    <td>Araca görevli personel dışında yolcu alınması yasaktır. Araç terk edildiğinde kapılar kilitlenmeli,
    kontak anahtarı araç üzerinde bırakılmamalıdır.</td>
  </tr>
  <tr>
    <td><strong>Güzergah Seçimi</strong></td>
    <td>Yalnızca Emniyet Koordinatörü tarafından onaylanmış ana arterler (otoyollar) kullanılır.
    Molalar aydınlatılmış, kameralı ve güvenli tır parklarında verilir.</td>
  </tr>
  <tr>
    <td><strong>Erişim Kontrolü</strong></td>
    <td>Tank menhol kapakları ve boşaltım vanaları mühürlü ve kilitlidir.
    Yükleme/boşaltma tesislerinde kimlik ibrazı ve kartlı geçiş zorunludur.</td>
  </tr>
  <tr>
    <td><strong>İzleme Teçhizatı</strong></td>
    <td>Araçta 7/24 GPS araç takip sistemi ve kabin içi Panik Butonu bulunmaktadır.
    Rota dışına çıkıldığında merkeze anında uyarı gönderilmektedir.</td>
  </tr>
</table>
</div>

<div class="section">
<h2>(e) Olay Raporlama Prosedürü</h2>
<p class="note">Emniyet ihlali veya olaylar için bildirim zinciri:</p>
<ol style="font-size:9pt;">
  <li><strong>Sürücü:</strong> Tehlike sezinlediğinde aracı güvenli şekilde terk eder/kilitler ve Panik Butonuna basar.</li>
  <li><strong>Kolluk Kuvvetleri:</strong> Sürücü derhal <strong>112</strong> Acil Çağrı Merkezi'ni arayarak konum ve
      yük bilgisini (UN 1203 – Benzin) bildirir.</li>
  <li><strong>Emniyet Koordinatörü:</strong> Sürücü eş zamanlı olarak Selim Kaya'yı bilgilendirir.</li>
  <li><strong>Kurum İçi Kriz Masası:</strong> Koordinatör; Gönderici, Taşıyıcı ve TMGD'ye acil kodla bilgi verir.
      Olay Ulaştırma ve Altyapı Bakanlığı'na yazılı olarak raporlanır.</li>
</ol>
</div>

<div class="section">
<h2>(f) Plan Gözden Geçirme</h2>
<table>
  <tr><th>Gözden Geçirme Tarihi</th><th>Yapılan Değişiklik</th><th>Onaylayan</th></tr>
  <tr><td>{now}</td><td>İlk taslağın oluşturulması ve güzergah analizlerinin eklenmesi.</td><td>Selim Kaya</td></tr>
  <tr><td></td><td></td><td></td></tr>
</table>
</div>

<div class="section">
<h2>İmza ve Onay</h2>
<table>
  <tr>
    <td style="width:50%;padding:12px;vertical-align:top;">
      <strong>Gönderici / Yükleyen Yetkilisi</strong><br><br>
      <span style="font-size:9pt;color:#555;">Ad Soyad:</span><br>
      <div class="sig-box">&nbsp;</div>
      <span style="font-size:9pt;color:#555;">İmza / Kaşe:</span><br>
      <div class="sig-box" style="min-height:100px;">&nbsp;</div>
      <span style="font-size:9pt;color:#555;">Tarih: {now}</span>
    </td>
    <td style="width:50%;padding:12px;vertical-align:top;border-left:1px solid #ccc;">
      <strong>Taşıyıcı Yetkilisi</strong><br><br>
      <span style="font-size:9pt;color:#555;">Ad Soyad:</span><br>
      <div class="sig-box">&nbsp;</div>
      <span style="font-size:9pt;color:#555;">İmza / Kaşe:</span><br>
      <div class="sig-box" style="min-height:100px;">&nbsp;</div>
      <span style="font-size:9pt;color:#555;">Tarih: {now}</span>
    </td>
  </tr>
</table>
</div>

<p class="note" style="margin-top:16px;">
  Bu plan ADR 1.10.3.2.2 maddelerini (a)–(f) karşılamaktadır.
  Periyodik gözden geçirme zorunludur (ADR 1.10.3.2.2/f).
</p>
</body></html>"""

        madde_listesi = ""
        if items:
            for it in items:
                madde_listesi += (
                    f"<tr><td>UN{it.un_number}</td><td>{it.proper_name}</td>"
                    f"<td>{it.class_code}</td><td>{it.packing_group}</td>"
                    f"<td>{it.net_quantity} {it.unit}</td></tr>"
                )
        else:
            madde_listesi = '<tr><td colspan="5">—</td></tr>'

        return f"""<!DOCTYPE html><html lang="tr"><head>
<meta charset="UTF-8">
<style>
  body{{font-family:Arial,Helvetica,sans-serif;font-size:10pt;margin:20mm;color:#1a1a1a;}}
  h1{{font-size:14pt;border-bottom:2pt solid #1E3A5F;color:#1E3A5F;padding-bottom:4px;}}
  h2{{font-size:11pt;color:#1E3A5F;margin-top:14px;}}
  table{{border-collapse:collapse;width:100%;margin:8px 0;}}
  th{{background:#1E3A5F;color:#fff;padding:5px 8px;text-align:left;font-size:9pt;}}
  td{{border:1px solid #ccc;padding:4px 8px;font-size:9pt;}}
  .field{{border-bottom:1px solid #999;min-height:18px;display:block;margin:2px 0 8px;}}
  .req{{color:#c0392b;font-weight:bold;}}
  .note{{font-size:8pt;color:#555;font-style:italic;}}
  .section{{border:1px solid #1E3A5F;border-radius:3px;padding:8px 12px;margin-bottom:10px;}}
</style>
</head><body>

<h1>ADR EMNİYET PLANI — ADR 1.10.3.2</h1>
<p style="font-size:9pt;color:#555;">
  Belge No: <strong>{doc_no}</strong> &nbsp;|&nbsp; Düzenleme Tarihi: <strong>{now}</strong>
  &nbsp;|&nbsp; ADR Yönetmeliği Madde 1.10.3.2.2 kapsamında hazırlanmıştır.
</p>

<div class="section">
<h2>(a) Emniyet Sorumluluğu Dağılımı</h2>
<table>
  <tr><th>Görev</th><th>Sorumlu Kişi / Birim</th><th>İletişim</th></tr>
  <tr><td>Emniyet koordinatörü</td><td class="field">&nbsp;</td><td class="field">&nbsp;</td></tr>
  <tr><td>Gönderici yetkilisi</td><td class="field">&nbsp;</td><td class="field">&nbsp;</td></tr>
  <tr><td>Taşıyıcı yetkilisi</td><td class="field">&nbsp;</td><td class="field">&nbsp;</td></tr>
  <tr><td>Alıcı yetkilisi</td><td class="field">&nbsp;</td><td class="field">&nbsp;</td></tr>
</table>
</div>

<div class="section">
<h2>(b) Taşınan Tehlikeli Mal Kayıtları</h2>
<table>
  <tr><th>UN No</th><th>Uygun Sevkiyat Adı</th><th>Sınıf</th><th>PG</th><th>Miktar</th></tr>
  {madde_listesi}
</table>
</div>

<div class="section">
<h2>(c) Emniyet Riski Değerlendirmesi</h2>
<p class="note">Duraklamalar, depolama, aktarma noktaları ve güzergah riskleri:</p>
<span class="field">&nbsp;<br>&nbsp;<br>&nbsp;</span>
</div>

<div class="section">
<h2>(d) Riski Azaltma Önlemleri</h2>
<table>
  <tr><th>Önlem</th><th>Uygulama Detayı</th></tr>
  <tr><td>Eğitim (ADR 1.3)</td><td class="field">&nbsp;</td></tr>
  <tr><td>Emniyet politikası</td><td class="field">&nbsp;</td></tr>
  <tr><td>Güzergah seçimi</td><td class="field">&nbsp;</td></tr>
  <tr><td>Erişim kontrolü</td><td class="field">&nbsp;</td></tr>
  <tr><td>İzleme teçhizatı</td><td class="field">&nbsp;</td></tr>
</table>
</div>

<div class="section">
<h2>(e) Olay Raporlama Prosedürü</h2>
<p class="note">Emniyet ihlali veya olaylar için bildirim zinciri:</p>
<span class="field">&nbsp;<br>&nbsp;</span>
</div>

<div class="section">
<h2>(f) Plan Gözden Geçirme</h2>
<table>
  <tr><th>Gözden Geçirme Tarihi</th><th>Yapılan Değişiklik</th><th>Onaylayan</th></tr>
  <tr><td class="field">&nbsp;</td><td class="field">&nbsp;</td><td class="field">&nbsp;</td></tr>
  <tr><td class="field">&nbsp;</td><td class="field">&nbsp;</td><td class="field">&nbsp;</td></tr>
</table>
</div>

<div class="section">
<h2>İmza ve Onay</h2>
<table>
  <tr>
    <td style="width:50%;padding:12px;">
      Gönderici / Yükleyen<br>
      Ad Soyad: <span class="field">&nbsp;</span>
      Tarih: <span class="field">&nbsp;</span>
      İmza / Kaşe: <span class="field">&nbsp;<br>&nbsp;</span>
    </td>
    <td style="width:50%;padding:12px;">
      Taşıyıcı Yetkilisi<br>
      Ad Soyad: <span class="field">&nbsp;</span>
      Tarih: <span class="field">&nbsp;</span>
      İmza / Kaşe: <span class="field">&nbsp;<br>&nbsp;</span>
    </td>
  </tr>
</table>
</div>

<p class="note" style="margin-top:16px;">
  Bu plan ADR 1.10.3.2.2 maddelerini (a)–(h) karşılamaktadır.
  Periyodik gözden geçirme zorunludur (ADR 1.10.3.2.2/f).
</p>
</body></html>"""


    # ─────────────────────────────────────────────────────────────────────
    # [v4.7] STATİK ENVANTER TARAMASI (Güvenlik Planı İnceleme Raporu)
    # ─────────────────────────────────────────────────────────────────────
    # Yukarıdaki check() metodu belirli bir SEVKİYATIN kalemlerini (miktar +
    # taşıma modu dahil) değerlendirir. Bu metod ise firmanın TÜM KİMYASAL
    # ENVANTERİNİ (belirli bir sevkiyattan bağımsız), yalnızca sınıf/PG/
    # sınıflandırma kodu bilgisine göre "Tablo 1.10.3.1.2 kapsamına
    # girip girmediğini" tarar — tıpkı örnek "Güvenlik Planı İnceleme
    # Raporu"nda olduğu gibi. Miktar burada değerlendirilmez çünkü envanter
    # taraması amacı, maddenin TÜRÜNE göre kapsam potansiyelini belirlemektir;
    # ambalaj sütunu ADR'de yalnızca 0 (her miktarda kapsam içi) veya b
    # (miktar ne olursa olsun muaf) değerlerini alır.
    @classmethod
    def screen_inventory_chemical(cls, chemical) -> dict:
        """Tek bir kimyasalı Tablo 1.10.3.1.2 kapsamında statik olarak
        değerlendirir. Dönüş: in_scope (True/False/"conditional"),
        table_key, sonuc_text (örnek rapordaki gibi Türkçe açıklama)."""
        from types import SimpleNamespace

        def _field(obj, key, default=""):
            """Chemical dataclass (getattr) VEYA sqlite3.Row / dict
            (anahtar erişimi) nesnelerinden güvenle alan okur. sqlite3.Row
            getattr ile ÇALIŞMAZ (sessizce default döner) — bu yüzden ham
            satır objelerinin yanlışlıkla boş veri üretmesini önler."""
            val = getattr(obj, key, None)
            if val not in (None, ""):
                return val
            try:
                if key in obj.keys():
                    return obj[key]
            except (AttributeError, TypeError):
                pass
            return default

        un_raw = str(_field(chemical, "un_number", "") or "")
        cls_raw_full = str(_field(chemical, "class_code", "") or "").strip()
        pg = str(_field(chemical, "packing_group", "") or "").strip().upper()
        cc = str(_field(chemical, "classification_code", "") or "").strip().upper()
        name = (_field(chemical, "proper_shipping_name_tr", "") or
                _field(chemical, "name", "") or
                _field(chemical, "proper_shipping_name_en", "") or "")

        fake_item = SimpleNamespace(
            class_code=cls_raw_full, packing_group=pg,
            classification_code=cc, un_number=un_raw,
            notes="", proper_name=name)

        base = {
            "un_number": un_raw, "class_code": cls_raw_full,
            "packing_group": pg, "classification_code": cc, "name": name,
        }

        key = cls._get_table_key(fake_item)
        if key is None:
            base.update(in_scope=False, table_key=None, sonuc_text=(
                f"Sınıf {cls_raw_full or chr(0x2014)}; bu madde ADR Tablo 1.10.3.1.2 "
                f"kapsamındaki sınıf/ambalajlama grubu kombinasyonlarından "
                f"hiçbirine girmemektedir. Bu nedenle güvenlik planı "
                f"hazırlanmasına gerek yoktur."))
            return base

        threshold_cls = "1" if cls_raw_full.startswith("1.") else cls_raw_full
        row = cls.THRESHOLDS.get((threshold_cls, key))
        if row is None:
            base.update(in_scope=False, table_key=key, sonuc_text=(
                f"Sınıf {cls_raw_full}; Tablo 1.10.3.1.2'de bu sınıf/kategori "
                f"için tanımlı bir satır bulunamadı. Bu nedenle güvenlik "
                f"planı hazırlanmasına gerek yoktur."))
            return base

        package_limit = row[2]

        descriptions = {
            ("1", "1.1"): "Sınıf 1.1 Patlayıcılar",
            ("1", "1.2"): "Sınıf 1.2 Patlayıcılar",
            ("1", "1.3C"): "Sınıf 1.3 Uyumluluk Grubu C Patlayıcılar",
            ("1", "1.4_special"): "Tablo 1.10.3.1.2'de özel olarak sayılan UN numaralı Sınıf 1.4 Patlayıcılar",
            ("1", "1.5"): "Sınıf 1.5 Patlayıcılar",
            ("2", "F"): "Alevlenebilir gazlar (F sınıflandırma kodu)",
            ("2", "FC"): "Alevlenebilir gazlar (FC sınıflandırma kodu)",
            ("2", "T"): "Zehirli gazlar (T sınıflandırma kodu)",
            ("2", "TF"): "Zehirli gazlar (TF sınıflandırma kodu)",
            ("2", "TC"): "Zehirli gazlar (TC sınıflandırma kodu)",
            ("2", "TO"): "Zehirli gazlar (TO sınıflandırma kodu)",
            ("2", "TFC"): "Zehirli gazlar (TFC sınıflandırma kodu)",
            ("2", "TOC"): "Zehirli gazlar (TOC sınıflandırma kodu)",
            ("3", "PGI"): "Ambalajlama grubu I'deki alevlenebilir sıvılar",
            ("3", "PGII"): "Ambalajlama grubu I ve II'deki alevlenebilir sıvılar",
            ("3", "desensitized"): "Duyarlılığı azaltılmış patlayıcılar (Sınıf 3)",
            ("4.1", "desensitized"): "Duyarlılığı azaltılmış patlayıcılar (Sınıf 4.1)",
            ("4.2", "PGI"): "Ambalajlama grubu I'deki kendiliğinden yanabilen maddeler",
            ("4.3", "PGI"): "Ambalajlama grubu I'deki maddeler (su ile temasta tehlikeli)",
            ("5.1", "PGI_liquid"): "Ambalajlama grubu I'deki yükseltgen sıvılar",
            ("5.1", "perchlorate_AN"): "Perkloratlar, amonyum nitrat, amonyum nitrat gübreler ve amonyum nitrat emülsiyonlar veya süspansiyonlar veya jeller",
            ("6.1", "PGI"): "Ambalajlama grubu I'deki zehirli maddeler",
            ("6.2", "catA"): "Kategori A'daki bulaşıcı maddeler (UN 2814 ve 2900 hayvansal malzemeler hariç)",
            ("8", "PGI"): "Ambalajlama grubu I'deki aşındırıcı maddeler",
        }
        desc = descriptions.get((threshold_cls, key), f"{cls_raw_full} sınıfı / {key}")

        if package_limit == 0:
            base.update(in_scope=True, table_key=key, sonuc_text=(
                f"Sınıf {cls_raw_full}; {desc} olarak sınıflandırılmıştır. "
                f"Bu madde Tablo 1.10.3.1.2 kapsamına GİRMEKTEDİR — ambalajlı "
                f"taşımada herhangi bir miktarda güvenlik planı değerlendirmesi "
                f"GEREKLİDİR."))
        elif package_limit == -1:
            base.update(in_scope=False, table_key=key, sonuc_text=(
                f"Sınıf {cls_raw_full}; {desc} olarak sınıflandırılmıştır. "
                f"Bu sınıfda ambalajlı taşımada miktar ne olursa olsun 1.10.3 "
                f"hükümleri uygulanmaz. Bu nedenle sınıfa girmemektedir; "
                f"güvenlik planı hazırlanmasına gerek yoktur."))
        elif package_limit is None:
            base.update(in_scope=False, table_key=key, sonuc_text=(
                f"Sınıf {cls_raw_full}; {desc} olarak sınıflandırılmıştır. "
                f"Ambalajlı taşıma modu için Tablo 1.10.3.1.2 uygulanamaz (a). "
                f"Bu nedenle güvenlik planı hazırlanmasına gerek yoktur."))
        else:
            base.update(in_scope="conditional", table_key=key, sonuc_text=(
                f"Sınıf {cls_raw_full}; {desc} olarak sınıflandırılmıştır. "
                f"Ambalajlı taşımada {package_limit} kg üzeri miktarlarda "
                f"güvenlik planı değerlendirmesi gereklidir; kesin sonuç için "
                f"sevkiyat miktarı esas alınmalıdır."))
        return base

    @classmethod
    def screen_inventory(cls, chemicals: list) -> dict:
        """Firmanın tüm kimyasal envanterini tarar ve özet + kalem bazlı
        sonuçları döndürür."""
        results = [cls.screen_inventory_chemical(c) for c in chemicals]
        in_scope = sum(1 for r in results if r["in_scope"] is True)
        conditional = sum(1 for r in results if r["in_scope"] == "conditional")
        exempt = sum(1 for r in results if r["in_scope"] is False)
        return {
            "results": results,
            "in_scope_count": in_scope,
            "conditional_count": conditional,
            "exempt_count": exempt,
            "total": len(results),
        }


    @classmethod
    def generate_inventory_review_html(cls, company_name: str, prepared_by: str,
                                       approved_by: str, screen_result: dict,
                                       date_str: str = "", validity_years: int = 2,
                                       logo_b64: str = "") -> str:
        """Örnek 'Güvenlik Planı İnceleme Raporu' formatında çok sayfalı HTML
        üretir: kapak + Tablo 1.10.3.1.2 referansı + madde bazlı değerlendirme
        + sonuç/imza sayfası. QTextDocument + QPrinter ile yazdırılabilir/
        PDF'e aktarılabilir (aynı doküman diğer evrak önizlemelerinde
        kullanılan mimariyle uyumludur)."""
        from datetime import datetime as _dt
        date_str = date_str or _dt.now().strftime("%d/%m/%Y")
        results = screen_result.get("results", [])
        in_scope_items = [r for r in results if r["in_scope"] is True]
        cond_items = [r for r in results if r["in_scope"] == "conditional"]
        exempt_items = [r for r in results if r["in_scope"] is False]

        NAVY = "#1E293B"
        MUTED = "#64748B"

        # ── Antet filigranı: varsa firma logosu (soluk), yoksa boş ──────
        watermark_b64 = ""
        try:
            # ShipmentEditorPage'deki paylaşılan filigran üreticisini
            # (logo + gerekiyorsa TASLAK yazısı) burada da kullan.
            watermark_b64 = ShipmentEditorPage._build_letterhead_watermark_b64(
                logo_b64, True)  # rapor onaylı belge niteliğinde, TASLAK yazısı yok
        except Exception:
            watermark_b64 = ""

        wrap_open = (
            f'<table width="100%" style="border-collapse:separate;'
            f'background-image:url(data:image/png;base64,{watermark_b64});'
            f'background-repeat:no-repeat;background-position:center top;">'
            f'<tr><td style="padding:0;">'
        ) if watermark_b64 else ""
        wrap_close = "</td></tr></table>" if watermark_b64 else ""

        def _esc(t):
            return (str(t or "")
                    .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

        # ── Sayfa 1: Kapak ────────────────────────────────────────────
        cover = f"""
<div style="border:2px solid #333; padding:40px; margin:20px; page-break-after:always;">
  <table width="100%"><tr>
    <td style="font-size:16pt; font-weight:bold;">{_esc(company_name) or 'FİRMA ADI'}</td>
    <td align="right" style="color:{MUTED}; font-size:9pt;">METKA</td>
  </tr></table>
  <div style="height:220px;"></div>
  <p align="center" style="font-size:15pt; font-weight:bold; color:{NAVY};">
    {_esc(company_name) or 'FİRMA ADI'}
  </p>
  <p align="center" style="font-size:18pt; font-weight:bold; color:{NAVY}; margin-top:20px;">
    GÜVENLİK PLANI İNCELEME RAPORU
  </p>
  <div style="height:120px;"></div>
  <p align="center" style="font-size:11pt;">{date_str}</p>
  <p align="center" style="font-size:10pt; color:{MUTED};">Geçerlilik Süresi: {validity_years} Yıl</p>
  <div style="height:40px;"></div>
  <table width="100%" style="border-collapse:collapse;">
    <tr>
      <td width="50%" style="border:1px solid #999; padding:10px;">
        <b>Hazırlayan:</b> Tehlikeli Madde Güvenlik Danışmanı<br><br>
        {_esc(prepared_by) or '&nbsp;'}
      </td>
      <td width="50%" style="border:1px solid #999; padding:10px;">
        <b>Onaylayan:</b><br><br>
        {_esc(approved_by) or '&nbsp;'}
      </td>
    </tr>
  </table>
</div>"""

        # ── Sayfa 2: ADR Tablo 1.10.3.1.2 referans tablosu ──────────────
        table_rows = [
            ("1", "1.1", "Patlayıcılar", "a", "a", "0"),
            ("1", "1.2", "Patlayıcılar", "a", "a", "0"),
            ("1", "1.3", "Uyumluluk grubu C patlayıcılar", "a", "a", "0"),
            ("1", "1.4", "Patlayıcılar, UN No. 0104, 0237, 0255, 0267, 0289, 0361, "
                          "0365, 0366, 0440, 0441, 0455, 0456 ve 0500", "a", "a", "0"),
            ("1", "1.5", "Patlayıcılar", "0", "a", "0"),
            ("2", "", "Alevlenebilir gazlar (Yalnızca F harfi içeren sınıflandırma kodları)", "3000", "a", "b"),
            ("2", "", "Zehirli gazlar (T, TF, TC, TO, TFC veya TOC harflerini içeren "
                       "sınıflandırma kodları) aerosoller hariç", "0", "a", "0"),
            ("3", "", "Ambalajlama grubu I ve II'deki alevlenebilir sıvılar", "3000", "a", "b"),
            ("3", "", "Duyarlılığı azaltılmış patlayıcılar", "0", "a", "0"),
            ("4.1", "", "Duyarlılığı azaltılmış patlayıcılar", "a", "a", "0"),
            ("4.2", "", "Ambalajlama grubu I'deki maddeler", "3000", "a", "b"),
            ("4.3", "", "Ambalajlama grubu I'deki maddeler", "3000", "a", "b"),
            ("5.1", "", "Ambalajlama grubu I'deki yükseltgen sıvılar", "3000", "a", "b"),
            ("5.1", "", "Perkloratlar, amonyum nitrat, amonyum nitrat gübreler ve "
                        "amonyum nitrat emülsiyonlar veya süspansiyonlar veya jeller", "3000", "3000", "b"),
            ("6.1", "", "Ambalajlama grubu I'deki zehirli maddeler", "0", "a", "0"),
            ("6.2", "", "Kategori A'daki bulaşıcı maddeler (UN No. 2814 ve 2900 "
                        "hayvansal malzemeler hariç)", "a", "0", "0"),
            ("8", "", "Ambalajlama grubu I'deki aşındırıcı maddeler", "3000", "a", "b"),
        ]
        rows_html = "".join(
            f'<tr><td>{s}</td><td>{sg}</td><td>{_esc(m)}</td>'
            f'<td align="center">{t}</td><td align="center">{bl}</td>'
            f'<td align="center">{am}</td></tr>'
            for s, sg, m, t, bl, am in table_rows
        )
        table_page = f"""
<div style="padding:20px; page-break-after:always;">
  <p>Ciddi sonuçlara neden olabilecek maddelerin incelemesi ADRBOOK 1.10.3.1.2
  referans alınarak sonuçlar oluşturulmuştur.</p>
  <p style="font-weight:bold; font-size:11pt;">ADR TABLO 1.10.3.1.2</p>
  <table width="100%" border="1" style="border-collapse:collapse; font-size:8pt;">
    <tr style="background:#DDDDDD; font-weight:bold;">
      <td>Sınıf</td><td>Alt Grup</td><td>Madde veya nesne</td>
      <td align="center">Tank (l)</td><td align="center">Dökme yük (kg)</td>
      <td align="center">Ambalajlar (kg)</td>
    </tr>
    {rows_html}
  </table>
  <p style="font-size:8pt; margin-top:10px;">
    a: İlgili değil<br>
    b: Miktar ne olursa olsun 1.10.3 hükümleri uygulanmaz.<br>
    c: Bu sütunda belirtilen bir değer, tanklarda taşıma için izin verilmişse geçerlidir.<br>
    d: Bu sütunda belirtilen bir değer, dökme yük taşıma için izin verilmişse geçerlidir.
  </p>
</div>"""

        # ── Sayfa 3: Madde bazlı değerlendirme ──────────────────────────
        def _row(r, color):
            return (f'<tr><td>UN{_esc(r["un_number"])}<br>'
                    f'<span style="font-size:7.5pt;color:{MUTED}">{_esc(r["name"])}</span></td>'
                    f'<td align="center">{_esc(r["classification_code"]) or chr(0x2014)}</td>'
                    f'<td style="font-size:8pt;">{_esc(r["sonuc_text"])}</td>'
                    f'<td align="center">{_esc(r["class_code"])}</td>'
                    f'<td align="center">{_esc(r["packing_group"]) or chr(0x2014)}</td></tr>')

        eval_rows = "".join(_row(r, "#DC2626") for r in in_scope_items)
        eval_rows += "".join(_row(r, "#D97706") for r in cond_items)
        eval_rows += "".join(_row(r, "#166534") for r in exempt_items)

        eval_page = f"""
<div style="padding:20px; page-break-after:always;">
  <p style="font-weight:bold; font-size:11pt;">
    CİDDİ SONUÇLARA NEDEN OLABİLECEK MADDELER İNCELEMESİ
    (ADR BOOK 1.10.3.1.2 referans alınarak sonuçlar oluşturulmuştur.)
  </p>
  <table width="100%" border="1" style="border-collapse:collapse; font-size:8pt;">
    <tr style="background:#DDDDDD; font-weight:bold;">
      <td>UN No / Madde</td><td>Sınıflandırma Kodu</td><td>SONUÇ</td>
      <td>SINIF</td><td>PG</td>
    </tr>
    {eval_rows if eval_rows else '<tr><td colspan="5" align="center">Envanterde kimyasal bulunamadı</td></tr>'}
  </table>
</div>"""

        # ── Sayfa 4: Sonuç ve imzalar ────────────────────────────────────
        if in_scope_items or cond_items:
            un_list = ", ".join(f"UN{_esc(r['un_number'])}" for r in (in_scope_items + cond_items))
            conclusion_text = (
                f"Yukarıda incelemeleri yapılmış olan ADR'ye tabi kimyasallardan "
                f"<b>{len(in_scope_items) + len(cond_items)} tanesi</b> "
                f"({un_list}) Tablo 1.10.3.1.2 kapsamına girmektedir. "
                f"Bu maddeler için <b>GÜVENLİK PLANI HAZIRLANMASI GEREKLİDİR.</b> "
                f"Diğer {len(exempt_items)} kimyasal için güvenlik planı hazırlanmasına "
                f"gerek yoktur."
            )
        else:
            conclusion_text = (
                "Ciddi sonuçlara neden olabilecek tehlikeli malların veya ciddi "
                "sonuçlara neden olabilecek radyoaktif malzemelerin taşınmasına dahil "
                "olan, dolduran, paketleyen, yükleyen, gönderen, alıcı, boşaltan ve "
                "tank-konteyner/taşınabilir tank işletmecisi herhangi bir acil durum "
                "oluştuğunda hemen organize olarak, düzenli bir şekilde müdahale etmek "
                "ve ortaya çıkabilecek olan zararları en az seviyeye indirebilmesi için "
                "güvenlik planı incelenmesi gerçekleştirilmiştir.<br><br>"
                "Bu hususta yukarıda incelemeleri yapılmış olan ADR'ye tabi kimyasallar "
                "için <b>GÜVENLİK PLANI HAZIRLANMASINA GEREK YOKTUR.</b>"
            )

        conclusion_page = f"""
<div style="padding:20px;">
  <p>{conclusion_text}</p>
  <div style="height:60px;"></div>
  <table width="100%" style="border-collapse:collapse;">
    <tr>
      <td width="50%" style="padding:10px;">
        Tehlikeli Madde Güvenlik Danışmanlığı<br><br>
        {_esc(prepared_by) or '&nbsp;'}
      </td>
      <td width="50%" style="padding:10px;">
        {_esc(company_name) or '&nbsp;'}<br><br>
        {_esc(approved_by) or '&nbsp;'}
      </td>
    </tr>
  </table>
  <p style="font-size:8pt; color:{MUTED}; margin-top:30px;">
    Değerlendirilen kimyasal sayısı: {len(results)} &nbsp;|&nbsp;
    Kapsam içi: {len(in_scope_items)} &nbsp;|&nbsp;
    Koşullu: {len(cond_items)} &nbsp;|&nbsp;
    Muaf: {len(exempt_items)}
  </p>
</div>"""

        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body {{ font-family: 'Segoe UI', Arial, sans-serif; font-size:9.5pt; color:#1F2937; }}
</style></head><body>
{wrap_open}
{cover}
{table_page}
{eval_page}
{conclusion_page}
{wrap_close}
</body></html>"""




class ADREngine:
    """ADR mevzuat hesaplamalari ve dogrulamalari."""

    TC_POINTS = {"0": 0, "1": 50, "2": 3, "3": 1, "4": 0}

    @classmethod
    def calculate_1136_points(cls, items: List[ShipmentItem]) -> Tuple[float, bool, str]:
        """
        ADR 1.1.3.6 Miktar Muafiyeti (1000 Puan Kurali)

        Tasima Kategorileri ve Puanlari:
        - TC 0: 0 puan (EQ maddeler)
        - TC 1: 50 puan (Cok tehlikeli)
        - TC 2: 3 puan (Tehlikeli)
        - TC 3: 1 puan (Az tehlikeli)
        - TC 4: 0 puan (LQ maddeler)

        Toplam 1000 puani asarsa turuncu plaka zorunlu.
        """
        total = 0.0
        detail_lines = []
        # TC=4 olan kalemler (sınırsız taşınabilir) ayrı takip edilir
        tc4_items = []

        for item in items:
            if item.is_lq:
                points_per_unit = 0
                detail_lines.append(f"  UN{item.un_number}: LQ → 0 puan (sınırsız)")
            elif item.is_eq:
                points_per_unit = 0
                detail_lines.append(f"  UN{item.un_number}: EQ → 0 puan (sınırsız)")
            else:
                raw_tc = str(getattr(item, "transport_category", "")).strip()
                tc = raw_tc.split()[0] if raw_tc else ""

                # [GUVENLIK] Bos/gecersiz TC: hesaptan ATLANMAZ — en
                # kisitlayici carpan (x50) uygulanir ve acikca uyarilir.
                # Atlamak puani dusuk gosterip plakasiz sevkiyata yol acar.
                if not tc or tc not in cls.TC_POINTS:
                    detail_lines.append(
                        f"  ⚠ UN{item.un_number}: Taşıma Kategorisi boş/geçersiz"
                        f" ('{raw_tc}') — GÜVENLİ TARAF: x50 uygulandı,"
                        f" kategoriyi veritabanında tamamlayın!"
                    )
                    tc = "1"

                # [GUVENLIK] Kategori 0: miktar ne olursa olsun 1.1.3.6
                # muafiyeti MUMKUN DEGIL — turuncu plaka zorunlu.
                if tc == "0":
                    detail_lines.append(
                        f"  ⛔ UN{item.un_number}: Kategori 0 — muafiyet"
                        f" mümkün değil, TURUNCU PLAKA ZORUNLU"
                    )
                    total = float(MAX_1136_POINTS) + 1  # limiti asir
                    continue

                points_per_unit = cls.TC_POINTS[tc]

                # [DÜZELTİLDİ] TC=4: ADR 3.4/3.5 kapsamında sınırsız taşıma
                # 0 puan verir, 1000 puan limitine dahil edilmez
                if tc == "4":
                    tc4_items.append(item)
                    detail_lines.append(
                        f"  UN{item.un_number}: TC=4 → 0 puan"
                        f" (ADR 3.4 — sınırsız, limite dahil değil)"
                    )
                    continue  # toplama ekleme

                line_total = float(item.net_quantity) * points_per_unit
                detail_lines.append(
                    f"  UN{item.un_number}: TC={tc} → {points_per_unit} puan/kg"
                    f" × {item.net_quantity} {item.unit} = {line_total:.1f} puan"
                )

            total += float(item.net_quantity) * points_per_unit

        required = total > MAX_1136_POINTS

        # TC=4 notu varsa özete ekle
        if tc4_items:
            detail_lines.append(
                f"  ℹ TC=4 kalem sayısı: {len(tc4_items)} "
                f"— ADR 3.4 kapsamında puan hesabına dahil edilmedi"
            )

        # [DÜZELTİLDİ] Puan 0 ise (tüm kalemler TC=4, LQ, EQ veya boş TC)
        # "gerekmez" mesajı yerine bilgilendirici mesaj göster
        if total == 0 and not required:
            if tc4_items or any(i.is_lq or i.is_eq for i in items):
                msg = f"Puan hesabı 0 — tüm kalemler sınırsız kategoride (TC=4/LQ/EQ)"
            else:
                msg = f"Puan hesabı 0 — Taşıma Kategorisi girilmemiş kalemler var"
        elif required:
            msg = f"TURUNCU PLAKA ZORUNLU! ({total:.0f} / {MAX_1136_POINTS} Puan)"
        else:
            msg = f"Turuncu plaka gerekmez ({total:.0f} / {MAX_1136_POINTS} Puan)"

        detail_lines.insert(0, f"=== 1.1.3.6 PUAN HESAPLAMA ===")
        detail_lines.append(f"TOPLAM: {total:.1f} puan")
        detail_lines.append(f"SONUC: {msg}")

        return total, required, "\n".join(detail_lines)

    @classmethod
    def calculate_tunnel_restriction(cls, items: List[ShipmentItem]) -> str:
        if not items:
            return "E"

        most_restrictive = "E"
        for item in items:
            # "D/E", "(C/D)" gibi bilesik kodlar: en kisitlayici bilesen esas
            raw = (item.tunnel_code or "E").replace("(", "").replace(")", "")
            for code in raw.split("/"):
                code = code.strip().upper()
                if code in TUNNEL_HIERARCHY:
                    if TUNNEL_HIERARCHY[code] < TUNNEL_HIERARCHY[most_restrictive]:
                        most_restrictive = code

        return most_restrictive

    @classmethod
    def check_compatibility(cls, items: List[ShipmentItem]) -> List[str]:
        errors = []
        groups = set()

        CLASS_TO_SEGREGATION = {
            "3":   "Yanici Maddeler",
            "5.1": "Yukseltgenler",
            "5.2": "Organik Peroksitler",
            "8":   "Asitler",
            "4.3": "Su ile Tepki Veren",
            "2.3": "2.3 Sinifi Zehirli Gazlar",
        }

        for item in items:
            class_code = item.class_code or ""
            seg_group = CLASS_TO_SEGREGATION.get(class_code)
            if seg_group:
                groups.add(seg_group)
            if item.segregation_group:
                groups.add(item.segregation_group)

        seen_pairs = set()
        for group in groups:
            incompatible = INCOMPATIBILITY_MATRIX.get(group, [])
            for other in groups:
                if other != group and other in incompatible:
                    pair_key = tuple(sorted((group, other)))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    errors.append(f"UYUMSUZ: {group} + {other} birlikte tasinamaz!")

        return errors

    # ------------------------------------------------------------------
    # LQ (ADR 3.4) / EQ (ADR 3.5) — maddeye ozgu limitler
    # Sinif-bazli sabit tablolar KALDIRILDI: LQ limiti Tablo A sutun 7a'da
    # UN bazinda, EQ limiti sutun 7b E-kodu ile belirlenir.
    # ------------------------------------------------------------------
    EQ_TABLE = {
        "E0": (0, 0),
        "E1": (30, 1000),
        "E2": (30, 500),
        "E3": (30, 300),
        "E4": (1, 500),
        "E5": (1, 300),
    }

    @staticmethod
    def parse_date_flexible(text) -> Optional[datetime]:
        """Tarihi yaygin Turk ve ISO bicimlerinde ayristirir.
        Kabul: 2027-12-31, 31.12.2027, 31/12/2027, 31-12-2027.
        Uymazsa None doner; cagiran taraf ACIK hata uretmelidir."""
        raw = str(text or "").strip()
        if not raw:
            return None
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                continue
        return None

    @classmethod
    def parse_lq_limit(cls, text) -> Tuple[float, str]:
        """Tablo A 7a metnini ("1 L", "5 kg", "500 ml", "0") ayristirir.
        Donus: (deger, birim) — L veya kg'a normalize; yasaksa (0.0, "")."""
        if text is None:
            return 0.0, ""
        raw = str(text).strip()
        if raw == "" or raw.lower() in ("nan", "-", "yok", "none", "0"):
            return 0.0, ""
        m = re.match(r"^\s*(\d+(?:[.,]\d+)?)\s*(l|lt|litre|ml|kg|g|gr)?",
                     raw, re.IGNORECASE)
        if not m:
            return 0.0, ""
        value = float(m.group(1).replace(",", "."))
        unit = (m.group(2) or "kg").lower()
        if unit == "ml":
            return value / 1000.0, "L"
        if unit in ("l", "lt", "litre"):
            return value, "L"
        if unit in ("g", "gr"):
            return value / 1000.0, "kg"
        return value, "kg"

    @classmethod
    def eq_limits(cls, code) -> Tuple[int, int]:
        """E-kodu -> (ic, dis) g/ml limiti; taninmayan kod = (0, 0)."""
        key = str(code or "").strip().upper()
        return cls.EQ_TABLE.get(key, (0, 0))

    @classmethod
    def is_lq_allowed(cls, chemical: Chemical) -> bool:
        limit, _ = cls.parse_lq_limit(getattr(chemical, "limited_quantity", ""))
        if limit > 0:
            return True
        if not str(getattr(chemical, "limited_quantity", "") or "").strip():
            return bool(chemical.lq_allowed)  # eski kayit: boolean'a saygi
        return False

    @classmethod
    def is_eq_allowed(cls, chemical: Chemical) -> bool:
        code = str(getattr(chemical, "excepted_quantity", "") or "").strip().upper()
        if code:
            return cls.eq_limits(code)[0] > 0
        return bool(chemical.eq_allowed)

    @classmethod
    def check_lq_eligibility(cls, chemical: Chemical, quantity: float,
                              unit: str = "") -> Tuple[bool, str, float]:
        """Ic ambalaj basina miktari MADDENIN KENDI 7a limitiyle karsilastirir."""
        max_qty, limit_unit = cls.parse_lq_limit(
            getattr(chemical, "limited_quantity", ""))

        if max_qty <= 0:
            if (not str(getattr(chemical, "limited_quantity", "") or "").strip()
                    and chemical.lq_allowed):
                return True, ("LQ isaretli (eski kayit, limit bilgisi yok - "
                              "Tablo A'dan dogrulayin)"), 0.0
            return False, "Bu madde LQ olarak tasinamaz (7a = 0)", 0.0

        VOLUME = {"l", "lt", "litre", "ml"}
        MASS = {"kg", "g", "gr"}
        unit_note = ""
        u = str(unit or "").strip().lower()
        if u:
            entered_family = "L" if u in VOLUME else ("kg" if u in MASS else "?")
            if entered_family == "?" or entered_family != limit_unit:
                unit_note = (f" | UYARI: birim uyusmuyor (limit {limit_unit}, "
                             f"girilen {unit}) - manuel dogrulayin")

        if quantity > max_qty:
            return False, (f"LQ limiti asildi: {quantity:g} > "
                           f"{max_qty:g} {limit_unit}{unit_note}"), max_qty
        return True, f"LQ uygun (Max: {max_qty:g} {limit_unit}/ic ambalaj){unit_note}", max_qty

    @classmethod
    def check_eq_eligibility(cls, chemical: Chemical,
                             inner_quantity_g_ml: float) -> Tuple[bool, str, float]:
        """Ic ambalaj basina miktari (g/ml) maddenin E-koduna gore denetler."""
        code = str(getattr(chemical, "excepted_quantity", "") or "").strip().upper()

        if not code:
            if chemical.eq_allowed:
                return True, ("EQ isaretli (eski kayit, E-kodu yok - "
                              "Tablo A'dan dogrulayin)"), 0.0
            return False, "Bu madde EQ olarak tasinamaz (E-kodu yok)", 0.0

        inner, outer = cls.eq_limits(code)
        if inner <= 0:
            return False, f"Bu madde EQ olarak tasinamaz (kod: {code})", 0.0

        if inner_quantity_g_ml > inner:
            return False, (f"EQ limiti asildi ({code}): {inner_quantity_g_ml:g} > "
                           f"{inner} g/ml ic ambalaj (dis max {outer} g/ml)"), float(inner)
        return True, (f"EQ uygun ({code}: ic {inner} g/ml, "
                      f"dis {outer} g/ml)"), float(inner)

    @classmethod
    def verify_chemicals_data(cls, items: List[ShipmentItem]) -> List[dict]:
        """
        Eksik veya geçersiz veri içeren kimyasalları tespit eder.

        ADR 1.1.3.6 puan hesaplamasını ve tünel kodu atamasını
        olumsuz etkileyebilecek sorunları raporlar.

        Returns:
            List[dict]: Her sorun için {'un': ..., 'sorun': ...} içeren liste.
                        Liste boşsa tüm veriler tamdır.
        """
        sorunlar = []
        for item in items:
            un = getattr(item, "un_number", "?")
            un_str = f"UN{un}"

            # Taşıma Kategorisi (TC) kontrolü
            raw_tc = str(getattr(item, "transport_category", "") or "").strip()
            tc = raw_tc.split()[0] if raw_tc else ""
            if not item.is_lq and not item.is_eq:
                if not tc:
                    sorunlar.append({
                        "un": un_str,
                        "sorun": "Taşıma Kategorisi (TC) boş — 1.1.3.6 puan hesaplanamaz."
                    })
                elif tc not in cls.TC_POINTS:
                    sorunlar.append({
                        "un": un_str,
                        "sorun": f"Taşıma Kategorisi geçersiz: '{tc}' (geçerli: 0,1,2,3,4)."
                    })

            # Tünel Kodu kontrolü
            tun = getattr(item, "tunnel_code", "") or ""
            valid_tunnels = {"A", "B", "B1", "B/D", "B/E", "C", "C/D", "C/E", "D", "D/E", "E"}
            if tun and tun.upper() not in {t.upper() for t in valid_tunnels}:
                sorunlar.append({
                    "un": un_str,
                    "sorun": f"Tünel kodu geçersiz: '{tun}'."
                })

            # Net miktar sıfır veya negatif kontrolü
            try:
                qty = float(item.net_quantity or 0)
            except (TypeError, ValueError):
                qty = 0
            if qty <= 0:
                sorunlar.append({
                    "un": un_str,
                    "sorun": f"Net miktar sıfır veya negatif: {item.net_quantity!r}."
                })

        return sorunlar

    @classmethod
    def generate_adr_report(cls, items: List[ShipmentItem],
                             driver: Driver = None,
                             vehicle: Vehicle = None,
                             packaging_types: List[str] = None) -> ADRReport:
        """
        ADR raporu oluştur - muafiyetleri doğru değerlendir.

        Muafiyet Hiyerarşisi:
        1. EQ (İstisnai Miktar) - En üst düzey muafiyet
        2. LQ (Sınırlı Miktar)
        3. ADR 1.1.3.6 (Miktar Muafiyeti - 1000 Puan)
        4. Özel Hükümler (SP kodları)
        5. Genel Muafiyetler (1.1.3.1)
        """
        report = ADRReport()
        packaging_types = packaging_types or []

        if not items:
            report.info.append((WarningLevel.INFO, "Sevkiyat bos"))
            return report

        # === TC DURUM SINIFLANDIRMASI ===
        aktif = [i for i in items if float(i.net_quantity or 0) > 0]
        lq_count     = sum(1 for i in aktif if i.is_lq)
        eq_count     = sum(1 for i in aktif if i.is_eq)
        tc4_count    = sum(1 for i in aktif
                          if not i.is_lq and not i.is_eq and
                          str(getattr(i, "transport_category", "")).strip().split()[0:1] == ["4"])
        empty_tc_count = sum(1 for i in aktif
                             if not i.is_lq and not i.is_eq and
                             not str(getattr(i, "transport_category", "")).strip())
        normal_count = len(aktif) - lq_count - eq_count - tc4_count - empty_tc_count

        # TC boş kalemler varsa: puan hesabı yapılamaz, rapor kısmi gösterilir
        has_empty_tc = empty_tc_count > 0
        # Hesaplanabilir kalem var mı (TC=4/LQ/EQ veya normal TC)
        has_calculable = (lq_count + eq_count + tc4_count + normal_count) > 0

        if has_empty_tc:
            report.warnings.append((WarningLevel.WARNING,
                f"{empty_tc_count} kalemin Taşıma Kategorisi boş — "
                "puan hesabına dahil edilmedi. Excel'i kontrol edin."))

        # === 1.1.3.6 PUAN HESAPLAMA ===
        total_points, orange_required, points_detail = cls.calculate_1136_points(items)
        report.total_points = total_points
        report.orange_plate_required = orange_required

        # Puan sadece hesaplanabilir kalem varsa göster
        if total_points > 0:
            if orange_required:
                report.errors.append((WarningLevel.ERROR,
                    f"TURUNCU PLAKA ZORUNLU! ({total_points:.0f} / {MAX_1136_POINTS} Puan)"))
            else:
                report.info.append((WarningLevel.INFO,
                    f"Turuncu plaka gerekmez ({total_points:.0f} / {MAX_1136_POINTS} Puan)"))
            report.info.append((WarningLevel.INFO, points_detail))
        elif tc4_count > 0 and not has_empty_tc:
            report.info.append((WarningLevel.INFO,
                f"TC=4 kalemler sınırsız taşınabilir (ADR 3.4) — puan limiti uygulanmaz"))
        elif lq_count > 0 or eq_count > 0:
            report.info.append((WarningLevel.INFO,
                "LQ/EQ muafiyetli kalemler — puan limiti uygulanmaz"))

        # === TUNEL KISITLAMA ===
        tunnel = cls.calculate_tunnel_restriction(items)
        report.tunnel_code = tunnel
        report.info.append((WarningLevel.INFO, f"Tunel kisitlama kodu: {tunnel}"))
        if tunnel == "A":
            report.errors.append((WarningLevel.CRITICAL,
                "Tunel kodu A: Bu sevkiyat tunelden gecemez!"))
        elif tunnel in ["B", "C"]:
            report.warnings.append((WarningLevel.WARNING,
                f"Tunel kodu {tunnel}: Kisitli tunel gecisi"))

        # === UYUMSUZLUK KONTROLU ===
        compat_errors = cls.check_compatibility(items)
        for err in compat_errors:
            report.errors.append((WarningLevel.CRITICAL, err))
        report.compatibility_errors = compat_errors

        # === LQ / EQ DURUMU ===
        if lq_count > 0:
            report.lq_status = f"{lq_count} kalemden LQ (Sinirli Miktar) uygulandi"
            report.info.append((WarningLevel.INFO, report.lq_status))
        if eq_count > 0:
            report.eq_status = f"{eq_count} kalemden EQ (Istisnai Miktar) uygulandi"
            report.info.append((WarningLevel.INFO, report.eq_status))

        # === [v4.4] LQ/EQ İŞARETLİ KALEMLERDE MADDEYE ÖZGÜ LİMİT DENETİMİ ===
        # LQ/EQ kutucuğu işaretlenmiş olması muafiyeti otomatik geçerli
        # kılmaz — iç ambalaj başına miktar, maddenin kendi 7a/7b limitini
        # aşıyorsa muafiyet GEÇERSİZDİR ve kritik hata üretilmelidir.
        for it in aktif:
            per_pkg = (float(it.net_quantity) / it.packaging_count
                       if it.packaging_count else float(it.net_quantity))
            if it.is_lq and it.lq_max_per_package > 0 and per_pkg > it.lq_max_per_package:
                report.errors.append((WarningLevel.CRITICAL,
                    f"UN {it.un_number}: LQ limiti asiliyor "
                    f"({per_pkg:g} > {it.lq_max_per_package:g} / ic ambalaj). "
                    f"LQ muafiyeti GECERSIZ!"))
            if it.is_eq and it.eq_max_per_package > 0:
                per_pkg_g = per_pkg * 1000  # kg/L -> g/ml
                if per_pkg_g > it.eq_max_per_package:
                    report.errors.append((WarningLevel.CRITICAL,
                        f"UN {it.un_number}: EQ ic ambalaj limiti asiliyor "
                        f"({per_pkg_g:g} g/ml > {it.eq_max_per_package:g} g/ml). "
                        f"EQ muafiyeti GECERSIZ!"))

        if tc4_count > 0:
            report.info.append((WarningLevel.INFO,
                f"{tc4_count} kalem TC=4 (sınırsız, ADR 3.4 kapsamı)"))
        if normal_count > 0:
            report.info.append((WarningLevel.INFO,
                f"{normal_count} kalem normal ADR kurallarina tabi"))

        # === MUAFIYET DEĞERLENDİRMESİ ===
        # TC boş kalemler varken muafiyet belirsiz — hesaplama yapma
        if has_empty_tc and not has_calculable:
            report.exemption_type = ExemptionType.NONE.value
            report.info.append((WarningLevel.INFO,
                "Muafiyet belirlenemiyor — Taşıma Kategorisi eksik"))
        elif eq_count > 0 and eq_count == len(aktif):
            report.exemption_type = ExemptionType.EQ.value
            report.info.append((WarningLevel.INFO,
                "TUMU EQ: ADR 3.5 Istisnai Miktar muafiyeti uygulanir"))
        elif lq_count > 0 and lq_count == len(aktif):
            report.exemption_type = ExemptionType.LQ.value
            report.info.append((WarningLevel.INFO,
                "TUMU LQ: ADR 3.4 Sinirli Miktar muafiyeti uygulanir"))
        elif tc4_count > 0 and (tc4_count + lq_count + eq_count) == len(aktif):
            # Sadece TC=4 / LQ / EQ → sınırsız
            report.exemption_type = ExemptionType.ADR_1_1_3_6.value
            report.info.append((WarningLevel.INFO,
                "Tüm kalemler TC=4/LQ/EQ — ADR 3.4 kapsamında sınırsız taşıma"))
        elif total_points > 0 and total_points <= MAX_1136_POINTS and normal_count > 0:
            report.exemption_type = ExemptionType.ADR_1_1_3_6.value
            report.info.append((WarningLevel.INFO,
                f"ADR 1.1.3.6: Miktar muafiyeti uygulanir ({total_points:.0f} < {MAX_1136_POINTS} puan)"))
        elif any(item.special_provisions for item in items if hasattr(item, 'special_provisions')):
            report.exemption_type = ExemptionType.SPECIAL_PROVISION.value
            report.info.append((WarningLevel.INFO,
                "ADR 3.3: Ozel hukumler kapsaminda muafiyet degerlendirildi"))
        else:
            report.exemption_type = ExemptionType.NONE.value
            report.info.append((WarningLevel.INFO,
                "Muafiyet yok - Tam ADR uygulamasi zorunlu"))

        # === YAZILI TALİMAT ===
        # TC boş ve hesaplanabilir kalem yoksa yazılı talimat da belirsiz
        if not has_calculable and has_empty_tc:
            pass  # Gösterme
        else:
            has_class_1 = any((item.class_code or "").startswith("1") for item in items)
            has_class_7 = any(item.class_code == "7" for item in items)
            if has_class_1 or has_class_7 or orange_required:
                report.written_instructions_required = True
                report.warnings.append((WarningLevel.WARNING,
                    "Yazili talimat zorunlu (ADR 8.1.2.1)"))
            else:
                report.info.append((WarningLevel.INFO, "Yazili talimat gerekmez"))

        # === SÜRÜCÜ ADR SERTİFİKA ===
        if not has_calculable and has_empty_tc:
            pass  # TC boş, sertifika kontrolü yapma
        else:
            has_tank = any(pt == "Tank" for pt in packaging_types) if packaging_types else False
            if orange_required or any(
                (item.class_code or "").startswith("1") or
                item.class_code in ["2.3", "6.2", "7"]
                for item in items
            ):
                report.driver_adr_required = True
                if driver:
                    # DÜZELTME (Umut'un talebi): "ADR Belge No/Bitiş" alanları
                    # sürücüyle ilgisiz olduğu için Driver modelinden TAMAMEN
                    # kaldırıldı — bu yüzden buradaki doğrulama da kaldırıldı.
                    # driver_adr_required bayrağı (üstteki satır) hâlâ
                    # hesaplanıyor ve evraktaki ZORUNLU/GEREKMEZ rozetini
                    # besliyor; yalnızca artık var olmayan sertifika
                    # alanlarına karşı YAPILAN DOĞRULAMA kaldırıldı.
                    if not driver.src5_no:
                        report.errors.append((WarningLevel.CRITICAL, "SRC5 belgesi zorunlu!"))
                    else:
                        report.info.append((WarningLevel.INFO, f"SRC5 belgesi: {driver.src5_no}"))
                else:
                    report.errors.append((WarningLevel.CRITICAL, "Surucu bilgisi eksik!"))

            if has_tank:
                report.warnings.append((WarningLevel.WARNING,
                    "Tank tasimasi: T9/Tasit Uygunluk Belgesi zorunlu!"))
                if vehicle:
                    if not vehicle.adr_compliance_cert_no:
                        report.errors.append((WarningLevel.CRITICAL,
                            "T9/Tasit Uygunluk Belgesi eksik!"))
                    else:
                        report.info.append((WarningLevel.INFO,
                            f"T9/Tasit Uygunluk Belgesi: {vehicle.adr_compliance_cert_no}"))

        # === ADR 1.10.3 EMNİYET PLANI ===
        try:
            sp = SecurityPlanEngine.check(
                items,
                transport_mode="ambalaj",
                total_1136_points=report.total_points,
            )
            report.security_plan_required = sp["required"]
            report.security_plan_exempt   = sp["exempt"]
            report.security_plan_reasons  = sp["reasons"]
            if sp["required"]:
                report.warnings.append((WarningLevel.WARNING,
                    "🛡 ADR 1.10.3: EMNİYET PLANI GEREKLİ — "
                    + "; ".join(sp["reasons"][:2])))
            elif sp["exempt"]:
                report.info.append((WarningLevel.INFO,
                    "✅ ADR 1.10.3: Emniyet planı gerekmiyor (1.10.4 muafiyeti)"))
        except Exception:
            pass

        return report
    @classmethod
    def validate_shipment(cls, items: List[ShipmentItem],
                           sender: Company = None,
                           receiver: Company = None,
                           driver: Driver = None,
                           vehicle: Vehicle = None,
                           packaging_types: List[str] = None) -> ValidationResult:
        """
        Sevkiyat validasyonu - ADR kurallarına uygunluk kontrolü.

        Zorunlu alanlar:
        - Ambalaj türü (IBC, Varil, Bidon, Kutu, Çuval, Kompozit Ambalaj, Tank, Dökme)
        - Miktar (> 0)
        - UN numarası
        - Sınıf bilgisi
        """
        result = ValidationResult()
        packaging_types = packaging_types or []

        if not items:
            result.errors.append((WarningLevel.ERROR, "En az bir urun eklenmeli"))
            return result

        # === ZORUNLU ALAN KONTROLLERI ===
        VALID_PACKAGING_TYPES = [
            "IBC", "Varil", "Bidon", "Kutu", 
            "Çuval", "Kompozit Ambalaj", "Tank", "Dökme"
        ]

        for i, item in enumerate(items, 1):
            # UN numarası kontrolü
            if not item.un_number:
                result.errors.append((WarningLevel.ERROR, f"Satir {i}: UN numarasi eksik"))

            # Sınıf kontrolü
            if not item.class_code:
                result.errors.append((WarningLevel.ERROR, f"Satir {i}: Sinif bilgisi eksik"))

            # Miktar kontrolü (> 0)
            if item.net_quantity <= 0:
                result.errors.append((WarningLevel.ERROR, 
                    f"Satir {i}: Miktar 0'dan buyuk olmali (Girilen: {item.net_quantity})"))

            # Ambalaj türü kontrolü (ZORUNLU)
            if not item.packaging_type:
                result.errors.append((WarningLevel.ERROR, 
                    f"Satir {i}: Ambalaj turu zorunlu! (Secenekler: {', '.join(VALID_PACKAGING_TYPES)})"))
            elif item.packaging_type not in VALID_PACKAGING_TYPES:
                result.warnings.append((WarningLevel.WARNING, 
                    f"Satir {i}: '{item.packaging_type}' standart ambalaj turu degil. "
                    f"Beklenen: {', '.join(VALID_PACKAGING_TYPES)}"))

            # Ambalaj adeti kontrolü
            if item.packaging_count <= 0:
                result.warnings.append((WarningLevel.WARNING, 
                    f"Satir {i}: Ambalaj adeti 0'dan buyuk olmali"))

            # Birim kontrolü
            if not item.unit:
                result.warnings.append((WarningLevel.WARNING, 
                    f"Satir {i}: Birim (kg/lt/adet) belirtilmemis"))

        # === FIRMA KONTROLLERI ===
        # [GUVENLIK] None kontrolu: firma HIC secilmemisse de hata uretilir
        # (eski kod "sender and ..." ile None durumunu sessizce geciyordu)
        if sender is None or not sender.name:
            result.errors.append((WarningLevel.ERROR, "Gonderici firma secilmemis"))
        if receiver is None or not receiver.name:
            result.errors.append((WarningLevel.ERROR, "Alici firma secilmemis"))

        # === SURUCU KONTROLLERI ===
        if driver:
            # SRC5 kontrolü (her zaman zorunlu)
            if not driver.src5_no:
                result.errors.append((WarningLevel.ERROR, "SRC5 belgesi zorunlu!"))
            else:
                src5_expiry = cls.parse_date_flexible(driver.src5_expiry)
                if src5_expiry is None:
                    result.errors.append((WarningLevel.ERROR,
                        f"SRC5 bitis tarihi okunamadi: '{driver.src5_expiry}' "
                        f"(desteklenen: 2027-12-31, 31.12.2027, 31/12/2027)"))
                elif src5_expiry < datetime.now():
                    result.errors.append((WarningLevel.ERROR, "SRC5 belgesi gecersiz!"))
                elif src5_expiry < datetime.now() + timedelta(days=30):
                    result.warnings.append((WarningLevel.WARNING,
                        "SRC5 belgesi yakinda bitiyor!"))

            # DÜZELTME (Umut'un talebi): "ADR sertifikası" alanı sürücüyle
            # ilgisiz olduğu için Driver modelinden tamamen kaldırıldı;
            # buna dayanan bu öneri kontrolü de kaldırıldı.
        else:
            result.errors.append((WarningLevel.ERROR, "Surucu secilmemis!"))

        # === ARAC KONTROLLERI ===
        if vehicle:
            # Muayene kontrolü
            if not str(vehicle.inspection_expiry or "").strip():
                result.warnings.append((WarningLevel.WARNING,
                    "Arac muayene tarihi kayitli degil"))
            else:
                inspection_expiry = cls.parse_date_flexible(vehicle.inspection_expiry)
                if inspection_expiry is None:
                    result.errors.append((WarningLevel.ERROR,
                        f"Arac muayene tarihi okunamadi: '{vehicle.inspection_expiry}' "
                        f"(desteklenen: 2027-12-31, 31.12.2027, 31/12/2027)"))
                elif inspection_expiry < datetime.now():
                    result.errors.append((WarningLevel.ERROR, "Arac muayenesi gecersiz!"))
                elif inspection_expiry < datetime.now() + timedelta(days=30):
                    result.warnings.append((WarningLevel.WARNING, "Arac muayenesi yakinda bitiyor"))

            # T9/Taşıt Uygunluk Belgesi kontrolü (sadece tank taşıması için)
            has_tank = any(pt == "Tank" for pt in packaging_types)
            if has_tank:
                if not vehicle.adr_compliance_cert_no:
                    result.errors.append((WarningLevel.CRITICAL, 
                        "Tank tasimasi: T9/Tasit Uygunluk Belgesi zorunlu!"))
                else:
                    adr_expiry = cls.parse_date_flexible(vehicle.adr_compliance_expiry)
                    if adr_expiry is None:
                        result.errors.append((WarningLevel.ERROR,
                            f"T9 gecerlilik tarihi okunamadi: "
                            f"'{vehicle.adr_compliance_expiry}' "
                            f"(desteklenen: 2027-12-31, 31.12.2027, 31/12/2027)"))
                    elif adr_expiry < datetime.now():
                        result.errors.append((WarningLevel.ERROR,
                            "T9/Tasit Uygunluk Belgesi gecersiz!"))
            else:
                # Tank değilse ADR uygunluk belgesi opsiyonel
                if vehicle.adr_compliance_cert_no:
                    result.info.append((WarningLevel.INFO, 
                        "T9/Tasit Uygunluk Belgesi mevcut (opsiyonel)"))
        else:
            result.errors.append((WarningLevel.ERROR, "Arac secilmemis!"))

        # === ADR RAPORU ===
        adr_report = cls.generate_adr_report(items, driver, vehicle, packaging_types)
        result.errors.extend(adr_report.errors)
        result.warnings.extend(adr_report.warnings)
        result.info.extend(adr_report.info)

        result.is_valid = len(result.errors) == 0

        return result
    @classmethod
    def get_class_color(cls, class_code: str) -> Tuple[str, str]:
        return CLASS_COLORS.get(class_code, ("#808080", "#FFFFFF"))

    @classmethod
    def format_document_number(cls) -> str:
        now = datetime.now()
        return f"ADR-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"


# =============================================================================
# KIMYASAL EKLE / DUZENLE DIALOG
# =============================================================================

