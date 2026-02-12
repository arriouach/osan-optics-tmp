from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ZidPayout(models.Model):
    _name = 'zid.payout'
    _description = 'Zid Payout/Settlement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'settlement_date desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    
    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True
    )

    settlement_date = fields.Date(string='Settlement Date', required=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('reconciled', 'Reconciled'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    amount_total = fields.Monetary(string='Total Amount', currency_field='currency_id')
    amount_fees = fields.Monetary(string='Fees', currency_field='currency_id')
    amount_net = fields.Monetary(string='Net Amount', currency_field='currency_id', compute='_compute_amount_net', store=True)
    
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', related='zid_connector_id.company_id', store=True)

    line_ids = fields.One2many('zid.payout.line', 'payout_id', string='Transactions')

    @api.depends('amount_total', 'amount_fees')
    def _compute_amount_net(self):
        for rec in self:
            rec.amount_net = rec.amount_total - rec.amount_fees

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('zid.payout') or 'New'
        return super().create(vals_list)

    def action_post(self):
        self.write({'state': 'posted'})

    def action_reconcile(self):
        """Logic to match lines with Odoo payments"""
        self.write({'state': 'reconciled'})


class ZidPayoutLine(models.Model):
    _name = 'zid.payout.line'
    _description = 'Zid Payout Transaction'

    payout_id = fields.Many2one('zid.payout', string='Payout', ondelete='cascade')
    
    zid_order_id = fields.Many2one('zid.sale.order', string='Zid Order')
    sale_order_id = fields.Many2one('sale.order', related='zid_order_id.sale_order_id', string='Odoo Order', store=True)
    
    transaction_type = fields.Selection([
        ('order', 'Order'),
        ('refund', 'Refund'),
        ('fee', 'Fee'),
        ('adjustment', 'Adjustment')
    ], string='Type', default='order')
    
    amount = fields.Monetary(string='Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='payout_id.currency_id')
    
    reference = fields.Char(string='Transaction Ref')
