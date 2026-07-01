import logging
import os
from pathlib import Path

log_level = os.getenv("LOG_LEVEL", "INFO").upper()

log_dir = Path(
    os.getenv("LOG_DIR", str(Path(__file__).resolve().parents[3] / "logs"))
)
log_dir.mkdir(parents=True, exist_ok=True)


logger = logging.getLogger(__name__)
logger.setLevel(log_level)

if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)

    formatter = logging.Formatter(
        "%(asctime)s - %(filename)s:%(funcName)s:%(lineno)d - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    try:
        file_handler = logging.FileHandler(log_dir / "app.log")
    except OSError:
        logger.warning("File logging disabled because %s is not writable", log_dir)
    else:
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
