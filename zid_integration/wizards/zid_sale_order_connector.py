from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class ZidSaleOrderConnector(models.TransientModel):
    _name = 'zid.sale.order.connector'
    _description = 'Zid Sale Order Import Wizard'

    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        default=lambda self: self._get_default_connector()
    )

    # Date Filters (Start Sync Date)
    date_from = fields.Datetime(
        string='Start Sync Date',
        default=lambda self: fields.Datetime.now() - timedelta(days=7),
        help="Fetch orders created or modified after this date."
    )

    date_to = fields.Datetime(
        string='End Sync Date',
        default=fields.Datetime.now,
        help="Fetch orders created or modified before this date."
    )

    # Other Filters
    order_status = fields.Selection([
        ('all', 'All Orders'),
        ('new', 'New'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready'),
        ('indelivery', 'In Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('reversed', 'Reversed'),
        ('refunded', 'Refunded'),
        ('reverse_in_progress', 'Reverse In Progress'),
        ('ready_for_reverse', 'Ready For Reverse'),
        ('partially_reversed', 'Partially Reversed')
    ], string='Order Status', default='all')

    payment_status = fields.Selection([
        ('all', 'All'),
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('refunded', 'Refunded'),
        ('voided', 'Voided')
    ], string='Payment Status', default='all')

    import_mode = fields.Selection([
        ('new', 'Import New Orders Only'),
        ('update', 'Update Existing Orders'),
        ('all', 'Import All Orders')
    ], string='Import Mode', default='new', required=True)

    order_ids = fields.Text(
        string='Specific Order IDs',
        help='Comma-separated order IDs to import specific orders'
    )

    # Batch & Progress Tracking Fields
    state = fields.Selection([
        ('draft', 'Draft'),
        ('importing', 'Importing'),
        ('done', 'Done'),
        ('error', 'Error')
    ], string='Status', default='draft', readonly=True)

    progress_text = fields.Text(
        string='Progress',
        readonly=True
    )
    
    current_page = fields.Integer(string='Current Page', default=1, readonly=True)
    total_fetched = fields.Integer(string='Total Orders Fetched', default=0, readonly=True)
    page_size = fields.Integer(string='Batch Size', default=50, help='Number of orders to fetch per request')
    
    # Store the queue ID to resume processing
    current_queue_id = fields.Many2one('zid.queue.ept', string='Current Queue', readonly=True)
    
    # Error tracking
    error_message = fields.Text(string='Error Message', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        connector_id = res.get('zid_connector_id') or self._get_default_connector()
        if connector_id:
            if isinstance(connector_id, int):
                connector = self.env['zid.connector'].browse(connector_id)
            else:
                connector = connector_id
            
            if connector.order_import_start_date:
                res['date_from'] = connector.order_import_start_date
        return res

    @api.model
    def _get_default_connector(self):
        """Get default active connector"""
        connector = self.env['zid.connector'].search([
            ('authorization_status', '=', 'connected'),
        ], limit=1)
        return connector

    def _prepare_api_params(self):
        """Prepare parameters for API request"""
        params = {}

        # Date filters - Using updated_at to filter by order modification date
        if self.date_from:
            # Use updated_at parameters for Zid API
            params['updated_at_from'] = self.date_from.isoformat()
            params['date_from'] = self.date_from.isoformat()  # Keep for backward compatibility
            params['date_attribute'] = 'updated_at'  # Tell Zid which date field to filter by
        if self.date_to:
            params['updated_at_to'] = self.date_to.isoformat()
            params['date_to'] = self.date_to.isoformat()
            if 'date_attribute' not in params:
                params['date_attribute'] = 'updated_at'

        # Status filters
        if self.order_status != 'all':
            params['status'] = self.order_status
        if self.payment_status != 'all':
            params['payment_status'] = self.payment_status

        # Specific order IDs
        if self.order_ids:
            params['order_id'] = self.order_ids.replace(' ', '')

        return params

    def action_start_import(self):
        """Initialize import process"""
        self.ensure_one()
        
        # Reset progress (but don't create queue yet - only when we have data)
        self.write({
            'state': 'importing',
            'current_page': 1,
            'total_fetched': 0,
            'progress_text': _('Starting import...\n'),
            'error_message': False,
            'current_queue_id': False,  # No queue yet
        })
        
        # Commit to save initialization
        self.env.cr.commit()
        
        # Start batch processing
        return self.action_process_batch()

    def action_process_batch(self):
        """Process a single batch (page) and return action to continue"""
        self.ensure_one()
        
        if self.state != 'importing':
            return
            
        try:
            params = self._prepare_api_params()
            params.update({
                'page': self.current_page,
                'per_page': self.page_size
            })

            self._update_progress(_('Fetching page %d...') % self.current_page)
            
            # Fetch from Proxy
            result = self.zid_connector_id.call_proxy_api(
                '/api/zid/fetch-orders',
                params
            )

            if not result.get('success'):
                error = result.get('error', 'Unknown error')
                raise UserError(_('Proxy error: %s') % error)

            orders = result.get('orders', [])
            
            # Client-side date filtering (since Zid API may not respect date parameters)
            if self.date_from or self.date_to:
                filtered_orders = []
                for order in orders:
                    updated_at_str = order.get('updated_at')
                    if not updated_at_str:
                        # Fallback to created_at if updated_at is missing
                        updated_at_str = order.get('created_at')
                    
                    if not updated_at_str:
                        continue
                    
                    try:
                        # Parse Zid's datetime format: "2025-12-28 13:41:16"
                        from datetime import datetime
                        updated_at = datetime.strptime(updated_at_str, '%Y-%m-%d %H:%M:%S')
                        
                        # Check if within range
                        if self.date_from and updated_at < self.date_from:
                            continue
                        if self.date_to and updated_at > self.date_to:
                            continue
                            
                        filtered_orders.append(order)
                    except Exception as e:
                        _logger.warning(f"Could not parse updated_at/created_at for order {order.get('id')}: {updated_at_str}")
                        # Include order if we can't parse the date
                        filtered_orders.append(order)
                
                orders = filtered_orders
                _logger.info(f"Filtered {len(result.get('orders', []))} orders to {len(orders)} within modification date range")
            
            if not orders:
                # No more orders, we are done
                if self.total_fetched == 0:
                    # No orders found at all - don't create empty queue
                    self._finish_import_no_data()
                else:
                    # Some orders were processed in previous batches
                    self._finish_import()
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'zid.sale.order.connector',
                    'res_id': self.id,
                    'view_mode': 'form',
                    'target': 'new',
                }

            # Create queue ONLY when we have data to process
            queue = self.current_queue_id
            if not queue:
                # First batch with actual data - create queue now
                queue = self.env['zid.queue.ept'].create({
                    'zid_connector_id': self.zid_connector_id.id,
                    'model_type': 'order',
                    'name': _('Order Import - %s') % fields.Datetime.now()
                })
                self.current_queue_id = queue.id
                _logger.info(f"Created queue {queue.name} for {len(orders)} orders")

            queue_lines = []
            for order_data in orders:
                queue_lines.append({
                    'queue_id': queue.id,
                    'zid_id': str(order_data.get('id')),
                    'name': order_data.get('code'),
                    'data': json.dumps(order_data, ensure_ascii=False),
                    'state': 'draft'
                })
            
            if queue_lines:
                self.env['zid.queue.line.ept'].create(queue_lines)
            
            # Update counters
            fetched_count = len(orders)
            new_total = self.total_fetched + fetched_count
            self.write({
                'current_page': self.current_page + 1,
                'total_fetched': new_total,
                'progress_text': self.progress_text + _('✓ Fetched %d orders (Total: %d)\n') % (fetched_count, new_total)
            })
            
            # Commit this batch
            self.env.cr.commit()
            
            # Check if we should continue
            if fetched_count < self.page_size:
                # Less than page size means end of results
                self._finish_import()
            else:
                # Return server action to call this method again immediately (loop)
                # We return the dictionary of the action, pointing to the XML record
                action_ref = self.env.ref('zid_integration.action_zid_import_orders_batch_processing')
                if not action_ref:
                     raise UserError(_("Server action for batch processing not found."))

                action = action_ref.read()[0]
                action['context'] = {'active_ids': [self.id], 'active_id': self.id}
                return action

        except Exception as e:
            self.env.cr.rollback()
            _logger.error(f"Batch import failed: {str(e)}")
            self.write({
                'state': 'error',
                'error_message': str(e),
                'progress_text': self.progress_text + _('\n❌ Error: %s') % str(e)
            })
            self.env.cr.commit()
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'zid.sale.order.connector',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'zid.sale.order.connector',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _finish_import(self):
        """Finalize import"""
        self.write({
            'state': 'done',
            'progress_text': self.progress_text + _('\n✓ All pages fetched. Processing queue...\n')
        })
        self.env.cr.commit() # Save state before processing
        
        # Auto-process the queue after fetching
        if self.current_queue_id:
             self.current_queue_id.action_process()
             
        # Trigger status sync for recent orders if enabled
        try:
            zid_order_model = self.env['zid.sale.order']
            zid_order_model.sync_status_during_import(self.zid_connector_id)
        except Exception as e:
            _logger.warning(f"Status sync during import failed: {str(e)}")
             
        self.write({
            'progress_text': self.progress_text + _('✓ Queue processed successfully.')
        })

    def _finish_import_no_data(self):
        """Finalize import when no data was found"""
        self.write({
            'state': 'done',
            'progress_text': self.progress_text + _('\n✓ Import completed - No orders found matching criteria.\n')
        })
        _logger.info("Import completed with no orders found - no queue created")

    def action_reset(self):
        """Reset wizard to draft"""
        self.write({
            'state': 'draft',
            'current_page': 1,
            'total_fetched': 0,
            'progress_text': '',
            'error_message': False,
            'current_queue_id': False
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'zid.sale.order.connector',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _update_progress(self, text):
        """Helper to update progress text"""
        self.write({'progress_text': self.progress_text + text + '\n'})
    
    def _prepare_order_values(self, order_data):
        """Prepare values for creating zid.sale.order from raw Zid order data"""
        self.ensure_one()
        
        customer = order_data.get('customer', {})
        order_status = order_data.get('order_status', {})
        shipping = order_data.get('shipping', {})
        shipping_method = shipping.get('method', {})
        payment = order_data.get('payment', {})
        payment_method = payment.get('method', {})
        
        # Note: Zid API returns 'order_total' in some endpoints and 'total' in others
        order_total = float(order_data.get('order_total') or order_data.get('total') or 0)
        
        return {
            'zid_connector_id': self.zid_connector_id.id,
            'zid_order_id': int(order_data.get('id', 0)),
            'order_code': order_data.get('code'),
            'store_id': int(order_data.get('store_id', 0)),
            'store_name': order_data.get('store_name'),
            'store_url': order_data.get('store_url'),
            'order_url': order_data.get('order_url'),
            
            # Status Info
            'order_status': order_status.get('code'),
            'order_status_name': order_status.get('name'),
            'payment_status': order_data.get('payment_status'),
            
            # Customer Info
            'customer_id': int(customer.get('id', 0)),
            'customer_name': customer.get('name'),
            'customer_email': customer.get('email'),
            'customer_mobile': customer.get('mobile'),
            'customer_note': customer.get('note'),
            'customer_note_field': customer.get('note'),
            'customer_verified': int(customer.get('verified', 0)),
            'customer_type': customer.get('type'),
            
            # Financial Info
            'currency_code': order_data.get('currency_code', 'SAR'),
            'order_total': order_total,
            'order_total_string': order_data.get('order_total_string'),
            'has_different_transaction_currency': bool(order_data.get('has_different_transaction_currency')),
            'transaction_reference': order_data.get('transaction_reference'),
            'transaction_amount': float(order_data.get('transaction_amount') or 0),
            'transaction_amount_string': order_data.get('transaction_amount_string'),
            
            # Payment Info
            'payment_method_name': payment_method.get('name'),
            'payment_method_code': payment_method.get('code'),
            'payment_method_type': payment_method.get('type'),
            'payment_link': payment.get('link'),
            
            # Shipping Info
            'shipping_method_code': shipping_method.get('code'),
            'requires_shipping': bool(order_data.get('requires_shipping')),
            'should_merchant_set_shipping_method': bool(order_data.get('should_merchant_set_shipping_method')),
            
            # Order Details & Flags
            'source': order_data.get('source'),
            'source_code': order_data.get('source_code'),
            'issue_date': order_data.get('issue_date'),
            'is_marketplace_order': bool(order_data.get('is_marketplace_order')),
            'is_guest_customer': bool(order_data.get('is_guest_customer')),
            'is_gift_order': bool(order_data.get('is_gift_order')),
            'is_quick_checkout_order': bool(order_data.get('is_quick_checkout_order')),
            'is_potential_fraud': bool(order_data.get('is_potential_fraud')),
            'is_reseller_transaction': bool(order_data.get('is_reseller_transaction')),
            'is_on_demand': bool(order_data.get('is_on_demand')),
            'cod_confirmed': bool(order_data.get('cod_confirmed')),
            
            # Dates
            'zid_created_at': order_data.get('created_at'),
            'zid_updated_at': order_data.get('updated_at'),
            
            # Raw data storage
            'raw_data': json.dumps(order_data, ensure_ascii=False),
        }

