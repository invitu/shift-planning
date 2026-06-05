# Copyright 2026 INVITU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from datetime import date

from odoo.addons.hr_shift.tests.common import TestHrShiftBase


class TestShiftPattern(TestHrShiftBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Demo data may flag other employees with shift_planning=True; restrict
        # the planning generation to the test employees only.
        cls.env["hr.employee"].search(
            [
                ("shift_planning", "=", True),
                ("id", "not in", (cls.employee_a + cls.employee_b).ids),
            ]
        ).shift_planning = False
        cls.week_morning = cls.env["hr.shift.pattern.week"].create(
            {
                "name": "Morning week",
                "line_ids": [
                    (0, 0, {"day_number": "0", "template_id": cls.template_morning.id}),
                    (0, 0, {"day_number": "4", "template_id": cls.template_morning.id}),
                ],
            }
        )
        cls.week_afternoon = cls.env["hr.shift.pattern.week"].create(
            {
                "name": "Afternoon week",
                "line_ids": [
                    (
                        0,
                        0,
                        {"day_number": "0", "template_id": cls.template_afternoon.id},
                    ),
                ],
            }
        )
        cls.pattern = cls.env["hr.shift.pattern"].create(
            {
                "name": "Two weeks",
                "step_ids": [
                    (0, 0, {"sequence": 10, "week_id": cls.week_morning.id}),
                    (0, 0, {"sequence": 20, "week_id": cls.week_afternoon.id}),
                ],
            }
        )
        # Future weeks, so the recompute (future only) actually applies
        cls.start = date.fromisocalendar(2026, 30, 1)
        cls.employee_a.write(
            {
                "shift_pattern_id": cls.pattern.id,
                "shift_pattern_start_date": cls.start,
            }
        )

    def _make_planning(self, year, week):
        planning = self.env["hr.shift.planning"].create(
            {
                "year": year,
                "week_number": week,
                "start_date": date.fromisocalendar(year, week, 1),
                "end_date": date.fromisocalendar(year, week, 7),
            }
        )
        planning.generate_shifts()
        return planning

    def _shift(self, planning):
        return planning.shift_ids.filtered(
            lambda shift: shift.employee_id == self.employee_a
        )

    def _monday(self, shift):
        return shift.line_ids.filtered(lambda line: line.day_number == "0")

    def test_start_week_snapped_to_monday(self):
        # A mid-week date is normalised to its Monday
        self.employee_a.shift_pattern_start_date = date(2026, 7, 22)  # Wednesday
        self.assertEqual(self.employee_a.shift_pattern_start_date, date(2026, 7, 20))
        self.employee_a.shift_pattern_start_date = self.start

    def test_first_cycle_step(self):
        shift = self._shift(self._make_planning(2026, 30))
        self.assertEqual(shift.cycle_step, "1 / 2")
        self.assertEqual(self._monday(shift).template_id, self.template_morning)

    def test_second_cycle_step(self):
        shift = self._shift(self._make_planning(2026, 31))
        self.assertEqual(shift.cycle_step, "2 / 2")
        self.assertEqual(self._monday(shift).template_id, self.template_afternoon)

    def test_recompute_future_on_start_change(self):
        planning = self._make_planning(2026, 31)
        self.assertEqual(
            self._monday(self._shift(planning)).template_id, self.template_afternoon
        )
        # Shift the start one week later: week 31 becomes step 1 (morning)
        self.employee_a.shift_pattern_start_date = date.fromisocalendar(2026, 31, 1)
        self.assertEqual(
            self._monday(self._shift(planning)).template_id, self.template_morning
        )

    def test_manual_override(self):
        planning = self._make_planning(2026, 30)
        shift = self._shift(planning)
        shift.pattern_week_id = self.week_afternoon
        self.assertEqual(self._monday(shift).template_id, self.template_afternoon)

    def test_no_start_date_calendar_anchor(self):
        # Without a start date the cycle is always active (calendar-anchored)
        self.employee_a.shift_pattern_start_date = False
        shift = self._shift(self._make_planning(2026, 30))
        self.assertTrue(shift.cycle_step)
        self.assertIn(
            self._monday(shift).template_id,
            self.template_morning + self.template_afternoon,
        )

    def test_button_routes_to_manual_when_extra(self):
        # employee_b has no cycle -> it is counted as a manual shift
        planning = self._make_planning(2026, 30)
        self.assertEqual(planning.cycle_shifts_count, 1)
        self.assertEqual(planning.manual_shifts_count, 1)
        action = planning.action_view_manual_shifts()
        self.assertIn("shift_pattern_id", str(action["domain"]))
        self.assertIn("'=', False", str(action["domain"]))

    def test_button_routes_to_cycle_when_all_have_cycle(self):
        self.employee_b.write(
            {
                "shift_pattern_id": self.pattern.id,
                "shift_pattern_start_date": self.start,
            }
        )
        planning = self._make_planning(2026, 30)
        self.assertEqual(planning.cycle_shifts_count, 2)
        self.assertEqual(planning.manual_shifts_count, 0)
        action = planning.action_view_cycle_shifts()
        self.assertEqual(action["res_model"], "hr.shift.planning.line")
        self.assertIn("shift_pattern_id", str(action["domain"]))
        self.assertIn("'!=', False", str(action["domain"]))

    def test_all_lines_action_includes_cycle_and_manual(self):
        planning = self._make_planning(2026, 30)
        # both employees have shifts in the planning (one cycle, one extra)
        self.assertGreater(planning.all_lines_count, 0)
        action = planning.action_view_all_lines()
        self.assertEqual(action["res_model"], "hr.shift.planning.line")
        # no population filter in the domain: both cycle and manual visible
        self.assertNotIn("shift_pattern_id", str(action["domain"]))
