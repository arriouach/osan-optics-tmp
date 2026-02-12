# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from urllib.parse import parse_qsl, urlparse

from werkzeug import urls

from odoo import _, fields, models
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
CHECKOUT_ENDPOINT = "/api/v2/checkout"
CAPTURE_PAYMENT_ENDPOINT = "/api/v2/payments/%s/captures"
REFUND_ENDPOINT = "/api/v2/payments/%s/refunds"


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    capture_reference = fields.Char(string="Capture Reference", copy=False)
    cancel_reference = fields.Char(string="Cancel Reference", copy=False)
    refund_reference = fields.Char(string="Refund Reference", copy=False)

    def _get_specific_rendering_values(self, processing_values):
        """Override of payment to return Tabby-specific rendering values.g

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the transaction
        :return: The dict of provider-specific rendering values
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != "tabby":
            return res

        data = self._tabby_prepare_checkout_request_payload(processing_values)
        authentication_response = self.provider_id._tabby_make_request(CHECKOUT_ENDPOINT, data)
        installment_product = authentication_response.get("configuration", {}).get("products", {}).get("installments")
        if not installment_product.get("is_available"):
            raise ValidationError(_(f"Tabby: {installment_product.get('rejection_reason')}"))

        if (
            url := authentication_response.get("configuration", {})
            .get("available_products", {})
            .get("installments", [])[0]
            .get("web_url")
        ):
            self.provider_reference = authentication_response.get('payment', {}).get('id', '')
            parsed_url = urlparse(url)
            parameters = dict(parse_qsl(parsed_url.query), api_url=url)
            return parameters
        else:
            raise ValidationError(_("Tabby: Failed to establish connection!"))

    def _tabby_prepare_checkout_request_payload(self, processing_values):
        base_url = self.provider_id.get_base_url()
        partner_orders = self.env['sale.order'].search([
            ('partner_id', '=', self.partner_id.id),
            ('state', '=', 'sale'),
            ('transaction_ids.provider_id.code', '=', 'tabby'),
            ('transaction_ids.state', 'in', ('authorized', 'done'))], limit=10)
        return {
            "payment": {
                "amount": str(processing_values.get("amount")),
                "currency": self.env["res.currency"].browse(processing_values.get("currency_id")).display_name,
                "description": processing_values.get("reference"),
                "buyer": {
                    "phone": self.partner_phone,
                    "email": self.partner_email,
                    "name": self.partner_name,
                    "dob": "1970-01-01",
                },
                "shipping_address": {
                    "city": self.partner_city,
                    "address": self.partner_address,
                    "zip": self.partner_zip or '',
                },
                "order": {
                    "reference_id": self.reference,
                    "items": [{
                        "title": line.name,
                        "quantity": int(line.product_uom_qty),
                        "unit_price": str(line.price_unit),
                        "category": line.product_id.categ_id.name,
                    } for line in self.sale_order_ids.order_line]
                },
                "buyer_history": {
                    "registered_since": self.partner_id.create_date.isoformat() + 'Z',
                    "loyalty_level": len(partner_orders),
                },
                "order_history": [{
                    "purchased_at": order.date_order.isoformat() + 'Z',
                    "amount": str(order.amount_total),
                    "status": ORDER_STATUS.get(order.state, ''),
                    "buyer": {
                        "phone": order.partner_id.phone,
                        "email": order.partner_id.email,
                        "name": order.partner_id.name,
                    },
                    "shipping_address": {
                        "city": order.partner_shipping_id.city,
                        "address": payment_utils.format_partner_address(order.partner_shipping_id.street, order.partner_shipping_id.street2),
                        "zip": order.partner_shipping_id.zip or '',
                    }
                } for order in partner_orders],
            },
            "lang": self.partner_lang[:2],
            "merchant_code": self.provider_id.tabby_merchant_code,
            "merchant_urls": {
                "success": urls.url_join(base_url, TabbyController._success_url),
                "cancel": urls.url_join(base_url, TabbyController._cancel_url),
                "failure": urls.url_join(base_url, TabbyController._failure_url),
            },
        }

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Override of payment to find the transaction based on Tabby data.

        :param str provider: The provider of the provider that handled the transaction
        :param dict data: The feedback data sent by the provider
        :return: The transaction if found
        :rtype: recordset of `payment.transaction`
        :raise: ValidationError if the data match no transaction
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != "tabby":
            return tx

        payment_id = notification_data.get("id")
        tx = self.search([("provider_reference", "=", payment_id), ("provider_code", "=", provider_code)])
        if not tx:
            raise ValidationError(_("Tabby: " + "No transaction found matching Tabby payment id %s.", payment_id))
        return tx

    def _process_notification_data(self, data):
        """Override of payment to process the transaction based on Tabby data.

            Note: self.ensure_one()

        :param dict data: The feedback data sent by the provider
        :return: None
        """
        super()._process_notification_data(data)
        if self.provider_code != "tabby":
            return

        status = self.env.context.get("status")
        if status == "success":
            self._set_pending()
        elif status == "cancel":
            self._set_canceled(_("You aborted the payment. Please retry or choose another payment method."))
        elif status == "notification":
            self._handle_tabby_notification(data)
        else:
            self._set_error(_("Sorry, Tabby is unable to approve this purchase, please use an alternative payment method for your order."))

    def _handle_tabby_notification(self, data):
        """ Handle Tabby notification from webhooks."""
        status = data.get('status') or data.get('order_status')
        if status.lower() == "authorized":
            if not data.get('captures'):
                self._set_authorized()
                self._log_message_on_linked_documents(_("The transaction with reference %s has been approved and "
                                                        "authorized", self.provider_reference, ))
                self._send_capture_request()
            else:
                self._log_message_on_linked_documents(_("The transaction with reference %s has been captured", self.provider_reference,))
        elif status.lower() == "closed":
            self._set_done()
            self._log_message_on_linked_documents(_("The transaction with reference %s has been closed", self.provider_reference))
            if refunds := data.get('refunds'):
                self._log_message_on_linked_documents(_("The transaction with reference %s : An amount of %s has been refunded",
                                                        self.provider_reference, str([refund.amount for refund in refunds])))
            elif data.get('captures'):
                self._log_message_on_linked_documents(_("The transaction with reference %s has been captured", self.provider_reference,))
        elif status.lower() in ("rejected", "expired"):
            self._log_message_on_linked_documents(_("The transaction with reference %s has been %s ",
                                                    self.provider_reference, status))

    def _send_capture_request(self, amount_to_capture=None):
        child_capture_tx = super()._send_capture_request(amount_to_capture=amount_to_capture)
        if self.provider_code != 'tabby':
            return child_capture_tx
        data = {
            "amount": amount_to_capture or self.amount,
            "reference_id": self.provider_reference,
        }

        capture_response = self.provider_id._tabby_make_request(CAPTURE_PAYMENT_ENDPOINT % self.provider_reference, data)
        self._log_message_on_linked_documents(_(
            "The capture of the transaction with reference %s has been requested (%s).",
            self.reference, self.provider_id.name
        ))
        if capture_response.get("captures", {}):
            self.capture_reference = capture_response.get("captures", {})[0].get("id")
            self._set_done()
        return child_capture_tx

    def _send_refund_request(self, amount_to_refund=None):
        """ Override of payment to send a refund request to Adyen.

        Note: self.ensure_one()

        :param float amount_to_refund: The amount to refund
        :return: The refund transaction created to process the refund request.
        :rtype: recordset of `payment.transaction`
        """
        refund_tx = super()._send_refund_request(amount_to_refund=amount_to_refund)
        if self.provider_code != 'tabby':
            return refund_tx

        data = {
            "amount": self.amount,
            "reference_id": self.provider_reference,
        }
        refund_response = self.provider_id._tabby_make_request(REFUND_ENDPOINT % self.provider_reference, data)
        self._log_message_on_linked_documents(_(
            "A request was sent to void the transaction with reference %s (%s) with provider reference %s.",
            self.reference, self.provider_id.name, self.provider_reference))
        if refund_response.get("refunds"):
            self.refund_reference = refund_response.get("refunds")[0].get("id")
            refund_tx._set_done()
        return refund_tx
