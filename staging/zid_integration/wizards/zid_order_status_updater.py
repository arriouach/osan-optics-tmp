from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ZidOrderStatusUpdater(models.TransientModel):
    _name = 'zid.order.status.updater'
    _description = 'Update Zid Order Status'

    zid_order_id = fields.Many2one(
        'zid.sale.order',
        string='Zid Order',
        required=True,
        readonly=True
    )

    current_status = fields.Selection([
        ('new', 'New'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready'),
        ('indelivery', 'In Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled')
    ], string='Current Status', readonly=True)

    new_status = fields.Selection([
        ('new', 'New'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready'),
        ('indelivery', 'In Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled')
    ], string='New Status', required=True)

    inventory_address_id = fields.Char(
        string='Inventory Address ID',
        help='Required when changing status to Ready for shipping company pickup'
    )

    tracking_number = fields.Char(
        string='Tracking Number'
    )

    tracking_url = fields.Char(
        string='Tracking URL'
    )

    waybill_url = fields.Char(
        string='Waybill URL'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_id'):
            order = self.env['zid.sale.order'].browse(self.env.context['active_id'])
            res.update({
                'zid_order_id': order.id,
                'current_status': order.order_status
            })
        return res

    def action_update_status(self):
        """Update order status in Zid"""
        self.ensure_one()

        if not self.zid_order_id.zid_connector_id.is_connected:
            raise UserError(_('Zid connector is not connected'))

        # Prepare data for API
        data = {
            'order_status': self.new_status
        }

        if self.inventory_address_id:
            data['inventory_address_id'] = self.inventory_address_id
        if self.tracking_number:
            data['tracking_number'] = self.tracking_number
        if self.tracking_url:
            data['tracking_url'] = self.tracking_url
        if self.waybill_url:
            data['waybill_url'] = self.waybill_url

        try:
            # Make API request using multipart/form-data
            response = self._update_order_status_api(data)

            # Update local record
            self.zid_order_id.write({
                'order_status': self.new_status,
                'last_sync_date': fields.Datetime.now()
            })

            # Log the update
            self.zid_order_id.message_post(
                body=_('Order status updated from %s to %s') % (
                    self.current_status, self.new_status
                )
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Order status updated successfully'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f"Failed to update order status: {str(e)}")
            raise UserError(_('Failed to update order status: %s') % str(e))

    def _update_order_status_api(self, data):
        """Make API request to update order status via proxy"""
        connector = self.zid_order_id.zid_connector_id
        endpoint = f"managers/store/orders/{self.zid_order_id.zid_order_id}/change-order-status"
        
        response = connector.api_request(
            endpoint=endpoint,
            method='POST',
            data=data
        )
        
        return response