import unittest
from datetime import datetime, timezone, timedelta

from time_zone_tabulator import TimeZoneTabulator, ZoneMatch


class TestZoneMatch(unittest.TestCase):
    def test_is_frozen_and_fields(self):
        m = ZoneMatch(name="UTC", utc_offset=0, dst_active=False)
        self.assertEqual(m.name, "UTC")
        self.assertEqual(m.utc_offset, 0)
        self.assertFalse(m.dst_active)
        with self.assertRaises(Exception):
            m.name = "x"  # type: ignore[misc]


class TestFind(unittest.TestCase):
    def setUp(self):
        # A northern-hemisphere summer instant. Several northern zones are
        # on DST at this point, which lets us exercise both branches.
        self.summer = datetime(2024, 7, 15, 12, 0, 0)
        self.t = TimeZoneTabulator(now=self.summer)

    def test_utc_zero_no_dst_includes_utc(self):
        results = self.t.find(0, False)
        names = [m.name for m in results]
        self.assertIn("UTC", names)
        for m in results:
            self.assertEqual(m.utc_offset, 0)
            self.assertFalse(m.dst_active)

    def test_utc_zero_with_dst_excludes_utc(self):
        results = self.t.find(0, True)
        for m in results:
            self.assertEqual(m.utc_offset, 0)
            self.assertTrue(m.dst_active)
        self.assertNotIn("UTC", [m.name for m in results])

    def test_new_york_summer_is_minus_four_with_dst(self):
        results = self.t.find(-240, True)
        names = [m.name for m in results]
        self.assertIn("America/New_York", names)

    def test_new_york_summer_not_in_standard_offset_bucket(self):
        # America/New_York is UTC-4 during DST, not UTC-5.
        results = self.t.find(-300, True)
        self.assertNotIn("America/New_York", [m.name for m in results])

    def test_kolkata_half_hour_offset(self):
        # Asia/Kolkata is UTC+5:30 year-round, no DST.
        results = self.t.find(330, False)
        names = [m.name for m in results]
        self.assertIn("Asia/Kolkata", names)

    def test_kolkata_not_in_dst_bucket(self):
        results = self.t.find(330, True)
        self.assertNotIn("Asia/Kolkata", [m.name for m in results])

    def test_results_sorted_by_name(self):
        results = self.t.find(0, False)
        names = [m.name for m in results]
        self.assertEqual(names, sorted(names))

    def test_results_are_zone_match_instances(self):
        results = self.t.find(0, False)
        self.assertTrue(len(results) > 0)
        for m in results:
            self.assertIsInstance(m, ZoneMatch)

    def test_no_duplicates(self):
        results = self.t.find(0, False)
        names = [m.name for m in results]
        self.assertEqual(len(names), len(set(names)))

    def test_no_match_returns_empty_list(self):
        # No IANA zone sits at UTC+16:30.
        results = self.t.find(990, False)
        self.assertEqual(results, [])

    def test_negative_offset_with_dst(self):
        # At the summer instant, America/Los_Angeles is UTC-7 with DST.
        results = self.t.find(-420, True)
        names = [m.name for m in results]
        self.assertIn("America/Los_Angeles", names)

    def test_winter_instant_changes_dst_for_northern_zones(self):
        winter = datetime(2024, 1, 15, 12, 0, 0)
        t_winter = TimeZoneTabulator(now=winter)
        # America/New_York in January: UTC-5, no DST.
        results = t_winter.find(-300, False)
        names = [m.name for m in results]
        self.assertIn("America/New_York", names)
        # And it should NOT appear in the DST bucket at -5.
        results_dst = t_winter.find(-300, True)
        self.assertNotIn("America/New_York", [m.name for m in results_dst])

    def test_southern_hemisphere_dst_in_january(self):
        # Australia/Sydney observes DST during the southern summer (January):
        # UTC+11 with DST active.
        summer = datetime(2024, 1, 15, 12, 0, 0)
        t = TimeZoneTabulator(now=summer)
        results = t.find(660, True)
        names = [m.name for m in results]
        self.assertIn("Australia/Sydney", names)

    def test_default_constructor_uses_some_instant(self):
        # We do not assert what the instant is; we only assert the call
        # succeeds and returns a list of ZoneMatch. This avoids any
        # dependence on wall-clock values.
        t = TimeZoneTabulator()
        results = t.find(0, False)
        self.assertIsInstance(results, list)
        for m in results:
            self.assertIsInstance(m, ZoneMatch)


if __name__ == "__main__":
    unittest.main()
