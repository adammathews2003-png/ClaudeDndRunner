"""lib/gametime.py arithmetic incl. midnight wrap (plan.md Phase 1 item 6)."""
import unittest

import fixture  # noqa: F401  (puts tools/ on sys.path)
from lib import gametime as gt


class Parse(unittest.TestCase):
    def test_parse_and_fmt(self):
        self.assertEqual(gt.parse("Day 1 19:30"), (1, 1170))
        self.assertEqual(gt.parse('"Day -1 00:05"'), (-1, 5))
        self.assertEqual(gt.fmt(1, 1170), "Day 1 19:30")
        self.assertEqual(gt.fmt((2, 10)), "Day 2 00:10")
        for bad in ("Day 1", "19:30", "Day 1 24:00", "tomorrow"):
            with self.assertRaises(gt.TimeError):
                gt.parse(bad)

    def test_named_times(self):
        self.assertEqual(gt.parse_clock("dawn"), 6 * 60)
        self.assertEqual(gt.parse_clock("pre-dawn"), 4 * 60)
        self.assertEqual(gt.parse_clock("midnight"), 0)
        self.assertEqual(gt.parse_clock("night"), 22 * 60)
        self.assertEqual(gt.parse_clock("07:05"), 425)


class Add(unittest.TestCase):
    def test_plus_crosses_midnight(self):
        t = gt.parse("Day 1 19:40")
        self.assertEqual(gt.fmt(gt.add(t, "+4h30m")), "Day 2 00:10")  # the 06:362 example
        self.assertEqual(gt.fmt(gt.add(t, "+20m")), "Day 1 20:00")
        self.assertEqual(gt.fmt(gt.add(t, "+1d")), "Day 2 19:40")
        self.assertEqual(gt.fmt(gt.add(t, "+2d 5h")), "Day 4 00:40")
        self.assertEqual(gt.fmt(gt.add((1, 0), "+0m")), "Day 1 00:00")

    def test_to_clock_is_next_occurrence(self):
        t = gt.parse("Day 1 19:40")
        self.assertEqual(gt.fmt(gt.add(t, "to 06:00")), "Day 2 06:00")
        self.assertEqual(gt.fmt(gt.add(t, "to dawn")), "Day 2 06:00")
        self.assertEqual(gt.fmt(gt.add(t, "to 21:00")), "Day 1 21:00")
        self.assertEqual(gt.fmt(gt.add(t, "to midnight")), "Day 2 00:00")
        self.assertEqual(gt.fmt(gt.add((1, 360), "to dawn")), "Day 2 06:00")  # same minute → a day

    def test_bad_spec(self):
        for bad in ("+4x", "to soon", "later"):
            with self.assertRaises(gt.TimeError):
                gt.add((1, 0), bad)

    def test_diff_and_fmt_delta(self):
        a, b = gt.parse("Day 2 00:10"), gt.parse("Day 3 04:00")
        self.assertEqual(gt.diff(a, b), 27 * 60 + 50)
        self.assertEqual(gt.fmt_delta(gt.diff(a, b)), "1d 3h50m")  # the 06:365 example
        self.assertEqual(gt.fmt_delta(90), "1h30m")
        self.assertEqual(gt.fmt_delta(0), "0m")
        self.assertEqual(gt.fmt_delta(-30), "-30m")


class Period(unittest.TestCase):
    def test_period_bands(self):
        cases = {"00:30": "midnight", "04:00": "pre-dawn", "06:00": "dawn", "07:59": "dawn",
                 "08:00": "morning", "12:30": "noon", "15:00": "afternoon", "18:30": "dusk",
                 "19:40": "evening", "22:00": "night", "23:59": "night"}
        for clock, want in cases.items():
            self.assertEqual(gt.period((1, gt.parse_clock(clock))), want, clock)


class Between(unittest.TestCase):
    def test_plain_window(self):
        self.assertTrue(gt.between("10:00", "08:00", "12:00"))
        self.assertFalse(gt.between("12:00", "08:00", "12:00"))  # end exclusive
        self.assertTrue(gt.between("08:00", "08:00", "12:00"))

    def test_wraps_midnight(self):
        # Veskar's `04:00–00:00` and `00:00–04:00` windows (poc/npcs/veskar.md)
        day, night = gt.parse_window("04:00–00:00"), gt.parse_window("00:00-04:00")
        self.assertTrue(gt.between(gt.parse("Day 1 18:30"), *day))
        self.assertFalse(gt.between(gt.parse("Day 2 00:10"), *day))
        self.assertTrue(gt.between(gt.parse("Day 2 00:10"), *night))
        self.assertTrue(gt.between("23:30", "22:00", "02:00"))
        self.assertTrue(gt.between("01:00", "22:00", "02:00"))
        self.assertFalse(gt.between("02:00", "22:00", "02:00"))
        self.assertFalse(gt.between("12:00", "22:00", "02:00"))
        self.assertTrue(gt.between("12:00", "09:00", "09:00"))  # whole day


if __name__ == "__main__":
    unittest.main()
