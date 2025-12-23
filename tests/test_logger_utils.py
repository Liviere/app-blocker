import unittest

from logger_utils import parse_log_line


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


if __name__ == "__main__":
    unittest.main()
