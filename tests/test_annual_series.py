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
enrich_from_mustarrd_epg = MODULE.enrich_from_mustarrd_epg
needs_raw_xmltv_lookup = MODULE.needs_raw_xmltv_lookup


class AnnualSeriesSeasonTests(unittest.TestCase):
    def test_real_dispatcharr_payload_is_enriched_from_first_things_first_epg(self):
        dispatcharr_program = {
            "id": 8436484,
            "title": "First Things First",
            "start_time": "2026-08-14T19:00:00+00:00",
            "start_timestamp": 1786734000,
            "stop_timestamp": 1786741200,
            "season_number": 0,
            "episode_number": 158,
            "episode_onscreen": "S00E158",
        }
        mustarrd_epg = [{
            "id": "8436484",
            "start_timestamp": 1786734000,
            "stop_timestamp": 1786741200,
            "season_number": 0,
            "episode_number": 158,
            "episode_onscreen": "S00E158",
            "episode_xmltv_ns": "-1.157.",
        }]

        self.assertTrue(needs_raw_xmltv_lookup(dispatcharr_program))
        enriched = enrich_from_mustarrd_epg(dispatcharr_program, mustarrd_epg)
        normalized = normalize_annual_series_season(enriched)

        self.assertEqual(enriched["episode_xmltv_ns"], "-1.157.")
        self.assertEqual(normalized["season_number"], 2026)
        self.assertNotIn("episode_xmltv_ns", dispatcharr_program)

    def test_current_upstream_mustarrd_field_names_are_supported(self):
        dispatcharr_program = {
            "id": 8436484,
            "title": "First Things First",
            "start_time": "2026-08-14T19:00:00+00:00",
            "start_timestamp": 1786734000,
            "stop_timestamp": 1786741200,
            "season_number": 0,
            "episode_number": 158,
            "episode_onscreen": "S00E158",
        }
        upstream_mustarrd_epg = [{
            "id": "8436484",
            "start_timestamp": 1786734000,
            "stop_timestamp": 1786741200,
            "season_number": 0,
            "episode_number": 158,
            "episode_num_onscreen": "S00E158",
            "episode_num_xmltv": "-1.157.",
        }]

        enriched = enrich_from_mustarrd_epg(
            dispatcharr_program,
            upstream_mustarrd_epg,
        )
        normalized = normalize_annual_series_season(enriched)

        self.assertEqual(enriched["episode_xmltv_ns"], "-1.157.")
        self.assertEqual(normalized["season_number"], 2026)

    def test_real_dispatcharr_payload_is_enriched_from_first_things_first_ot_epg(self):
        dispatcharr_program = {
            "id": 8433457,
            "title": "First Things First: OT",
            "start_time": "2026-08-14T21:00:00+00:00",
            "start_timestamp": 1786741200,
            "stop_timestamp": 1786744800,
            "season_number": 0,
            "episode_number": 145,
            "episode_onscreen": "S00E145",
        }
        mustarrd_epg = [{
            "id": "8433457",
            "start_timestamp": 1786741200,
            "stop_timestamp": 1786744800,
            "season_number": 0,
            "episode_number": 145,
            "episode_onscreen": "S00E145",
            "episode_xmltv_ns": "-1.144.",
        }]

        enriched = enrich_from_mustarrd_epg(dispatcharr_program, mustarrd_epg)
        normalized = normalize_annual_series_season(enriched)

        self.assertEqual(normalized["season_number"], 2026)

    def test_epg_entry_for_another_program_does_not_change_special(self):
        special = {
            "id": 10,
            "start_time": "2026-12-20T20:00:00+00:00",
            "start_timestamp": 1797796800,
            "stop_timestamp": 1797800400,
            "season_number": 0,
            "episode_number": 3,
            "episode_onscreen": "S00E03",
        }
        unrelated_epg = [{
            "id": "11",
            "start_timestamp": 1797804000,
            "stop_timestamp": 1797807600,
            "episode_xmltv_ns": "-1.2.",
        }]

        enriched = enrich_from_mustarrd_epg(special, unrelated_epg)
        normalized = normalize_annual_series_season(enriched)

        self.assertIs(enriched, special)
        self.assertIs(normalized, special)
        self.assertEqual(normalized["season_number"], 0)

    def test_first_things_first_uses_airing_year(self):
        program = {
            "title": "First Things First",
            "start_time": "2026-08-14T19:00:00+00:00",
            "season_number": 0,
            "episode_number": 158,
            "episode_onscreen": "S00E158",
            "episode_xmltv_ns": "-1.157.",
            "categories": ["Sports", "Series"],
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
            "episode_onscreen": "S00E145",
            "episode_xmltv_ns": "-1.144.",
            "categories": ["Sports", "Series"],
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

    def test_explicit_s00_with_nonnegative_xmltv_season_is_preserved(self):
        program = {
            "title": "Example Series",
            "start_time": "2026-12-20T20:00:00+00:00",
            "season_number": 0,
            "episode_number": 3,
            "episode_onscreen": "S00E03",
            "episode_xmltv_ns": "0.2.",
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
