from odoo import fields, models


class PosOrderReport(models.Model):
    _inherit = 'report.pos.order'

    salesperson_id = fields.Many2one('hr.employee')

    def _group_by(self):
        res = super()._group_by()
        res += """,s.salesperson_id"""
        return res

    def _select(self):
        res = super()._select()
        res += """,s.salesperson_id AS salesperson_id"""
        return res
