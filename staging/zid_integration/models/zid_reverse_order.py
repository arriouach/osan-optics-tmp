from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class ZidReverseOrder(models.Model):
    _name = 'zid.reverse.order'
    _description = 'Zid Reverse Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'
    _order = 'create_date desc'

    # Connection
    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        ondelete='cascade'
    )

    # Original Order
    zid_order_id = fields.Many2one(
        'zid.sale.order',
        string='Original Order',
        required=True,
        ondelete='cascade'
    )

    order_code = fields.Char(
        related='zid_order_id.order_code',
        string='Order Code',
        store=True
    )

    # Reverse Order Info
    zid_reverse_id = fields.Char(
        string='Zid Reverse ID',
        readonly=True
    )

    store_id = fields.Char(
        string='Store ID',
        readonly=True
    )

    # Consignee Info (Who to pick up from)
    consignee_name = fields.Char(
        string='Consignee Name',
        required=True
    )

    consignee_mobile = fields.Char(
        string='Consignee Mobile',
        required=True
    )

    consignee_city_id = fields.Integer(
        string='City ID',
        required=True
    )

    consignee_city_name = fields.Char(
        string='City Name'
    )

    consignee_address_1 = fields.Char(
        string='Address Line 1',
        required=True
    )

    consignee_address_2 = fields.Char(
        string='Address Line 2'
    )

    # Inventory Location
    inventory_location_id = fields.Char(
        string='Inventory Location ID',
        help='Inventory location ID for multi-inventory stores'
    )

    # Reason
    reverse_reason_id = fields.Many2one(
        'zid.reverse.reason',
        string='Reverse Reason',
        required=True
    )

    # Waybill Info
    waybill_id = fields.Char(
        string='Waybill ID',
        readonly=True
    )

    waybill_cost = fields.Float(
        string='Waybill Cost',
        readonly=True
    )

    waybill_label_url = fields.Char(
        string='Label URL',
        readonly=True
    )

    waybill_tracking_number = fields.Char(
        string='Tracking Number',
        readonly=True
    )

    waybill_tracking_url = fields.Char(
        string='Tracking URL',
        readonly=True
    )

    waybill_status = fields.Char(
        string='Waybill Status',
        readonly=True
    )

    waybill_courier = fields.Char(
        string='Courier',
        readonly=True
    )

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent to Zid'),
        ('in_progress', 'In Progress'),
        ('waybill_created', 'Waybill Created'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    # Additional Info
    raw_response = fields.Text(
        string='Raw Response',
        readonly=True
    )

    # Computed
    display_name = fields.Char(
        compute='_compute_display_name',
        store=True
    )

    @api.depends('order_code', 'consignee_name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"REV-{record.order_code or 'NEW'} - {record.consignee_name or ''}"

    def action_send_to_zid(self):
        """Send reverse order to Zid"""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft reverse orders can be sent to Zid'))

        if not self.zid_connector_id.is_connected:
            raise UserError(_('Zid connector is not connected'))

        try:
            # Prepare data
            data = {
                'order_id': self.zid_order_id.zid_order_id,
                'consignee_name': self.consignee_name,
                'consignee_mobile': self.consignee_mobile,
                'consignee_city_id': self.consignee_city_id,
                'consignee_address_1': self.consignee_address_1,
                'consignee_address_2': self.consignee_address_2 or '',
                'inventory_location_id': self.inventory_location_id or '',
                'reason': [self.reverse_reason_id.name]
            }

            # Make API request
            response = self.zid_connector_id.api_request(
                endpoint='managers/store/reverse-orders',
                method='POST',
                data=data
            )

            # Update record with response
            if response:
                self.write({
                    'zid_reverse_id': response.get('id'),
                    'store_id': response.get('store_id'),
                    'state': 'sent',
                    'raw_response': json.dumps(response, indent=2)
                })

                # Update waybill info if present
                if response.get('waybill'):
                    waybill = response['waybill']
                    self.write({
                        'waybill_id': waybill.get('id'),
                        'waybill_cost': waybill.get('cost', 0),
                        'waybill_label_url': waybill.get('label'),
                        'waybill_tracking_number': waybill.get('tracking_number'),
                        'waybill_tracking_url': waybill.get('tracking_url'),
                        'waybill_status': waybill.get('status'),
                        'waybill_courier': waybill.get('courier'),
                        'state': 'waybill_created'
                    })

                # Update original order status
                self.zid_order_id.order_status = 'reverse_in_progress'

                # Increment reason usage
                self.reverse_reason_id.usage_count += 1

                self.message_post(
                    body=_('Reverse order sent to Zid successfully')
                )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Reverse order created successfully'),
                    'type': 'success',
                }
            }

        except Exception as e:
            _logger.error(f"Failed to create reverse order: {str(e)}")
            raise UserError(_('Failed to create reverse order: %s') % str(e))

    def action_create_waybill(self):
        """Create waybill for reverse order"""
        self.ensure_one()
        if self.state not in ['sent', 'in_progress']:
            raise UserError(_('Waybill can only be created for sent reverse orders'))

        if not self.zid_connector_id.is_connected:
            raise UserError(_('Zid connector is not connected'))

        try:
            # Make API request via proxy
            data = {
                'order_id': self.zid_order_id.zid_order_id,
                'is_standalone_zidship_waybill': 'true'
            }

            result = self.zid_connector_id.api_request(
                endpoint='managers/store/reverse-orders/waybill',
                method='POST',
                data=data
            )

            # Update waybill info
            if result and result.get('waybill'):
                waybill = result['waybill']
                self.write({
                    'waybill_id': waybill.get('id'),
                    'waybill_cost': waybill.get('cost', 0),
                    'waybill_label_url': waybill.get('label'),
                    'waybill_tracking_number': waybill.get('tracking_number'),
                    'waybill_tracking_url': waybill.get('tracking_url'),
                    'waybill_status': waybill.get('status'),
                    'waybill_courier': waybill.get('courier'),
                    'state': 'waybill_created',
                    'raw_response': json.dumps(result, indent=2)
                })

                self.message_post(
                    body=_('Waybill created successfully')
                )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Waybill created successfully'),
                    'type': 'success',
                }
            }

        except Exception as e:
            _logger.error(f"Failed to create waybill: {str(e)}")
            raise UserError(_('Failed to create waybill: %s') % str(e))

    def action_view_label(self):
        """Open waybill label"""
        self.ensure_one()
        if self.waybill_label_url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.waybill_label_url,
                'target': 'new',
            }
        else:
            raise UserError(_('No label available'))

    def action_track_shipment(self):
        """Open tracking URL"""
        self.ensure_one()
        if self.waybill_tracking_url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.waybill_tracking_url,
                'target': 'new',
            }
        else:
            raise UserError(_('No tracking URL available'))