# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class ZidWebhookController(http.Controller):

    @http.route('/zid/webhook/product', type='json', auth='public', methods=['POST'], csrf=False)
    def product_webhook(self, **kwargs):
        """Handle product webhooks from Zid"""
        try:
            data = request.jsonrequest
            event = request.httprequest.headers.get('X-Zid-Event', 'unknown')
            
            _logger.info(f"=== ZID PRODUCT WEBHOOK ===")
            _logger.info(f"Event: {event}")
            _logger.info(f"Data: {json.dumps(data, indent=2)}")
            
            # Process webhook based on event type
            if event == 'product.create':
                self._handle_product_create(data)
            elif event == 'product.update':
                self._handle_product_update(data)
            elif event == 'product.delete':
                self._handle_product_delete(data)
            else:
                _logger.warning(f"Unknown product event: {event}")
            
            # Update webhook trigger count
            self._update_webhook_stats(event)
            
            return {'status': 'success', 'message': 'Webhook processed'}
            
        except Exception as e:
            _logger.error(f"Product webhook error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/zid/webhook/order', type='json', auth='public', methods=['POST'], csrf=False)
    def order_webhook(self, **kwargs):
        """Handle order webhooks from Zid"""
        try:
            data = request.jsonrequest
            event = request.httprequest.headers.get('X-Zid-Event', 'unknown')
            
            _logger.info(f"=== ZID ORDER WEBHOOK ===")
            _logger.info(f"Event: {event}")
            _logger.info(f"Order ID: {data.get('id', 'unknown')}")
            
            # Process webhook based on event type
            if event == 'order.create':
                self._handle_order_create(data)
            elif event == 'order.status.update':
                self._handle_order_status_update(data)
            else:
                _logger.warning(f"Unknown order event: {event}")
            
            # Update webhook trigger count
            self._update_webhook_stats(event)
            
            return {'status': 'success', 'message': 'Webhook processed'}
            
        except Exception as e:
            _logger.error(f"Order webhook error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/zid/webhook/customer', type='json', auth='public', methods=['POST'], csrf=False)
    def customer_webhook(self, **kwargs):
        """Handle customer webhooks from Zid"""
        try:
            data = request.jsonrequest
            event = request.httprequest.headers.get('X-Zid-Event', 'unknown')
            
            _logger.info(f"=== ZID CUSTOMER WEBHOOK ===")
            _logger.info(f"Event: {event}")
            _logger.info(f"Customer ID: {data.get('id', 'unknown')}")
            
            # Process webhook based on event type
            if event == 'customer.create':
                self._handle_customer_create(data)
            else:
                _logger.warning(f"Unknown customer event: {event}")
            
            # Update webhook trigger count
            self._update_webhook_stats(event)
            
            return {'status': 'success', 'message': 'Webhook processed'}
            
        except Exception as e:
            _logger.error(f"Customer webhook error: {str(e)}", exc_info=True)
            return {'status': 'error', 'message': str(e)}

    @http.route('/zid/test', type='http', auth='public', methods=['GET'])
    def test_endpoint(self):
        """Test endpoint to verify module is working"""
        return "ZID Module Working!"

    # ==================== Webhook Handlers ====================
    
    def _handle_product_create(self, data):
        """Handle product creation webhook"""
        product_id = data.get('id')
        if not product_id:
            _logger.warning("Product create webhook missing ID")
            return
        
        # Find connector (assuming store_id in data or header)
        store_id = data.get('store_id') or request.httprequest.headers.get('X-Store-Id')
        if not store_id:
            _logger.warning("Cannot determine store_id from webhook")
            return
        
        connector = request.env['zid.connector'].sudo().search([
            ('store_id', '=', str(store_id))
        ], limit=1)
        
        if not connector:
            _logger.warning(f"No connector found for store {store_id}")
            return
        
        # Create or update product
        try:
            request.env['zid.product'].sudo().create_or_update_from_zid(
                data,
                connector.id
            )
            _logger.info(f"Product {product_id} created/updated via webhook")
        except Exception as e:
            _logger.error(f"Failed to create product from webhook: {str(e)}")

    def _handle_product_update(self, data):
        """Handle product update webhook"""
        self._handle_product_create(data)  # Same logic

    def _handle_product_delete(self, data):
        """Handle product deletion webhook"""
        product_id = str(data.get('id'))
        if not product_id:
            return
        
        # Find and archive product
        product = request.env['zid.product'].sudo().search([
            ('zid_product_id', '=', product_id)
        ], limit=1)
        
        if product:
            product.active = False
            _logger.info(f"Product {product_id} archived via webhook")

    def _handle_order_create(self, data):
        """Handle order creation webhook"""
        order_id = data.get('id')
        if not order_id:
            _logger.warning("Order create webhook missing ID")
            return
        
        # Find connector
        store_id = data.get('store_id') or request.httprequest.headers.get('X-Store-Id')
        if not store_id:
            _logger.warning("Cannot determine store_id from webhook")
            return
        
        connector = request.env['zid.connector'].sudo().search([
            ('store_id', '=', str(store_id))
        ], limit=1)
        
        if not connector:
            _logger.warning(f"No connector found for store {store_id}")
            return
        
        # Create queue entry for processing
        try:
            queue = request.env['zid.queue.ept'].sudo().create({
                'name': f'Webhook Order {order_id}',
                'zid_connector_id': connector.id,
                'model_type': 'order',
            })
            
            request.env['zid.queue.line.ept'].sudo().create({
                'queue_id': queue.id,
                'zid_id': str(order_id),
                'name': f'Order {order_id}',
                'data': json.dumps(data),
            })
            
            _logger.info(f"Order {order_id} queued for processing via webhook")
            
            # Process immediately if auto-process enabled
            if connector.auto_process_webhooks:
                queue.action_process()
                
        except Exception as e:
            _logger.error(f"Failed to queue order from webhook: {str(e)}")

    def _handle_order_status_update(self, data):
        """Handle order status update webhook"""
        order_id = str(data.get('id'))
        new_status = data.get('status')
        
        if not order_id or not new_status:
            return
        
        # Find and update order
        order = request.env['zid.sale.order'].sudo().search([
            ('zid_order_id', '=', order_id)
        ], limit=1)
        
        if order:
            # Validate status against allowed values
            allowed_statuses = dict(order._fields['order_status'].selection).keys()
            if new_status in allowed_statuses:
                order.order_status = new_status
                _logger.info(f"Order {order_id} status updated to {new_status} via webhook")
            else:
                _logger.warning(f"Unknown order status '{new_status}' received for order {order_id}. Skipping update.")

    def _handle_customer_create(self, data):
        """Handle customer creation webhook"""
        customer_id = data.get('id')
        if not customer_id:
            return
        
        # Find connector
        store_id = data.get('store_id') or request.httprequest.headers.get('X-Store-Id')
        if not store_id:
            return
        
        connector = request.env['zid.connector'].sudo().search([
            ('store_id', '=', str(store_id))
        ], limit=1)
        
        if not connector:
            return
        
        # Create or update customer
        try:
            # Extract customer data
            name = data.get('name', 'Guest')
            email = data.get('email')
            mobile = data.get('mobile')
            
            # Find or create partner
            domain = []
            if email:
                domain.append(('email', '=', email))
            if mobile and not domain:
                domain.append(('mobile', '=', mobile))
            
            partner = None
            if domain:
                partner = request.env['res.partner'].sudo().search(domain, limit=1)
            
            if partner:
                partner.write({
                    'name': name,
                    'email': email or partner.email,
                    'mobile': mobile or partner.mobile,
                })
            else:
                partner = request.env['res.partner'].sudo().create({
                    'name': name,
                    'email': email,
                    'mobile': mobile,
                    'customer_rank': 1,
                })
            
            _logger.info(f"Customer {customer_id} created/updated via webhook")
            
        except Exception as e:
            _logger.error(f"Failed to create customer from webhook: {str(e)}")

    def _update_webhook_stats(self, event):
        """Update webhook statistics"""
        try:
            webhook = request.env['zid.webhook'].sudo().search([
                ('event', '=', event)
            ], limit=1)
            
            if webhook:
                webhook.write({
                    'last_triggered': request.env.cr.now(),
                    'trigger_count': webhook.trigger_count + 1,
                })
        except Exception as e:
            _logger.error(f"Failed to update webhook stats: {str(e)}")