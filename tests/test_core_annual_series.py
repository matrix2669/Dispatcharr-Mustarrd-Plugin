import importlib.util
import sys
import types
import unittest
from pathlib import Path


if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")
    requests_stub.RequestException = RuntimeError
    requests_stub.Session = object
    sys.modules["requests"] = requests_stub


PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "mustarrd-dvr-handoff"
PACKAGE_NAME = "mustarrd_dvr_handoff_core_test"
PACKAGE = types.ModuleType(PACKAGE_NAME)
PACKAGE.__path__ = [str(PLUGIN_ROOT)]
sys.modules[PACKAGE_NAME] = PACKAGE


def _load_module(name):
    module_name = f"{PACKAGE_NAME}.{name}"
    spec = importlib.util.spec_from_file_location(
        module_name,
        PLUGIN_ROOT / f"{name}.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_load_module("annual_series")
CORE = _load_module("core")


class FakeClient:
    def __init__(self, entries=None, error=None):
        self.entries = entries or []
        self.error = error
        self.calls = []

    def get_json(self, path, params=None):
        self.calls.append((path, params))
        if self.error:
            raise self.error
        return self.entries


class CoreAnnualSeriesIntegrationTests(unittest.TestCase):
    def test_tmdb_tag_uses_dash_separator(self):
        self.assertEqual(
            CORE._tmdb_tag("series/304527"),
            "{tmdb-304527} [tmdbid-304527]",
        )

    def test_restore_fetches_fresh_epg_and_normalizes_schedule_payload(self):
        program = {
            "id": 8436484,
            "title": "First Things First",
            "start_time": "2026-08-14T19:00:00+00:00",
            "start_timestamp": 1786734000,
            "stop_timestamp": 1786741200,
            "season_number": 0,
            "episode_number": 158,
            "episode_onscreen": "S00E158",
        }
        client = FakeClient(entries=[{
            "id": "8436484",
            "episode_onscreen": "S00E158",
            "episode_xmltv_ns": "-1.157.",
        }])

        restored = CORE._restore_raw_episode_metadata(client, 1, "3310", program)

        self.assertEqual(restored["season_number"], 2026)
        self.assertEqual(restored["episode_xmltv_ns"], "-1.157.")
        self.assertEqual(
            client.calls,
            [(
                "/api/accounts/1/channels/3310/epg",
                {"days_back": 7, "fresh": "true"},
            )],
        )

    def test_lookup_failure_preserves_explicit_special(self):
        program = {
            "id": 10,
            "start_time": "2026-12-20T20:00:00+00:00",
            "season_number": 0,
            "episode_number": 3,
            "episode_onscreen": "S00E03",
        }
        client = FakeClient(error=CORE.MustarrdError("temporarily unavailable"))

        restored = CORE._restore_raw_episode_metadata(client, 1, "3310", program)

        self.assertIs(restored, program)
        self.assertEqual(restored["season_number"], 0)


if __name__ == "__main__":
    unittest.main()
