from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ZidAbandonedCartFetchWizard(models.TransientModel):
    _name = 'zid.abandoned.cart.fetch.wizard'
    _description = 'Fetch Abandoned Carts from Zid'

    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        default=lambda self: self._get_default_connector()
    )

    date_from = fields.Date(
        string='From Date',
        help='Fetch carts abandoned after this date'
    )

    date_to = fields.Date(
        string='To Date',
        default=fields.Date.today,
        help='Fetch carts abandoned before this date'
    )

    min_cart_value = fields.Float(
        string='Minimum Cart Value',
        default=0.0,
        help='Only fetch carts with value above this amount'
    )

    @api.model
    def _get_default_connector(self):
        """Get default active connector"""
        connector = self.env['zid.connector'].search([
            ('authorization_status', '=', 'connected'),
            ('active', '=', True)
        ], limit=1)
        return connector

    def action_fetch_carts(self):
        """Fetch abandoned carts from Zid"""
        self.ensure_one()

        if not self.zid_connector_id.is_connected:
            raise UserError(_('Selected connector is not connected to Zid'))

        try:
            # Prepare API parameters
            params = {}
            if self.date_from:
                params['from_date'] = self.date_from.strftime('%Y-%m-%d')
            if self.date_to:
                params['to_date'] = self.date_to.strftime('%Y-%m-%d')

            # Make API request
            # Note: Endpoint may vary - check Zid API documentation
            response = self.zid_connector_id.api_request(
                endpoint='managers/store/abandoned-carts',
                method='GET',
                params=params
            )

            if not response:
                raise UserError(_('No response from Zid API'))

            # Parse response
            carts_data = response.get('carts', []) or response.get('data', []) or []
            
            if not carts_data:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Info'),
                        'message': _('No abandoned carts found'),
                        'type': 'info',
                    }
                }

            # Create/update abandoned cart records
            cart_model = self.env['zid.abandoned.cart']
            created_count = 0
            updated_count = 0

            for cart_data in carts_data:
                cart_id = cart_data.get('id')
                if not cart_id:
                    continue

                # Check minimum value filter
                cart_total = float(cart_data.get('total', 0) or 0)
                if self.min_cart_value > 0 and cart_total < self.min_cart_value:
                    continue

                # Check if exists
                existing = cart_model.search([
                    ('zid_cart_id', '=', str(cart_id)),
                    ('zid_connector_id', '=', self.zid_connector_id.id)
                ], limit=1)

                vals = self._prepare_cart_values(cart_data)

                if existing:
                    existing.write(vals)
                    updated_count += 1
                else:
                    cart_model.create(vals)
                    created_count += 1

            message = _('Fetched abandoned carts:\n')
            message += _('✅ Created: %d\n') % created_count
            message += _('🔄 Updated: %d\n') % updated_count
            message += _('📊 Total: %d') % (created_count + updated_count)

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': message,
                    'type': 'success',
                    'sticky': True,
                }
            }

        except Exception as e:
            _logger.error(f"Failed to fetch abandoned carts: {str(e)}")
            raise UserError(_('Failed to fetch abandoned carts: %s') % str(e))

    def _prepare_cart_values(self, cart_data):
        """Prepare values for abandoned cart record"""
        import json
        
        vals = {
            'zid_connector_id': self.zid_connector_id.id,
            'zid_cart_id': str(cart_data.get('id')),
            'customer_name': cart_data.get('customer', {}).get('name'),
            'customer_email': cart_data.get('customer', {}).get('email'),
            'customer_mobile': cart_data.get('customer', {}).get('mobile'),
            'cart_total': float(cart_data.get('total', 0) or 0),
            'currency_code': cart_data.get('currency', 'SAR'),
            'cart_lines_data': json.dumps(cart_data.get('items', [])),
            'abandoned_date': cart_data.get('abandoned_at') or cart_data.get('updated_at'),
            'recovery_status': 'pending',
        }
        
        return vals
