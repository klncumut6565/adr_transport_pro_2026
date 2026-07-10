"""Merkezi loglama yapılandırması.

Konsola ve (varsa) kullanıcı dizinindeki app.log dosyasına yazar. Dosyaya
yazma izni yoksa (örn. salt-okunur ortam) sessizce sadece konsol loglamasına
düşer; bu yüzden uygulama log dizini oluşturulamadığında çökmemelidir.
"""

from __future__ import annotations

import logging
import sys

from .config import LOG_FILE, ensure_user_data_dir

_CONFIGURED = False


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    global _CONFIGURED

    logger = logging.getLogger("adr_mix_pro")

    if _CONFIGURED:
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    try:
        ensure_user_data_dir()
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        logger.warning(
            "Log dosyasına yazılamıyor (%s). Sadece konsola loglanacak.",
            LOG_FILE,
        )

    _CONFIGURED = True
    return logger


def get_logger() -> logging.Logger:
    return setup_logging()
