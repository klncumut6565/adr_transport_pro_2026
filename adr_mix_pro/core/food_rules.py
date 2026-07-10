"""Gıda, yem ve tüketim maddeleri ile ayrım (ADR 7.5.4, özel hüküm CV28).

ÖNEMLİ: CV28 kısıtlaması, segregasyon tablosundaki (7.5.2.1) gibi mutlak bir
"karışık yükleme yasağı" DEĞİLDİR. ADR 7.5.4 metnine göre; 6.1, 6.2 ya da
belirli UN numaralarına (2212, 2315, 2590, 3151, 3152, 3245) sahip 9 etiketli
paketler, gıda maddeleriyle "bitişik" istiflenemez/yüklenemez; ANCAK aralarına
en az paket yüksekliğinde bölme, en az 0,8 m mesafe veya ek
ambalajlama/örtü konularak birlikte taşınabilir. Bu nedenle bu modül "NO"
döndürmez; bunun yerine "tedbir gerektirir" anlamında bir uyarı (caution)
üretir ve nihai karar kullanıcıya/operasyona bırakılır.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import ProductRecord


@dataclass(slots=True)
class FoodSeparationOutcome:
    requires_precaution: bool
    message: str


def check_food_separation(record1: ProductRecord, record2: ProductRecord) -> FoodSeparationOutcome:
    cv1 = record1.cv_codes.upper()
    cv2 = record2.cv_codes.upper()

    if "CV28" not in cv1 and "CV28" not in cv2:
        return FoodSeparationOutcome(requires_precaution=False, message="")

    return FoodSeparationOutcome(
        requires_precaution=True,
        message=(
            "CV28: Bu kalemlerden biri gıda, diğer tüketim maddeleri veya "
            "hayvan yemi ile bitişik istiflenemez/yüklenemez (ADR 7.5.4). "
            "Aralarına en az paket yüksekliğinde bölme, en az 0,8 m mesafe "
            "veya ek ambalaj/örtü uygulanarak birlikte taşınabilir."
        ),
    )
