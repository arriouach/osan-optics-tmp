from odoo import fields, models


class PosConfig(models.Model):
    _inherit = 'pos.config'

    analytic_account_ids = fields.Many2many('account.analytic.account')
