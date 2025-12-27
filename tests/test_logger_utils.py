import tempfile
import unittest
from pathlib import Path

from logger_utils import get_logger, parse_log_line


class TestLoggerUtils(unittest.TestCase):
    def test_parse_valid_line(self):
        line = "2025-12-23 12:00:00 | INFO | app_blocker.monitor | Monitor start"
        parsed = parse_log_line(line)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["timestamp"], "2025-12-23 12:00:00")
        self.assertEqual(parsed["level"], "INFO")
        self.assertEqual(parsed["name"], "app_blocker.monitor")
        self.assertEqual(parsed["message"], "Monitor start")
        self.assertEqual(parsed["raw"], line)

    def test_parse_invalid_line(self):
        self.assertIsNone(parse_log_line(""))
        self.assertIsNone(parse_log_line("just some text"))

    def test_error_log_contains_stack_when_no_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app_dir = Path(tmpdir)
            logger = get_logger(
                "test_error_log_contains_stack_when_no_exception",
                app_dir=app_dir,
                event_log_enabled=False,
            )
            logger.error("Problem encountered")

            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)

            error_log = (app_dir / "app_blocker_errors.log").read_text(encoding="utf-8")

            self.assertIn("Problem encountered", error_log)
            self.assertIn("test_error_log_contains_stack_when_no_exception", error_log)

    def test_error_log_records_traceback_from_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            app_dir = Path(tmpdir)
            logger = get_logger(
                "test_error_log_records_traceback_from_exception",
                app_dir=app_dir,
                event_log_enabled=False,
            )
            try:
                raise ValueError("boom")
            except ValueError:
                logger.exception("Encountered exception")

            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)

            error_log = (app_dir / "app_blocker_errors.log").read_text(encoding="utf-8")

            self.assertIn("Encountered exception", error_log)
            self.assertIn("ValueError", error_log)


if __name__ == "__main__":
    unittest.main()
