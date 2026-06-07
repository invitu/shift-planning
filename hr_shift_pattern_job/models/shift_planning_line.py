# Copyright 2026 INVITU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class ShiftPlanningLine(models.Model):
    _inherit = "hr.shift.planning.line"

    job_id = fields.Many2one(
        comodel_name="hr.job",
        related="employee_id.job_id",
        store=True,
    )
