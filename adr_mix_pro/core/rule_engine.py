"""ADR 7.5.2.1 etiket bazlı karışık yükleme kural motoru.

Kurallar koddan ayrı, düzenlenebilir bir CSV dosyasından (varsayılan:
``resources/data/segregation_rules.csv``) okunur. Bu, bir TMGD/lojistik
uzmanının Python bilmeden tabloyu güncelleyebilmesini sağlar.

GÜVENLİK İLKESİ:
Tabloda yer almayan bir etiket çifti için motor **"OK" (uygun) DEĞİL**,
``STATUS_UNKNOWN`` döndürür. Önceki dağınık sürümlerin bazılarında
tanımsız kombinasyonlar sessizce "uygun" kabul ediliyordu; bu, bir
uygunluk denetim aracı için kabul edilemez bir varsayımdır ("bilmiyorum"
"güvenlidir" anlamına gelmez). Bilinmeyen kombinasyonlar UI'da ayrıca
vurgulanarak manuel kontrol gerektiği belirtilir.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..constants import STATUS_OK, STATUS_UNKNOWN
from ..exceptions import RuleFileError
from ..models import SegregationVerdict
from ..utils import normalize_label, sorted_pair_key

REQUIRED_COLUMNS = {"LABEL1", "LABEL2", "STATUS", "ADR", "DESCRIPTION"}


class SegregationRuleEngine:
    """``segregation_rules.csv`` dosyasını yükler ve etiket çifti sorgular."""

    def __init__(self, rule_file: str | Path):
        self.rule_file = Path(rule_file)
        self._rules: dict[tuple[str, str], SegregationVerdict] = {}
        self.load()

    def load(self) -> None:
        if not self.rule_file.exists():
            raise RuleFileError(f"Kural dosyası bulunamadı: {self.rule_file}")

        with open(self.rule_file, "r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(
                row for row in fh if not row.lstrip().startswith("#") and row.strip()
            )

            if reader.fieldnames is None or not REQUIRED_COLUMNS.issubset(
                {c.strip().upper() for c in reader.fieldnames}
            ):
                raise RuleFileError(
                    f"Kural dosyasının başlık satırı geçersiz: {self.rule_file}. "
                    f"Beklenen sütunlar: {sorted(REQUIRED_COLUMNS)}"
                )

            for row_number, row in enumerate(reader, start=2):
                try:
                    label1 = normalize_label(row["LABEL1"])
                    label2 = normalize_label(row["LABEL2"])
                    status = str(row["STATUS"]).strip().upper()
                    adr_ref = str(row["ADR"]).strip()
                    description = str(row["DESCRIPTION"]).strip()
                except KeyError as exc:
                    raise RuleFileError(
                        f"{self.rule_file}:{row_number} - eksik sütun: {exc}"
                    ) from exc

                if not label1 or not label2:
                    continue

                verdict = SegregationVerdict(
                    label1=label1,
                    label2=label2,
                    status=status,
                    adr_reference=adr_ref,
                    description=description,
                )

                key = sorted_pair_key(label1, label2)
                self._rules[key] = verdict

    def rule_count(self) -> int:
        return len(self._rules)

    def check(self, label1: str, label2: str) -> SegregationVerdict:
        l1 = normalize_label(label1)
        l2 = normalize_label(label2)
        key = sorted_pair_key(l1, l2)

        verdict = self._rules.get(key)
        if verdict is not None:
            return verdict

        return SegregationVerdict(
            label1=l1,
            label2=l2,
            status=STATUS_UNKNOWN,
            adr_reference="7.5.2.1",
            description=(
                f"'{l1}' ile '{l2}' etiketleri için tanımlı bir kural yok. "
                "ADR Tablo 7.5.2.1 üzerinden manuel doğrulama yapın."
            ),
        )

    def known_labels(self) -> list[str]:
        labels: set[str] = set()
        for l1, l2 in self._rules.keys():
            labels.add(l1)
            labels.add(l2)
        return sorted(labels)
