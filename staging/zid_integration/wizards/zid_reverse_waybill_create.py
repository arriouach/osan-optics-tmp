from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ZidReverseWaybillCreate(models.TransientModel):
    _name = 'zid.reverse.waybill.create'
    _description = 'Create Waybill for Reverse Order'

    reverse_order_id = fields.Many2one(
        'zid.reverse.order',
        string='Reverse Order',
        required=True,
        readonly=True
    )

    order_code = fields.Char(
        related='reverse_order_id.order_code',
        string='Order Code',
        readonly=True
    )

    zid_order_id = fields.Integer(
        related='reverse_order_id.zid_order_id.zid_order_id',
        string='Zid Order ID',
        readonly=True
    )

    current_state = fields.Selection(
        related='reverse_order_id.state',
        string='Current Status',
        readonly=True
    )

    is_standalone_zidship_waybill = fields.Boolean(
        string='Standalone Zidship Waybill',
        default=True,
        help='Create as standalone Zidship waybill'
    )

    # Display existing waybill info if any
    has_waybill = fields.Boolean(
        compute='_compute_has_waybill'
    )

    existing_waybill_id = fields.Char(
        related='reverse_order_id.waybill_id',
        string='Existing Waybill ID',
        readonly=True
    )

    existing_tracking_number = fields.Char(
        related='reverse_order_id.waybill_tracking_number',
        string='Existing Tracking Number',
        readonly=True
    )

    @api.depends('reverse_order_id.waybill_id')
    def _compute_has_waybill(self):
        for record in self:
            record.has_waybill = bool(record.reverse_order_id.waybill_id)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_id'):
            reverse_order = self.env['zid.reverse.order'].browse(self.env.context['active_id'])
            res['reverse_order_id'] = reverse_order.id
        return res

    def action_create_waybill(self):
        """Create waybill for reverse order"""
        self.ensure_one()

        if self.has_waybill:
            raise UserError(_('This reverse order already has a waybill'))

        if self.current_state not in ['sent', 'in_progress']:
            raise UserError(_('Waybill can only be created for sent reverse orders'))

        try:
            # Call the reverse order's create waybill method
            self.reverse_order_id.action_create_waybill()

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'zid.reverse.order',
                'res_id': self.reverse_order_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

        except Exception as e:
            _logger.error(f"Failed to create waybill: {str(e)}")
            raise UserError(_('Failed to create waybill: %s') % str(e))