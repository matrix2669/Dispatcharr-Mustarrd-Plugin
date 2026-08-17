import importlib.util
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path


class FakeCrontab:
    def __init__(self, minute='*', hour='*', day_of_month='*', month_of_year='*', day_of_week='*'):
        self.minute = self._expand(minute, 0, 59)
        self.hour = self._expand(hour, 0, 23)
        self.day_of_month = self._expand(day_of_month, 1, 31)
        self.month_of_year = self._expand(month_of_year, 1, 12)
        self.day_of_week = self._expand(day_of_week, 0, 6)

    @staticmethod
    def _expand(expr, low, high):
        expr = str(expr)
        values = set()
        for part in expr.split(','):
            if part == '*':
                values.update(range(low, high + 1))
            elif part.startswith('*/'):
                values.update(range(low, high + 1, int(part[2:])))
            elif '-' in part:
                start, end = [int(v) for v in part.split('-', 1)]
                values.update(range(start, end + 1))
            else:
                values.add(int(part))
        return values


celery_mod = types.ModuleType('celery')
schedules_mod = types.ModuleType('celery.schedules')
schedules_mod.crontab = FakeCrontab
sys.modules.setdefault('celery', celery_mod)
sys.modules['celery.schedules'] = schedules_mod

MODULE_PATH = Path(__file__).resolve().parents[1] / 'mustarrd-dvr-handoff' / 'scheduler.py'
spec = importlib.util.spec_from_file_location('mustarrd_scheduler_test', MODULE_PATH)
SCHEDULER = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(SCHEDULER)


class SchedulerCronTests(unittest.TestCase):
    def test_every_five_minutes_matches_only_expected_minutes(self):
        self.assertTrue(SCHEDULER.cron_matches('*/5 * * * *', datetime(2026, 8, 17, 19, 40, tzinfo=timezone.utc)))
        self.assertFalse(SCHEDULER.cron_matches('*/5 * * * *', datetime(2026, 8, 17, 19, 42, tzinfo=timezone.utc)))

    def test_specific_weekday_uses_sunday_zero(self):
        self.assertTrue(SCHEDULER.cron_matches('0 12 * * 0', datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)))
        self.assertFalse(SCHEDULER.cron_matches('0 12 * * 0', datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)))

    def test_invalid_field_count_is_rejected(self):
        with self.assertRaises(ValueError):
            SCHEDULER._parse_cron('*/5 * * *')


class SchedulerStateTests(unittest.TestCase):
    def test_state_round_trip_is_persistent_and_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'state.json')
            old = os.environ.get('MUSTARRD_DVR_SCHEDULER_STATE')
            os.environ['MUSTARRD_DVR_SCHEDULER_STATE'] = path
            try:
                written = SCHEDULER._write_state(enabled=True, cron_expr='*/5 * * * *')
                loaded = SCHEDULER._read_state()
            finally:
                if old is None:
                    os.environ.pop('MUSTARRD_DVR_SCHEDULER_STATE', None)
                else:
                    os.environ['MUSTARRD_DVR_SCHEDULER_STATE'] = old

            self.assertTrue(written['enabled'])
            self.assertEqual(loaded['cron'], '*/5 * * * *')
            self.assertEqual(loaded['version'], 1)


if __name__ == '__main__':
    unittest.main()
