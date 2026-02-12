from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_is_salesperson_mandatory = fields.Boolean(related='pos_config_id.is_salesperson_mandatory', readonly=False)
    pos_selected_employee_ids = fields.Many2many(related='pos_config_id.selected_employee_ids', readonly=False)
