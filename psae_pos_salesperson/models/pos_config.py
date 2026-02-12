from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    is_salesperson_mandatory = fields.Boolean()
    selected_employee_ids = fields.Many2many('hr.employee')
