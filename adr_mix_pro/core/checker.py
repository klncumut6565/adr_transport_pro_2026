"""Ana karışık yükleme denetleyicisi (orkestratör).

``MixChecker``, bir UN numarası listesi alır; bu listedeki her benzersiz
ikiliyi (combination) oluşturur ve her ikili için:

1. Segregasyon (ADR 7.5.2.1 / Sınıf 1 için 7.5.2.2) kontrolü,
2. Gıda ayrımı (CV28 / ADR 7.5.4) kontrolü,
3. Tünel kodu (bilgilendirme amaçlı) kontrolü

yapar ve sonuçları tek bir ``PairCheckResult`` listesi olarak döndürür.
"""

from __future__ import annotations

from itertools import combinations

from ..constants import STATUS_FOOD_CAUTION, STATUS_OK
from ..exceptions import RecordNotFoundError
from ..models import PairCheckResult, ProductRecord
from ..validators import normalize_un
from .database import ProductDatabase
from .food_rules import check_food_separation
from .risk_engine import score_result
from .rule_engine import SegregationRuleEngine
from .segregation_engine import SegregationEngine
from .tunnel_rules import describe_tunnel_code


class MixChecker:
    def __init__(self, database: ProductDatabase, rule_engine: SegregationRuleEngine):
        self.database = database
        self.rule_engine = rule_engine
        self.segregation = SegregationEngine(rule_engine)

    # ------------------------------------------------------------------
    def check_all(self, un_list: list[str]) -> tuple[list[PairCheckResult], list[str]]:
        """Listedeki tüm ikilileri kontrol eder.

        Dönüş: (sonuç_listesi, veritabanında_bulunamayan_un_numaralari)
        """

        normalized = [normalize_un(u) for u in un_list if str(u).strip()]
        unique_uns = list(dict.fromkeys(normalized))  # sırayı koru, tekrarı at

        records: dict[str, ProductRecord] = {}
        missing: list[str] = []

        for un in unique_uns:
            record = self.database.try_get_record(un)
            if record is None:
                missing.append(un)
            else:
                records[un] = record

        results: list[PairCheckResult] = []
        comparable = [u for u in unique_uns if u in records]

        for un1, un2 in combinations(comparable, 2):
            results.append(self._check_pair(records[un1], records[un2]))

        return results, missing

    # ------------------------------------------------------------------
    def _check_pair(self, r1: ProductRecord, r2: ProductRecord) -> PairCheckResult:
        seg_outcome = self.segregation.check_pair(r1, r2)
        food_outcome = check_food_separation(r1, r2)
        tunnel1 = describe_tunnel_code(r1.tunnel_code)
        tunnel2 = describe_tunnel_code(r2.tunnel_code)

        status = seg_outcome.status
        reason = seg_outcome.description
        adr_reference = seg_outcome.adr_reference

        notes: list[str] = []

        if food_outcome.requires_precaution:
            notes.append(food_outcome.message)
            # Segregasyon zaten "OK" ise, durumu "gıda tedbiri gerekir" olarak
            # işaretle; segregasyon zaten "NO"/"UNKNOWN"/"EXPLOSIVE_SPECIAL"
            # ise o daha öncelikli kabul edilip değiştirilmez.
            if status == STATUS_OK:
                status = STATUS_FOOD_CAUTION
                # Ana açıklama genel "izin verilir" metni yerine doğrudan
                # gıda ayrımı gerekliliğini söylesin (arayüzde ilk görünen
                # metin budur; ayrıntı notes içinde zaten mevcut).
                reason = food_outcome.message
                adr_reference = "7.5.4 (CV28)"

        if tunnel1.is_restricted:
            notes.append(f"{r1.un_no}: {tunnel1.note}")
        if tunnel2.is_restricted:
            notes.append(f"{r2.un_no}: {tunnel2.note}")

        risk = score_result(
            status,
            has_food_caution=food_outcome.requires_precaution,
            has_tunnel_restriction=tunnel1.is_restricted or tunnel2.is_restricted,
        )

        return PairCheckResult(
            un1=r1.un_no,
            un2=r2.un_no,
            name1=r1.display_name,
            name2=r2.display_name,
            labels1=r1.labels,
            labels2=r2.labels,
            status=status,
            adr_reference=adr_reference,
            reason=reason,
            risk_score=risk,
            matched_label1=seg_outcome.matched_label1,
            matched_label2=seg_outcome.matched_label2,
            notes=notes,
        )
