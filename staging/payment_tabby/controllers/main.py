# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging
import pprint

from odoo import http
from odoo.addons.website_sale.controllers import main
from odoo.http import request

_logger = logging.getLogger(__name__)


class TabbyController(http.Controller):
    _success_url = "/payment/tabby/success"
    _failure_url = "/payment/tabby/failure"
    _cancel_url = "/payment/tabby/cancel"
    _webhook_url = "/payment/webhook/tabby"

    @http.route(
        "/payment/tabby/<string:status>",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        website=True,
        csrf=False,
        save_session=False,
    )
    def tabby_return_from_redirect(self, status, **post):
        """Process the data returned by Tabby after redirection.

        The route is flagged with `save_session=False` to prevent Odoo from assigning a new session
        to the user if they are redirected to this route with a POST request. Indeed, as the session
        cookie is created without a `SameSite` attribute, some browsers that don't implement the
        recommended default `SameSite=Lax` behavior will not include the cookie in the redirection
        request from the payment provider to Odoo. As the redirection to the '/payment/status' page
        will satisfy any specification of the `SameSite` attribute, the session of the user will be
        retrieved and with it the transaction which will be immediately post-processed."""

        _logger.info("received tabby return data : %s", pprint.pformat(post))
        provider_id = request.env["payment.provider"].sudo().search([("code", "=", "tabby")])
        response = provider_id._tabby_make_request(
            "/api/v2/payments/" + post.get("payment_id"), method="GET"
        )

        request.env["payment.transaction"].sudo().with_context(status=status)._handle_notification_data(
            "tabby", response
        )

        return request.redirect("/payment/status")

    @http.route('/payment/webhook/tabby', type="http", auth="public", csrf=False)
    def tabby_webhook(self, **response):
        """Process the data returned by Tabby after redirection."""

        _logger.info("received tabby webhook request : %s", pprint.pformat(request.httprequest))
        _logger.info("tabby webhook data : %s", pprint.pformat(response))

        data = json.loads(request.httprequest.data) if request.httprequest.data else {}
        data.update(response)

        request.env['ir.logging'].sudo().create({
            'name': 'Tabby',
            'type': 'server',
            'level': 'DEBUG',
            'dbname': request.env.cr.dbname,
            'message': "received tabby webhook data : %s" % pprint.pformat(data),
            'func': 'tabby_webhook',
            'path': 1,
            'line': '0',
        })
        request.env["payment.transaction"].sudo().with_context(status='notification',
                                                               notification_data=data)._handle_notification_data(
            "tabby", data
        )

        return request.make_json_response({"status": "success"})


class WebsiteSale(main.WebsiteSale):
    def _prepare_product_values(self, product, category, search, **kwargs):
        values = super(WebsiteSale, self)._prepare_product_values(product, category, search, **kwargs)
        acquirer_request = request.env.ref('payment_tabby.payment_acquirer_tabby')
        values['public_API_key'] = acquirer_request.sudo().tabby_public_api_key
        values['merchant_code'] = acquirer_request.sudo().tabby_merchant_code
        return values

    def _get_express_shop_payment_values(self, order, **kwargs):
        # using this method to avoid monkey patching parent and matches requirements, set if order
        values = super()._get_express_shop_payment_values(order, **kwargs)
        acquirer_request = request.env.ref('payment_tabby.payment_acquirer_tabby')
        values['public_API_key'] = acquirer_request.sudo().tabby_public_api_key
        values['merchant_code'] = acquirer_request.sudo().tabby_merchant_code
        return values
