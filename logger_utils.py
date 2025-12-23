import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _get_app_directory():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


class _EventLogHandler(logging.Handler):
    def __init__(self, source_name: str):
        super().__init__()
        self.source_name = source_name
        try:
            import win32evtlogutil  # type: ignore
            import win32con  # type: ignore

            self._win32evtlogutil = win32evtlogutil
            self._event_types = {
                logging.DEBUG: win32con.EVENTLOG_INFORMATION_TYPE,
                logging.INFO: win32con.EVENTLOG_INFORMATION_TYPE,
                logging.WARNING: win32con.EVENTLOG_WARNING_TYPE,
                logging.ERROR: win32con.EVENTLOG_ERROR_TYPE,
                logging.CRITICAL: win32con.EVENTLOG_ERROR_TYPE,
            }
            self._available = True
        except Exception:
            self._available = False

    def emit(self, record):
        if not self._available:
            return
        try:
            msg = self.format(record)
            event_type = self._event_types.get(record.levelno)
            if event_type is None:
                return
            self._win32evtlogutil.ReportEvent(
                self.source_name,
                eventID=1,
                eventCategory=0,
                eventType=event_type,
                strings=[msg],
            )
        except Exception:
            # We do not want logging failures to break the app
            pass


def parse_log_line(line: str) -> dict | None:
    """Parse a single log line produced by get_logger handlers."""
    if not line:
        return None

    parts = line.strip().split(" | ", 3)
    if len(parts) != 4:
        return None

    timestamp, level, name, message = parts
    return {
        "timestamp": timestamp,
        "level": level,
        "name": name,
        "message": message,
        "raw": line.strip(),
    }


def get_logger(
    name: str = "app_blocker",
    app_dir: Path | None = None,
    event_log_enabled: bool = False,
):
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    app_dir = app_dir or _get_app_directory()
    app_dir.mkdir(exist_ok=True)
    log_file = app_dir / "app_blocker.log"

    file_handler = RotatingFileHandler(
        log_file, maxBytes=512 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    logger.addHandler(file_handler)

    if event_log_enabled and os.name == "nt":
        event_handler = _EventLogHandler("AppBlocker")
        event_handler.setFormatter(
            logging.Formatter("%(levelname)s | %(name)s | %(message)s")
        )
        logger.addHandler(event_handler)

    logger.propagate = False
    return logger
