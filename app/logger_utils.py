import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path
from .common import get_app_directory


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


class _ErrorFormatter(logging.Formatter):
    """Ensure every error-level record includes traceback or stack trace."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        parts = [base]

        if record.exc_info:
            try:
                parts.append(self.formatException(record.exc_info))
            except Exception:
                # Formatting errors must not break logging
                pass
        elif record.stack_info:
            try:
                parts.append(self.formatStack(record.stack_info))
            except Exception:
                pass

        return "\n".join(part for part in parts if part)


class _ErrorFileHandler(RotatingFileHandler):
    """Dedicated handler for errors that always persists tracebacks."""

    def emit(self, record: logging.LogRecord):
        if record.levelno < logging.ERROR:
            return

        error_record = logging.makeLogRecord(record.__dict__.copy())

        if error_record.exc_info in (None, (None, None, None)):
            current_exc = sys.exc_info()
            if current_exc != (None, None, None):
                error_record.exc_info = current_exc

        if error_record.exc_info in (None, (None, None, None)):
            error_record.stack_info = "".join(traceback.format_stack())

        super().emit(error_record)


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

    app_dir = app_dir or get_app_directory()
    app_dir.mkdir(exist_ok=True)

    log_file = app_dir / "app_blocker.log"
    error_log_file = app_dir / "app_blocker_errors.log"

    file_handler = RotatingFileHandler(
        log_file, maxBytes=512 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    logger.addHandler(file_handler)

    error_handler = _ErrorFileHandler(
        error_log_file, maxBytes=512 * 1024, backupCount=3, encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(
        _ErrorFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    logger.addHandler(error_handler)

    if event_log_enabled and os.name == "nt":
        event_handler = _EventLogHandler("AppBlocker")
        event_handler.setFormatter(
            logging.Formatter("%(levelname)s | %(name)s | %(message)s")
        )
        logger.addHandler(event_handler)

    logger.propagate = False
    return logger
