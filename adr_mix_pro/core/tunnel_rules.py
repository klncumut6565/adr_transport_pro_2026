"""Tünel sınırlama kodu (ADR 8.6 / Tablo A sütun 15) - bilgilendirme amaçlı.

DİKKAT: Tünel kısıtlama kodu, karışık yükleme yasağıyla DOĞRUDAN ilgili
değildir; bir aracın hangi karayolu tünellerinden geçebileceğini belirler.
Burada yalnızca bilgi/rota planlama amacıyla raporlarda gösterilir; karışık
yükleme OK/NO kararını etkilemez.
"""

from __future__ import annotations

from dataclasses import dataclass

# B, C, D, E kodları kısıtlama içerir (kademeli olarak daha sıkı); kodun
# yanına "/D" gibi bir ek varsa en kısıtlayıcı parça esas alınır. "(-)" ya da
# boş değer kısıtlama olmadığı anlamına gelir.
_RESTRICTED_CODES = {"B", "B/D", "B/E", "C", "C/D", "C/E", "D", "D/E", "E"}


@dataclass(slots=True)
class TunnelInfo:
    code: str
    is_restricted: bool
    note: str


def describe_tunnel_code(code: str) -> TunnelInfo:
    normalized = (code or "").strip().upper()

    if normalized in ("", "-", "N/A", "NAN"):
        return TunnelInfo(code=normalized, is_restricted=False, note="")

    if normalized in _RESTRICTED_CODES:
        return TunnelInfo(
            code=normalized,
            is_restricted=True,
            note=f"Tünel kategorisi '{normalized}': bazı tünellerde taşıma kısıtlı olabilir; rota planlamasında dikkate alın.",
        )

    return TunnelInfo(code=normalized, is_restricted=False, note="")
