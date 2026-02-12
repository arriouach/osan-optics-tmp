# controllers/webhook_controller.py
from odoo import http
from odoo.http import request
import json
import logging
import hmac
import hashlib

_logger = logging.getLogger(__name__)


class ZidWebhookController(http.Controller):

    @http.route('/zid/webhook/product', type='json', auth='public', methods=['POST'], csrf=False)
    def product_webhook(self, **kwargs):
        """Handle product webhooks from Zid"""
        try:
            # Get the raw request data
            data = request.jsonrequest

            # Log the incoming webhook
            _logger.info(f"Received Zid webhook: {json.dumps(data, indent=2)}")

            # Get webhook headers for verification
            headers = request.httprequest.headers
            webhook_signature = headers.get('X-Zid-Signature')
            webhook_event = headers.get('X-Zid-Event')

            # Find the connector based on store ID or webhook secret
            store_id = data.get('store_id') or data.get('merchant_id')

            if not store_id:
                _logger.error("No store_id in webhook data")
                return {'status': 'error', 'message': 'Missing store_id'}

            # Find the connector
            connector = request.env['zid.connector'].sudo().search([
                ('store_id', '=', str(store_id)),
                ('authorization_status', '=', 'connected')
            ], limit=1)

            if not connector:
                _logger.error(f"No connector found for store_id: {store_id}")
                return {'status': 'error', 'message': 'Connector not found'}

            # Process based on event type
            if webhook_event == 'product.create':
                self._handle_product_create(data, connector)
            elif webhook_event == 'product.update':
                self._handle_product_update(data, connector)
            elif webhook_event == 'product.delete':
                self._handle_product_delete(data, connector)
            else:
                _logger.warning(f"Unhandled webhook event: {webhook_event}")

            return {'status': 'success', 'message': 'Webhook processed'}

        except Exception as e:
            _logger.error(f"Error processing webhook: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _handle_product_create(self, data, connector):
        """Handle product creation webhook"""
        try:
            product_data = data.get('product', data)

            # Check if product already exists
            existing = request.env['product.template'].sudo().search([
                ('zid_product_id', '=', str(product_data.get('id'))),
                ('zid_connector_id', '=', connector.id)
            ], limit=1)

            if existing:
                _logger.info(f"Product already exists: {existing.name}")
                return

            # Create new product
            product_vals = self._prepare_product_vals(product_data, connector)
            new_product = request.env['product.template'].sudo().create(product_vals)

            _logger.info(f"Created product from webhook: {new_product.name} (ID: {new_product.id})")

            # Commit the transaction
            request.env.cr.commit()

        except Exception as e:
            _logger.error(f"Error creating product from webhook: {str(e)}")
            request.env.cr.rollback()
            raise

    def _prepare_product_vals(self, product_data, connector):
        """Prepare product values from Zid data"""

        # Handle multilingual names
        name_data = product_data.get('name', {})
        if isinstance(name_data, dict):
            product_name = name_data.get('en') or name_data.get('ar') or 'Unknown Product'
        else:
            product_name = str(name_data) if name_data else 'Unknown Product'

        # Prepare basic values
        vals = {
            'name': product_name,
            'zid_connector_id': connector.id,
            'zid_product_id': str(product_data.get('id')),
            'zid_sku': product_data.get('sku'),
            'zid_barcode': product_data.get('barcode'),
            'list_price': float(product_data.get('price', 0)),
            'standard_price': float(product_data.get('cost', 0)),
            'type': 'product' if not product_data.get('is_infinite') else 'consu',
            'sale_ok': True,
            'purchase_ok': True,
            'zid_sync_status': 'synced',
            'zid_last_sync': fields.Datetime.now(),
        }

        # Add Zid-specific fields
        vals.update({
            'zid_slug': product_data.get('slug'),
            'zid_html_url': product_data.get('html_url'),
            'zid_price': float(product_data.get('price', 0)),
            'zid_sale_price': float(product_data.get('sale_price', 0)) if product_data.get('sale_price') else 0,
            'zid_formatted_price': product_data.get('formatted_price'),
            'zid_formatted_sale_price': product_data.get('formatted_sale_price'),
            'zid_currency': product_data.get('currency'),
            'zid_currency_symbol': product_data.get('currency_symbol'),
            'zid_quantity': int(product_data.get('quantity', 0)),
            'zid_is_infinite': product_data.get('is_infinite', False),
            'zid_is_published': product_data.get('is_published', False),
            'zid_is_draft': product_data.get('is_draft', False),
            'zid_requires_shipping': product_data.get('requires_shipping', False),
            'zid_is_taxable': product_data.get('is_taxable', False),
            'zid_has_options': product_data.get('has_options', False),
            'zid_response': json.dumps(product_data, ensure_ascii=False),
        })

        # Handle description
        description_data = product_data.get('description', {})
        if isinstance(description_data, dict):
            vals['description_sale'] = description_data.get('en') or description_data.get('ar')
        elif description_data:
            vals['description_sale'] = str(description_data)

        # Handle barcode
        if product_data.get('barcode'):
            vals['barcode'] = product_data.get('barcode')

        # Handle weight
        weight_data = product_data.get('weight', {})
        if isinstance(weight_data, dict):
            weight_value = weight_data.get('value', 0)
            weight_unit = weight_data.get('unit', 'kg')
            if weight_unit == 'g':
                weight_value = weight_value / 1000  # Convert to kg
            vals['weight'] = weight_value

        return vals