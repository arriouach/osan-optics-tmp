from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ZidOrderFetchWizard(models.TransientModel):
    _name = 'zid.order.fetch.wizard'
    _description = 'Fetch Single Zid Order'

    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        default=lambda self: self._get_default_connector()
    )

    order_id = fields.Char(
        string='Order ID',
        required=True,
        help='Enter the Zid order ID to fetch'
    )

    @api.model
    def _get_default_connector(self):
        """Get default active connector"""
        connector = self.env['zid.connector'].search([
            ('authorization_status', '=', 'connected'),
            ('active', '=', True)
        ], limit=1)
        return connector

    def action_fetch_order(self):
        """Fetch single order from Zid"""
        self.ensure_one()

        if not self.zid_connector_id.is_connected:
            raise UserError(_('Selected connector is not connected to Zid'))

        if not self.order_id:
            raise UserError(_('Please enter an order ID'))

        try:
            # Make API request
            endpoint = f"managers/store/orders/{self.order_id}/view"
            response = self.zid_connector_id.api_request(
                endpoint=endpoint,
                method='GET'
            )

            if not response or 'order' not in response:
                raise UserError(_('Order not found or invalid response'))

            order_data = response['order']

            # Check if order exists
            order_model = self.env['zid.sale.order']
            existing = order_model.search([
                ('zid_order_id', '=', order_data.get('id')),
                ('zid_connector_id', '=', self.zid_connector_id.id)
            ], limit=1)

            if existing:
                # Update existing
                existing.write(self._prepare_order_values(order_data))
                message = _('Order updated successfully')
                order = existing
            else:
                # Create new
                order = order_model.create(self._prepare_order_values(order_data))
                message = _('Order created successfully')

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'zid.sale.order',
                'res_id': order.id,
                'view_mode': 'form',
                'target': 'current',
            }

        except Exception as e:
            _logger.error(f"Failed to fetch order: {str(e)}")
            raise UserError(_('Failed to fetch order: %s') % str(e))

    def _prepare_order_values(self, order_data):
        """Prepare order values - reuse from connector wizard"""
        connector_wizard = self.env['zid.sale.order.connector']
        vals = connector_wizard._prepare_order_values(order_data)
        vals['zid_connector_id'] = self.zid_connector_id.id
        return vals