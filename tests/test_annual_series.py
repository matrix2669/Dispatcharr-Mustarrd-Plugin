import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "mustarrd-dvr-handoff"
    / "annual_series.py"
)
SPEC = importlib.util.spec_from_file_location("mustarrd_dvr_annual_series", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

normalize_annual_series_season = MODULE.normalize_annual_series_season


class AnnualSeriesSeasonTests(unittest.TestCase):
    def test_first_things_first_uses_airing_year(self):
        program = {
            "title": "First Things First",
            "start_time": "2026-08-14T19:00:00+00:00",
            "season_number": 0,
            "episode_number": 158,
            "episode_onscreen": None,
            "categories": ["Sports"],
            "tmdb_id": "288982",
        }

        normalized = normalize_annual_series_season(program)

        self.assertEqual(normalized["season_number"], 2026)
        self.assertEqual(normalized["episode_number"], 158)
        self.assertEqual(program["season_number"], 0)

    def test_first_things_first_ot_uses_airing_year(self):
        program = {
            "title": "First Things First: OT",
            "start_time": "2026-08-14T21:00:00+00:00",
            "season_number": 0,
            "episode_number": 145,
            "episode_onscreen": None,
            "categories": ["Sports"],
            "tmdb_id": "304527",
        }

        normalized = normalize_annual_series_season(program)

        self.assertEqual(normalized["season_number"], 2026)
        self.assertEqual(normalized["episode_number"], 145)

    def test_explicit_s00_special_is_preserved(self):
        program = {
            "title": "Example Series",
            "start_time": "2026-12-20T20:00:00+00:00",
            "season_number": 0,
            "episode_number": 3,
            "episode_onscreen": "S00E03",
            "categories": ["Series"],
        }

        normalized = normalize_annual_series_season(program)

        self.assertIs(normalized, program)
        self.assertEqual(normalized["season_number"], 0)

    def test_nonzero_season_is_unchanged(self):
        program = {
            "title": "Example Series",
            "start_time": "2026-08-14T20:00:00+00:00",
            "season_number": 4,
            "episode_number": 12,
            "categories": ["Series"],
        }

        normalized = normalize_annual_series_season(program)

        self.assertIs(normalized, program)
        self.assertEqual(normalized["season_number"], 4)

    def test_timestamp_fallback_supplies_year(self):
        program = {
            "title": "Daily Example",
            "start_timestamp": 1786723200,
            "season_number": 0,
            "episode_number": 42,
            "categories": ["Talk"],
        }

        normalized = normalize_annual_series_season(program)

        self.assertEqual(normalized["season_number"], 2026)


if __name__ == "__main__":
    unittest.main()
