# Part of Odoo. See LICENSE file for full copyright and licensing details.
import html
import logging

import requests
from werkzeug import urls

from odoo import _, api, fields, models
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_tabby.controllers.main import TabbyController
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)
ORDER_STATUS = {
    'draft': 'new',
    'sent': 'processing',
    'sale': 'complete',
    'cancel': 'canceled'
}
PRE_SCORING_ENDPOINT = "/api/v2/checkout"
WEBHOOKS_ENDPOINT = "/api/v1/webhooks"


class PaymentAcquirer(models.Model):
    _inherit = "payment.provider"

    code = fields.Selection(selection_add=[("tabby", "Tabby")], ondelete={"tabby": "set default"})
    tabby_public_api_key = fields.Char(string="Public API Key", required_if_provider="tabby", groups="base.group_user")
    tabby_secret_api_key = fields.Char(string="Secret API Key", required_if_provider="tabby", groups="base.group_user")
    tabby_merchant_code = fields.Char(string="Merchant Code", required_if_provider="tabby", groups="base.group_user")
    webhook_id = fields.Char(string="Webhook ID")
    supported_currency_ids = fields.Many2many("res.currency", string="Supported Currencies")

    def _tabby_make_request(self, endpoint, data=None, method="POST", pre=False):
        """Make a request to Tabby endpoint.

        Note: self.ensure_one()

        :param str endpoint: The endpoint to be reached by the request
        :param dict data: The payload of the request
        :param str method: The HTTP method of the request
        :return The JSON-formatted content of the response
        :rtype: dict
        :raise: ValidationError if an HTTP error occurs
        """
        # Tabby enforces only showing the payment options if they have payment options
        url = 'https://api.tabby.ai'

        headers = {"Content-Type": "application/json", "Authorization": "Bearer %s" % self.tabby_secret_api_key}
        self.ensure_one()
        if self._context.get('webhook_request'):
            headers['X-Merchant-Code'] = self.tabby_merchant_code
        try:
            response = requests.request(method, url + html.escape(endpoint), json=data, headers=headers, timeout=60)
            if response.json().get("errors", [{}])[0].get("message"):
                raise ValidationError(_("Tabby: " + response.json()["errors"][0].get("message")))
            # check if this is a precheckout request and ignore raised errors as it effects all providers
            if not pre:
                response.raise_for_status()
            _logger.info("Tabby Response: %s", response.json())
        except requests.exceptions.RequestException:
            _logger.exception("Error details: %s", response.json())
            _logger.exception("Unable to communicate with Tabby: %s", endpoint)
            raise ValidationError(_("Tabby: " + "Could not establish a connection to the API."))
        return response.json()

    @api.model
    def _get_compatible_providers(
        self, company_id, partner_id, amount, currency_id=None, force_tokenization=False,
        is_express_checkout=False, is_validation=False, report=None, **kwargs
    ):
        """ Override of to filter out tabby payment if the currency is not allowed
        """
        providers = super()._get_compatible_providers(company_id=company_id, partner_id=partner_id, amount=amount, currency_id=currency_id, force_tokenization=force_tokenization,
                                                      is_express_checkout=is_express_checkout, is_validation=is_validation, report=report, **kwargs)
        currency = self.env['res.currency'].browse(currency_id).exists()
        sale_order = self.env['sale.order'].browse(kwargs.get('sale_order_id'))
        pre_scoring_response = {}
        if sale_order:
            tabby = self.env.ref('payment_tabby.payment_acquirer_tabby')
            pre_scoring_data = self._tabby_prepare_pre_scoring_request_payload(tabby, sale_order)
            # We shouldn't raise an Error here as this blocks other payment providers
            try:
                pre_scoring_response = tabby._tabby_make_request(PRE_SCORING_ENDPOINT,
                                                                    pre_scoring_data, pre=True)
            except:
                pre_scoring_response = {}

        if sale_order and not pre_scoring_response.get("configuration", {}).get("products", {}).get("installments", {}).get("is_available"):
            providers = providers.filtered(lambda r: r.code != "tabby")
        else:
            filtered_tabby = providers.filtered(lambda r: r.code == "tabby" and currency in r.supported_currency_ids)
            providers = providers.filtered(lambda r: r.code != "tabby" or r in filtered_tabby)

        return providers

    @api.model
    def _tabby_prepare_pre_scoring_request_payload(self, tabby_provider, order):
        base_url = self.get_base_url()
        partner_orders = self.env['sale.order'].search([
            ('partner_id', '=', order.partner_id.id),
            ('state', '=', 'sale'),
            ('transaction_ids.provider_id.code', '=', 'tabby'),
            ('transaction_ids.state', 'in', ('authorized', 'done'))], limit=10)
        return {
            "payment": {
                "amount": str(order.amount_total),
                "currency": order.currency_id.display_name,
                "description": order.name,
                "buyer": {
                    "phone": order.partner_id.phone,
                    "email": order.partner_id.email,
                    "name": order.partner_id.name,
                    "dob": "1970-01-01",
                },
                "shipping_address": {
                    "city": order.partner_id.city,
                    "address": payment_utils.format_partner_address(order.partner_shipping_id.street, order.partner_shipping_id.street2),
                    "zip": order.partner_id.zip or '',
                },
                "order": {
                    "reference_id": order.name,
                    "items": [{
                        "title": line.name,
                        "quantity": int(line.product_uom_qty),
                        "unit_price": str(line.price_unit),
                        "category": line.product_id.categ_id.name,
                    } for line in order.order_line]
                },
                "buyer_history": {
                    "registered_since": order.partner_id.create_date.isoformat() + 'Z',
                    "loyalty_level": len(partner_orders),
                },
                "order_history": [{
                    "purchased_at": record.date_order.isoformat() + 'Z',
                    "amount": str(record.amount_total),
                    "status": ORDER_STATUS.get(record.state, ''),
                    "buyer": {
                        "phone": record.partner_id.phone,
                        "email": record.partner_id.email,
                        "name": record.partner_id.name,
                    },
                    "shipping_address": {
                        "city": record.partner_shipping_id.city,
                        "address": payment_utils.format_partner_address(record.partner_shipping_id.street, record.partner_shipping_id.street2),
                        "zip": record.partner_shipping_id.zip or '',
                    }
                } for record in partner_orders],
            },
            "lang": order.partner_id.lang[:2],
            "merchant_code": tabby_provider.tabby_merchant_code,
            "merchant_urls": {
                "success": urls.url_join(base_url, TabbyController._success_url),
                "cancel": urls.url_join(base_url, TabbyController._cancel_url),
                "failure": urls.url_join(base_url, TabbyController._failure_url),
            },
        }

    def _compute_feature_support_fields(self):
        """ Override of `payment` to enable additional features. """
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'tabby').update({
            'support_manual_capture': 'partial',
            'support_refund': 'partial'
        })

    def action_register_webhook(self):
        self.ensure_one()
        if self.code != "tabby":
            return
        base_url = self.get_base_url()
        webhook_data = {
            "url": urls.url_join(base_url, TabbyController._webhook_url),
            "is_test": True if self.state == "test" else False,
        }
        webhook_register_response = self.with_context(webhook_request=True)._tabby_make_request(WEBHOOKS_ENDPOINT, webhook_data)
        if webhook_id := webhook_register_response.get('id'):
            self.write({'webhook_id': webhook_id})

    def action_remove_webhook(self):
        self.ensure_one()
        if self.code != "tabby":
            return
        if not self.webhook_id:
            raise ValidationError(_("There is no registerd webhook!"))
        webhook_remove_response = self.with_context(webhook_request=True)._tabby_make_request(WEBHOOKS_ENDPOINT + "/" + self.webhook_id, method="DELETE")
        self.write({'webhook_id': False})
