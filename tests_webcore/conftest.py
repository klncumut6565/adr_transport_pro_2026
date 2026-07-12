"""Ortak test fikstürleri.

main.py ve mix_integration.py iptal edildiği için (tüm karışık yükleme
entegrasyonu artık adr_transport_pro_2026.py içinde), bu fixture dosyası
adr_mix_pro çekirdek motorunu (SegregationRuleEngine, MixChecker) test etmek
için KENDİ İÇİNDE basit, bağımsız bir ProductDatabase sağlar — herhangi bir
adaptör dosyasına bağımlı değildir.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

RULE_FILE = ROOT / "resources" / "data" / "segregation_rules.csv"

from adr_mix_pro.core.rule_engine import SegregationRuleEngine  # noqa: E402
from adr_mix_pro.core.checker import MixChecker  # noqa: E402
from adr_mix_pro.models import ProductRecord  # noqa: E402


def make_record(un, name="TEST", cls="3", labels=None, code="", cv=""):
    return ProductRecord(
        un_no=un, name=name, hazard_class=cls,
        labels=labels if labels is not None else [cls],
        classification_code=code, cv_codes=cv,
    )


class SimpleProductDatabase:
    """adr_mix_pro'nun ProductDatabase arayüzünü (try_get_record/all_records/
    search) karşılayan, herhangi bir dış dosyaya bağımlı olmayan basit bellek
    içi veritabanı. Yalnızca çekirdek motor testleri için kullanılır."""

    def __init__(self):
        self._records_by_un: dict[str, ProductRecord] = {}

    def try_get_record(self, un):
        from adr_mix_pro.validators import normalize_un
        return self._records_by_un.get(normalize_un(un))

    def all_records(self):
        return list(self._records_by_un.values())

    def search(self, query, limit=200):
        q = str(query).strip().lower()
        if not q:
            return []
        return [r for r in self._records_by_un.values()
                if q in r.un_no.lower() or q in r.name.lower()][:limit]


@pytest.fixture(scope="session")
def rule_engine():
    return SegregationRuleEngine(RULE_FILE)


@pytest.fixture()
def db():
    """Zorlayıcı sentetik kayıtlarla doldurulmuş basit ürün veritabanı."""
    d = SimpleProductDatabase()
    for r in [
        make_record("0336", "HAVAİ FİŞEK 1.4G", "1", ["1.4G"], "1.4G"),
        make_record("0335", "HAVAİ FİŞEK 1.3G", "1", ["1.3G"], "1.3G"),
        make_record("0012", "FİŞEK 1.4S", "1", ["1.4S"], "1.4S"),
        make_record("0081", "PATLAYICI 1.1D", "1", ["1.1D"], "1.1D"),
        make_record("0209", "TNT 1.1D", "1", ["1.1D"], "1.1D"),
        make_record("2814", "BULAŞICI MADDE", "6.2", ["6.2"], cv="CV13 CV28"),
        make_record("2915", "RADYOAKTİF 7A", "7", ["7A"]),
        make_record("3332", "RADYOAKTİF 7B", "7", ["7B"]),
        make_record("9999", "ETİKETSİZ", "", []),
        # Yaygın basit maddeler (çeşitli testlerde referans alınır)
        make_record("1203", "BENZİN", "3", ["3"]),
        make_record("1830", "SÜLFÜRİK ASİT", "8", ["8"]),
        make_record("1090", "ASETON", "3", ["3"]),
        make_record("1170", "ETANOL", "3", ["3"]),
        make_record("3105", "ORGANİK PEROKSİT", "5.2", ["5.2"]),
    ]:
        d._records_by_un[r.un_no] = r
    return d


@pytest.fixture()
def checker(db, rule_engine):
    return MixChecker(db, rule_engine)
