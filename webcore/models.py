"""Veri modelleri (monolitten satırı satırına)."""

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

class DocumentStatus(Enum):
    DRAFT     = "Taslak"
    VALIDATED = "Onaylandi"
    PRINTED   = "Yazdirildi"
    ARCHIVED  = "Arsivlendi"
    CANCELLED = "Iptal Edildi"

class WarningLevel(Enum):
    INFO     = "Bilgi"
    WARNING  = "Uyari"
    ERROR    = "Hata"
    CRITICAL = "Kritik"

class ExemptionType(Enum):
    """ADR Muafiyet Türleri - ADR Book 1.1.3"""
    NONE                    = "Yok"
    # 1.1.3.1 Genel (Tam) Muafiyetler
    PERSONAL_USE            = "ADR 1.1.3.1 - Kisisel Kullanim"
    MACHINERY_EQUIPMENT     = "ADR 1.1.3.1 - Makine/Ekipman Icindeki Maddeler"
    EMERGENCY_TRANSPORT     = "ADR 1.1.3.1 - Acil Durum Tasimasi"
    AGRICULTURE_FORESTRY    = "ADR 1.1.3.1 - Tarim ve Ormancilik"
    # 1.1.3.2 Gazlarin Tasinmasi
    GAS_TRANSPORT           = "ADR 1.1.3.2 - Gazlarin Tasinmasi"
    # 1.1.3.3 Sivi Yakitlar
    LIQUID_FUEL             = "ADR 1.1.3.3 - Sivi Yakitlar"
    # 1.1.3.6 Miktar Muafiyeti (1000 Puan Kurali)
    ADR_1_1_3_6             = "ADR 1.1.3.6 - Miktar Muafiyeti (1000 Puan)"
    # 3.4 Sinirli Miktar (LQ)
    LQ                      = "ADR 3.4 - Sinirli Miktar (LQ)"
    # 3.5 Istisnai Miktar (EQ)
    EQ                      = "ADR 3.5 - Istisnai Miktar (EQ)"
    # Ozel Hukumler (3.3)
    SPECIAL_PROVISION       = "ADR 3.3 - Ozel Hukumler"
    # Bos Ambalaj
    EMPTY_PACKAGING         = "Bos Ambalaj"
    # Numune
    SAMPLE                  = "Numune"
    # Kismi Muafiyet
    PARTIAL_EXEMPTION       = "Kismi Muafiyet"

# =============================================================================
# VERI MODELLERI (DATACLASSES)
# =============================================================================

@dataclass
class Company:
    id: Optional[int] = None
    type: str = "sender"
    name: str = ""
    tax_number: str = ""
    tax_office: str = ""
    mersis_no: str = ""
    address: str = ""
    city: str = ""
    district: str = ""
    phone: str = ""
    email: str = ""
    contact_person: str = ""
    is_favorite: bool = False
    logo_path: str = ""  # PDF antet arka plani icin firma logosu
    created_at: str = ""
    updated_at: str = ""

@dataclass
class Driver:
    id: Optional[int] = None
    full_name: str = ""
    tc_no: str = ""
    phone: str = ""
    adr_certificate_no: str = ""
    adr_certificate_expiry: str = ""
    src5_no: str = ""
    src5_expiry: str = ""
    license_class: str = ""
    license_expiry: str = ""
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""

@dataclass
class Vehicle:
    id: Optional[int] = None
    plate: str = ""
    trailer_plate: str = ""
    adr_compliance_cert_no: str = ""
    adr_compliance_expiry: str = ""
    inspection_date: str = ""
    inspection_expiry: str = ""
    tank_info: str = ""
    vehicle_type: str = ""
    max_capacity: float = 0.0
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""

@dataclass
class Chemical:
    id: Optional[int] = None
    un_number: str = ""
    classification_code: str = ""  # Tablo A 3b: 1.4G, F1, 5T vb. (varyant ayirici)
    proper_shipping_name_tr: str = ""
    proper_shipping_name_en: str = ""
    class_code: str = ""
    packing_group: str = ""
    tunnel_code: str = ""
    transport_category: str = ""
    segregation_group: str = ""
    special_provisions: str = ""
    lq_allowed: bool = False
    eq_allowed: bool = False
    limited_quantity: str = ""   # Tablo A 7a: "1 L", "5 kg", "0"
    excepted_quantity: str = ""  # Tablo A 7b: E0..E5
    hazard_labels: str = ""

@dataclass
class ShipmentItem:
    id: Optional[int] = None
    shipment_id: Optional[int] = None
    chemical_id: int = 0
    un_number: str = ""
    proper_name: str = ""
    class_code: str = ""
    packing_group: str = ""
    packaging_type: str = ""
    packaging_count: int = 0
    net_quantity: float = 0.0
    gross_quantity: float = 0.0
    unit: str = "kg"
    is_lq: bool = False
    is_eq: bool = False
    lq_max_per_package: float = 0.0
    eq_max_per_package: float = 0.0
    notes: str = ""
    tunnel_code: str = ""
    segregation_group: str = ""
    classification_code: str = ""
    transport_category: str = ""   # [DÜZELTİLDİ] "2" varsayılanı kaldırıldı
    special_provisions: str = ""

@dataclass
class Shipment:
    id: Optional[int] = None
    document_no: str = ""
    document_date: str = ""
    status: str = "Taslak"
    sender_id: int = 0
    receiver_id: int = 0
    carrier_id: int = 0
    driver_id: int = 0
    vehicle_id: int = 0
    total_points: float = 0.0
    orange_plate_required: bool = False
    written_instructions_required: bool = False
    driver_adr_required: bool = False
    tunnel_restriction_code: str = ""
    exemption_type: str = "Yok"
    is_validated: bool = False
    validation_errors: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""
    created_by: str = ""

@dataclass
class ValidationResult:
    is_valid: bool = False
    errors: List[Tuple[WarningLevel, str]] = None
    warnings: List[Tuple[WarningLevel, str]] = None
    info: List[Tuple[WarningLevel, str]] = None

    def __post_init__(self):
        if self.errors   is None: self.errors   = []
        if self.warnings is None: self.warnings = []
        if self.info     is None: self.info     = []

@dataclass
class ADRReport:
    total_points: float = 0.0
    orange_plate_required: bool = False
    written_instructions_required: bool = False
    driver_adr_required: bool = False
    tunnel_code: str = "E"
    exemption_type: str = "Yok"
    segregation_warnings: List[str] = None
    compatibility_errors: List[str] = None
    lq_status: str = ""
    eq_status: str = ""
    # ADR 1.10.3 — Emniyet Planı
    security_plan_required: bool = False
    security_plan_reasons: List[str] = None   # gerektiren kalemler
    security_plan_exempt: bool = False        # 1.10.4 muafiyeti var
    errors: List[Tuple[WarningLevel, str]] = None
    warnings: List[Tuple[WarningLevel, str]] = None
    info: List[Tuple[WarningLevel, str]] = None

    def __post_init__(self):
        if self.segregation_warnings  is None: self.segregation_warnings  = []
        if self.compatibility_errors  is None: self.compatibility_errors  = []
        if self.security_plan_reasons is None: self.security_plan_reasons = []
        if self.errors   is None: self.errors   = []
        if self.warnings is None: self.warnings = []
        if self.info     is None: self.info     = []

# =============================================================================
# GÜVENLİK YARDIMCI FONKSİYONLARI
# =============================================================================


