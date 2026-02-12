from odoo import fields, models


class HrEmployeeBase(models.AbstractModel):
    _inherit = 'hr.employee.base'

    can_discount = fields.Boolean()
    can_change_price = fields.Boolean()
    can_see_cost_margin = fields.Boolean()
    can_refund = fields.Boolean()
    can_change_quantity = fields.Boolean()
    can_remove_line = fields.Boolean()
    can_change_price_list = fields.Boolean()
