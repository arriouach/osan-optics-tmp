# models/zid_webhook.py
import json
import logging

import requests
from odoo.exceptions import UserError

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class ZidWebhook(models.Model):
    _name = 'zid.webhook'
    _description = 'Zid Webhook Configuration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'event'

    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        ondelete='cascade'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='zid_connector_id.company_id',
        store=True,
        readonly=True
    )


    event = fields.Selection([
        ('product.create', 'Product Created'),
        ('product.update', 'Product Updated'),
        ('product.delete', 'Product Deleted'),
        ('order.create', 'Order Created'),
        ('order.status.update', 'Order Status Updated'),
        ('customer.create', 'Customer Created'),
    ], string='Event Type', required=True)

    webhook_url = fields.Char(
        string='Webhook URL',
        compute='_compute_webhook_url',
        store=True
    )

    zid_webhook_id = fields.Char(
        string='Zid Webhook ID',
        readonly=True
    )

    is_active = fields.Boolean(
        string='Active',
        default=True
    )

    conditions = fields.Text(
        string='Conditions (JSON)',
        help='JSON conditions for filtering webhook events'
    )

    last_triggered = fields.Datetime(
        string='Last Triggered',
        readonly=True
    )

    trigger_count = fields.Integer(
        string='Trigger Count',
        readonly=True,
        default=0
    )

    @api.depends('event')
    def _compute_webhook_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for webhook in self:
            if webhook.event:
                event_type = webhook.event.split('.')[0]  # product, order, customer
                webhook.webhook_url = f"{base_url}/zid/webhook/{event_type}"
            else:
                webhook.webhook_url = False

    def register_webhook(self):
        """Register this webhook with Zid"""
        self.ensure_one()

        if not self.zid_connector_id.is_connected:
            raise UserError(_('Connector is not connected to Zid'))

        # Prepare webhook data
        webhook_data = {
            'url': self.webhook_url,
            'event': self.event,
            'is_active': True
        }

        # Add conditions if specified
        if self.conditions:
            try:
                conditions = json.loads(self.conditions)
                webhook_data['conditions'] = conditions
            except json.JSONDecodeError:
                raise UserError(_('Invalid JSON in conditions field'))

        try:
            # Register webhook via API
            response = self.zid_connector_id.api_request(
                endpoint='webhooks/',
                method='POST',
                data=webhook_data
            )

            # Save webhook ID from response
            if response and response.get('id'):
                self.zid_webhook_id = str(response.get('id'))

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Webhook registered successfully'),
                    'type': 'success',
                }
            }

        except Exception as e:
            _logger.error(f"Failed to register webhook: {str(e)}")
            raise UserError(_('Failed to register webhook: %s') % str(e))

    def unregister_webhook(self):
        """Unregister this webhook from Zid"""
        self.ensure_one()

        if not self.zid_webhook_id:
            raise UserError(_('This webhook is not registered in Zid'))

        try:
            # Delete webhook via API
            self.zid_connector_id.api_request(
                endpoint=f'webhooks/{self.zid_webhook_id}',
                method='DELETE'
            )

            # Clear webhook ID
            self.zid_webhook_id = False
            self.is_active = False

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Webhook unregistered successfully'),
                    'type': 'success',
                }
            }

        except Exception as e:
            _logger.error(f"Failed to unregister webhook: {str(e)}")
            raise UserError(_('Failed to unregister webhook: %s') % str(e))

    def test_webhook(self):
        """Send a test request to the webhook URL"""
        self.ensure_one()

        test_data = {
            'test': True,
            'event': self.event,
            'store_id': self.zid_connector_id.store_id,
            'product': {
                'id': 'TEST123',
                'name': {'en': 'Test Product', 'ar': 'منتج تجريبي'},
                'sku': 'TEST-SKU',
                'price': 100.0,
                'quantity': 10,
                'is_published': True
            }
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=test_data,
                headers={
                    'Content-Type': 'application/json',
                    'X-Zid-Event': self.event
                },
                timeout=10
            )

            if response.status_code == 200:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Test webhook sent successfully'),
                        'type': 'success',
                    }
                }
            else:
                raise UserError(_('Test failed: %s') % response.text)

        except Exception as e:
            _logger.error(f"Webhook test failed: {str(e)}")
            raise UserError(_('Test failed: %s') % str(e))
