"""Proje dosyası (.adrproj) okuma/yazma.

Bir ".adrproj" dosyası; o ana kadar eklenmiş UN listesini, en son kontrol
sonuçlarını ve bazı ayarları JSON biçiminde saklar; böylece kullanıcı
yarım kalan bir analizi daha sonra aynı noktadan açabilir.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .. import __version__
from ..exceptions import ProjectFileError
from ..models import PairCheckResult

PROJECT_SCHEMA_VERSION = "2.0"


def _result_to_dict(result: PairCheckResult) -> dict:
    return asdict(result)


def _result_from_dict(data: dict) -> PairCheckResult:
    return PairCheckResult(**data)


def save_project(
    filepath: str | Path,
    un_list: list[str],
    results: list[PairCheckResult],
    database_path: str | None = None,
    rule_file_path: str | None = None,
) -> None:
    payload = {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "app_version": __version__,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "database_path": database_path,
        "rule_file_path": rule_file_path,
        "un_list": un_list,
        "results": [_result_to_dict(r) for r in results],
    }

    try:
        with open(filepath, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
    except OSError as exc:
        raise ProjectFileError(f"Proje dosyası kaydedilemedi: {exc}") from exc


def load_project(filepath: str | Path) -> dict:
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise ProjectFileError(f"Proje dosyası okunamadı: {exc}") from exc

    try:
        results = [_result_from_dict(r) for r in payload.get("results", [])]
    except TypeError as exc:
        raise ProjectFileError(
            f"Proje dosyası beklenmeyen bir biçimde: {exc}"
        ) from exc

    return {
        "un_list": payload.get("un_list", []),
        "results": results,
        "database_path": payload.get("database_path"),
        "rule_file_path": payload.get("rule_file_path"),
        "created_at": payload.get("created_at"),
    }
