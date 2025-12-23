import json
import unittest
import tempfile
from datetime import datetime, timedelta, UTC
from pathlib import Path
from unittest.mock import patch

import main
from gui import AppBlockerGUI


class TestMonitorHeartbeat(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.config_path = self.tmp / "config.json"
        self.log_path = self.tmp / "usage_log.json"
        self.heartbeat_path = self.tmp / "monitor_heartbeat.json"

        config = {
            "apps": {"notepad.exe": 2},
            "check_interval": 1,
            "enabled": True,
            "event_log_enabled": False,
        }
        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=2)
        with open(self.log_path, "w") as f:
            json.dump({}, f)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    @patch("main.psutil.process_iter", return_value=[])
    def test_monitor_writes_heartbeat_and_stops(self, _process_iter):
        iteration = {"count": 0}

        def custom_sleep(duration):
            iteration["count"] += 1
            if iteration["count"] >= 2:
                raise KeyboardInterrupt()

        with patch.object(main, "APP_DIR", self.tmp), patch.object(
            main, "CONFIG_PATH", self.config_path
        ), patch.object(main, "LOG_PATH", self.log_path), patch.object(
            main, "HEARTBEAT_PATH", self.heartbeat_path
        ), patch("time.sleep", side_effect=custom_sleep):
            try:
                main.monitor()
            except (KeyboardInterrupt, SystemExit):
                pass

        self.assertTrue(self.heartbeat_path.exists())
        with open(self.heartbeat_path, "r") as f:
            hb = json.load(f)

        self.assertEqual(hb.get("status"), "stopped")
        self.assertIn("timestamp", hb)
        self.assertIn("pid", hb)


class DummyProcess:
    def __init__(self, alive=True):
        self._alive = alive

    def poll(self):
        return None if self._alive else 1


class TestWatchdogLogic(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_gui_stub(self, heartbeat_ts: datetime):
        stub = object.__new__(AppBlockerGUI)
        stub.config = {
            "watchdog_enabled": True,
            "watchdog_restart": True,
            "watchdog_check_interval": 1,
            "heartbeat_ttl_seconds": 5,
            "check_interval": 1,
        }
        stub.logger = None
        stub.monitoring_process = DummyProcess(alive=True)
        stub.heartbeat_path = self.tmp / "hb.json"
        stub.is_monitoring = True
        stub._watchdog_restart_running = False
        stub._watchdog_grace_deadline = None
        with open(stub.heartbeat_path, "w") as f:
            json.dump({"timestamp": heartbeat_ts.isoformat()}, f)

        stub._terminate_monitoring_process = lambda: setattr(self, "terminated", True)
        stub.start_monitoring = lambda: setattr(self, "restarted", True)
        stub.stop_monitoring = lambda: setattr(self, "stopped", True)
        self.terminated = False
        self.restarted = False
        self.stopped = False
        return stub

    def test_watchdog_restarts_on_stale_heartbeat(self):
        old_ts = datetime.now(UTC) - timedelta(seconds=120)
        gui = self._make_gui_stub(old_ts)

        gui._check_monitor_health()

        self.assertTrue(self.terminated)
        self.assertTrue(self.restarted)
        self.assertFalse(self.stopped)

    def test_watchdog_stops_when_restart_disabled(self):
        old_ts = datetime.now(UTC) - timedelta(seconds=120)
        gui = self._make_gui_stub(old_ts)
        gui.config["watchdog_restart"] = False

        gui._check_monitor_health()

        self.assertFalse(self.terminated)
        self.assertFalse(self.restarted)
        self.assertTrue(self.stopped)

    def test_watchdog_grace_period_skip_restart(self):
        old_ts = datetime.now(UTC) - timedelta(seconds=120)
        gui = self._make_gui_stub(old_ts)
        gui._watchdog_grace_deadline = datetime.now(UTC) + timedelta(seconds=30)

        gui._check_monitor_health()

        self.assertFalse(self.restarted)
        self.assertFalse(self.terminated)
        self.assertFalse(self.stopped)

    def test_is_heartbeat_fresh(self):
        gui = object.__new__(AppBlockerGUI)
        gui.config = {"heartbeat_ttl_seconds": 10, "check_interval": 1}
        gui.heartbeat_path = self.tmp / "hb.json"

        fresh_ts = datetime.now(UTC)
        with open(gui.heartbeat_path, "w") as f:
            json.dump({"timestamp": fresh_ts.isoformat()}, f)
        self.assertTrue(gui._is_heartbeat_fresh())

        old_ts = datetime.now(UTC) - timedelta(seconds=120)
        with open(gui.heartbeat_path, "w") as f:
            json.dump({"timestamp": old_ts.isoformat()}, f)
        self.assertFalse(gui._is_heartbeat_fresh())


if __name__ == "__main__":
    unittest.main()
