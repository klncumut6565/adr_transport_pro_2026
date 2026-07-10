"""Ürün veritabanı katmanı.

Excel (.xlsx/.xls) veya CSV biçimindeki "ADR A Tablosu" tarzı veri
dosyalarını okur. Kurumdan kuruma değişebilen sütun başlıklarını
``config.COLUMN_ALIASES`` üzerinden eşler; böylece kullanıcı kendi Excel
dosyasını -sütun adlarını programa göre değiştirmeden- doğrudan
kullanabilir.

GERÇEK ADR A TABLOSU DOSYALARI İÇİN ÖZEL NOTLAR (v2.2):
Resmi "ADR A Tablosu" dışa aktarımları genellikle şu üç özelliği taşır,
ve her biri burada özel olarak ele alınmıştır:
  1) Ayraç (delimiter) çoğunlukla VİRGÜL değil NOKTALI VİRGÜL (;) olur.
     pandas'ın otomatik ayraç tespiti (sep=None + engine="python"),
     hücre içi çok satırlı (gömülü \\n içeren) metinler yüzünden bu
     dosyalarda GÜVENİLMEZ ve hatayla sonuçlanabilir; bu yüzden burada
     birkaç aday ayraç açıkça denenir (bkz. ``_read_csv_robust``).
  2) Sütun başlıkları çoğunlukla hücre içinde satır kırılması içerir
     (örn. "UN \\nNo."). Bu, ``\\n`` basitçe boşlukla değiştirildiğinde
     ÇİFT boşluğa yol açar ve alias eşlemesini bozar; bu yüzden başlık
     normalizasyonu artık TÜM boşluk dizilerini (yeni satır, tab, çoklu
     boşluk) tek bir boşluğa indirger (bkz. ``_normalize_header``).
  3) Gerçek dosyanın ilk veri satırından önce, sütun alt başlıklarını,
     ilgili ADR madde numaralarını ve sütun indekslerini ("1;2;(3a);...")
     içeren 2-3 "sahte satır" bulunur. Bu satırlar pandas tarafından veri
     satırı gibi okunur; sütun-indeksi satırı (örn. "İsim ve açıklama"
     sütununda sadece "2" gibi bir değer) tespit edilip atlanır (bkz.
     ``_looks_like_header_artifact``).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from ..config import COLUMN_ALIASES
from ..exceptions import ColumnNotFoundError, DatabaseError, RecordNotFoundError
from ..models import ProductRecord
from ..utils import normalize_label, split_labels
from ..validators import normalize_un

# Gerçek ADR A Tablosu dışa aktarımlarında en sık görülen ayraçlar, en
# olası sıraya göre. "," son sıradadır çünkü Türkçe sayı biçimlerinde
# (örn. "2,2") ondalık ayracı olarak da kullanılır ve yanlış pozitiflere
# yol açabilir.
_CSV_SEPARATOR_CANDIDATES = (";", "\t", ",")

# "İsim ve açıklama" sütununda sadece "2", "(3a)", "(7b)" gibi saf bir
# sütun-indeksi değeri varsa, bu satır gerçek bir ürün değil, çok satırlı
# başlık bloğundan kalan bir "sahte satır"dır.
_HEADER_ARTIFACT_PATTERN = re.compile(r"^\(?\d+[a-zA-Z]?\)?$")


def _normalize_header(text: str) -> str:
    text = str(text)
    # Hücre içi satır kırılması + olası çoklu boşluk -> TEK boşluk.
    text = re.sub(r"\s+", " ", text)
    text = text.strip().lower()
    text = text.replace("ı", "i").replace("İ", "i")
    return text


def _looks_like_header_artifact(name: str) -> bool:
    return bool(_HEADER_ARTIFACT_PATTERN.match(name.strip()))


def _read_csv_robust(path: Path) -> pd.DataFrame:
    """CSV dosyasını, ayraç (delimiter) tahminini güvenilir biçimde yaparak okur.

    ``sep=None`` (otomatik tespit, ``engine="python"``), gömülü çok
    satırlı hücreler içeren dosyalarda çökebildiği için burada birkaç
    aday ayraç (;, TAB, ,) hızlı ve sağlam "c" motoruyla denenir; en çok
    sütun üreten sonuç kazanır. Hiçbiri en az 2 sütun üretemezse, son
    çare olarak eski otomatik tespit yöntemine düşülür.
    """

    best_df: pd.DataFrame | None = None
    best_column_count = 1

    for sep in _CSV_SEPARATOR_CANDIDATES:
        try:
            df = pd.read_csv(
                path, dtype=str, encoding="utf-8-sig", sep=sep, engine="c"
            )
        except Exception:
            continue

        if df.shape[1] > best_column_count:
            best_column_count = df.shape[1]
            best_df = df

    if best_df is not None:
        return best_df

    # Son çare: eski davranış (yavaş ama daha esnek sezgisel ayraç tespiti).
    return pd.read_csv(
        path, dtype=str, encoding="utf-8-sig", sep=None, engine="python"
    )


class ProductDatabase:
    """Bellekte tutulan, sorgulanabilir ürün/madde veritabanı."""

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)
        self.dataframe: pd.DataFrame | None = None
        self._column_map: dict[str, str] = {}
        self._records_by_un: dict[str, ProductRecord] = {}
        self._skipped_header_rows = 0
        self._load()

    # ------------------------------------------------------------------
    # Yükleme
    # ------------------------------------------------------------------
    def _load(self) -> None:
        suffix = self.file_path.suffix.lower()

        try:
            if suffix in (".xlsx", ".xls"):
                df = pd.read_excel(self.file_path, dtype=str)
            elif suffix == ".csv":
                df = _read_csv_robust(self.file_path)
            else:
                raise DatabaseError(
                    f"Desteklenmeyen dosya biçimi: '{suffix}'. "
                    "Lütfen .xlsx, .xls veya .csv kullanın."
                )
        except DatabaseError:
            raise
        except Exception as exc:  # pandas/openpyxl tarafından üretilebilecek hatalar
            raise DatabaseError(
                f"'{self.file_path.name}' okunamadı: {exc}"
            ) from exc

        if df.shape[1] < 2:
            raise DatabaseError(
                f"'{self.file_path.name}' okunamadı: dosyada sadece 1 sütun "
                "tespit edildi. Ayraç (virgül/noktalı virgül) tanınamamış "
                "olabilir; dosyayı UTF-8 CSV veya .xlsx olarak yeniden "
                "kaydetmeyi deneyin."
            )

        df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.columns]
        self.dataframe = df
        self._build_column_map()
        self._build_records()

    def _build_column_map(self) -> None:
        assert self.dataframe is not None
        normalized_columns = {
            _normalize_header(col): col for col in self.dataframe.columns
        }

        for field_name, aliases in COLUMN_ALIASES.items():
            for alias in aliases:
                key = _normalize_header(alias)
                if key in normalized_columns:
                    self._column_map[field_name] = normalized_columns[key]
                    break

        if "UN_NO" not in self._column_map:
            available = ", ".join(f"'{c}'" for c in self.dataframe.columns[:8])
            raise ColumnNotFoundError(
                "Veri dosyasında bir UN numarası sütunu bulunamadı. "
                "Beklenen başlıklardan biri: 'UN No', 'UN No.', 'UN Numarası'... "
                f"Dosyada bulunan ilk sütunlar: {available}"
            )

    def _get(self, row: pd.Series, field_name: str) -> str:
        column = self._column_map.get(field_name)
        if column is None or column not in row:
            return ""
        value = row[column]
        if pd.isna(value):
            return ""
        # Kaynak dosyada hücre içi satır kırılmaları (PDF/Word'den dışa
        # aktarım artığı) sık görülür; bunlar anlamlı değildir ve arayüzde
        # metni bölüp görünümü bozar. Tek boşluğa indirilir.
        return re.sub(r"\s+", " ", str(value)).strip()

    def _build_records(self) -> None:
        assert self.dataframe is not None
        un_column = self._column_map["UN_NO"]

        for _, row in self.dataframe.iterrows():
            raw_un = row.get(un_column, "")
            if pd.isna(raw_un) or str(raw_un).strip() == "":
                continue

            name = self._get(row, "NAME")
            if _looks_like_header_artifact(name):
                # Çok satırlı başlık bloğundan kalan bir "sütun indeksi"
                # satırı (örn. isim alanında sadece "2" ya da "(3a)");
                # gerçek bir ürün değildir, atlanır.
                self._skipped_header_rows += 1
                continue

            un_no = normalize_un(raw_un)

            record = ProductRecord(
                un_no=un_no,
                name=name,
                hazard_class=normalize_label(self._get(row, "CLASS")),
                classification_code=normalize_label(self._get(row, "CLASSIFICATION_CODE")),
                packing_group=self._get(row, "PACKING_GROUP"),
                labels=split_labels(self._get(row, "LABELS")),
                special_provisions=self._get(row, "SPECIAL_PROVISIONS"),
                transport_category=self._get(row, "TRANSPORT_CATEGORY"),
                cv_codes=self._get(row, "CV_CODES"),
                tunnel_code=self._get(row, "TUNNEL_CODE"),
                danger_number=self._get(row, "DANGER_NUMBER"),
                raw=row.to_dict(),
            )

            # Aynı UN numarası birden çok satırda olabilir (farklı ambalaj
            # grubu/sınıflandırma kodu). İlk karşılaşılan kayıt esas alınır;
            # bu davranış ileride "tüm varyantları göster" şeklinde
            # genişletilebilir.
            self._records_by_un.setdefault(un_no, record)

    # ------------------------------------------------------------------
    # Sorgular
    # ------------------------------------------------------------------
    def total_records(self) -> int:
        return len(self._records_by_un)

    def has_record(self, un_no: str) -> bool:
        return normalize_un(un_no) in self._records_by_un

    def get_record(self, un_no: str) -> ProductRecord:
        key = normalize_un(un_no)
        record = self._records_by_un.get(key)
        if record is None:
            raise RecordNotFoundError(f"UN {un_no} veritabanında bulunamadı.")
        return record

    def try_get_record(self, un_no: str) -> ProductRecord | None:
        return self._records_by_un.get(normalize_un(un_no))

    def all_records(self) -> list[ProductRecord]:
        return list(self._records_by_un.values())

    def search(self, query: str, limit: int = 200) -> list[ProductRecord]:
        """UN numarası veya isim içinde basit metin araması yapar."""

        query = query.strip().lower()
        records = self.all_records()

        if not query:
            return records[:limit]

        results = [
            r
            for r in records
            if query in r.un_no.lower() or query in r.name.lower()
        ]
        return results[:limit]
