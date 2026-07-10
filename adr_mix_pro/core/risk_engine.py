"""Basit, sezgisel (heuristic) risk puanlama.

ÖNEMLİ: Bu puan ADR'de tanımlı resmi bir "risk skoru" DEĞİLDİR; sadece
sonuç tablosunu/sıralamasını kullanıcı için daha okunur kılmak amacıyla
üretilen, 0-100 aralığında göreceli bir önceliklendirme değeridir. Hiçbir
uygunluk kararı bu puana dayanmaz; karar her zaman ``status`` alanına göre
verilir.
"""

from __future__ import annotations

from ..constants import (
    STATUS_EXPLOSIVE_SPECIAL,
    STATUS_FOOD_CAUTION,
    STATUS_FORBIDDEN,
    STATUS_OK,
    STATUS_UNKNOWN,
)

_BASE_SCORE = {
    STATUS_FORBIDDEN: 100,
    STATUS_EXPLOSIVE_SPECIAL: 85,
    STATUS_UNKNOWN: 60,
    STATUS_FOOD_CAUTION: 40,
    STATUS_OK: 0,
}


def score_result(status: str, has_food_caution: bool = False, has_tunnel_restriction: bool = False) -> int:
    score = _BASE_SCORE.get(status, 50)

    if status == STATUS_OK and has_food_caution:
        score = max(score, _BASE_SCORE[STATUS_FOOD_CAUTION])

    if has_tunnel_restriction:
        score += 5

    return min(score, 100)
