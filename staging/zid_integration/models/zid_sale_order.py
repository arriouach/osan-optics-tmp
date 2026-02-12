from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging
import time
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class ZidSaleOrder(models.Model):
    _name = 'zid.sale.order'
    _description = 'Zid Sale Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'zid_order_id'
    _order = 'zid_created_at desc'

    # Connection
    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        ondelete='cascade'
    )

    # Order Basic Info
    zid_order_id = fields.Integer(
        string='Zid Order ID',
        required=True,
        readonly=True
    )
    zid_order_id_display = fields.Char(
        string='Zid Order ID',
        compute='_compute_zid_order_id_display',
        store=True,
        help='Zid Order ID formatted without commas'
    )
    order_code = fields.Char(
        string='Order Code',
        required=True,
        readonly=True,
        index=True
    )
    store_id = fields.Integer(
        string='Store ID',
        readonly=True
    )
    store_name = fields.Char(
        string='Store Name',
        readonly=True
    )
    store_url = fields.Char(
        string='Store URL',
        readonly=True
    )
    order_url = fields.Char(
        string='Order URL',
        readonly=True
    )

    # Order Status
    order_status = fields.Selection([
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
    ], string='Order Status', tracking=True)
    order_status_name = fields.Char(
        string='Status Name',
        readonly=True
    )
    
    # Product Mapping Validation
    has_unmapped_products = fields.Boolean(
        string='Has Unmapped Products',
        default=False,
        readonly=True,
        help='Indicates if this order contains products that are not mapped to Odoo'
    )
    
    unmapped_products_info = fields.Text(
        string='Unmapped Products Details',
        readonly=True,
        help='Details of products that could not be mapped'
    )
    
    mapping_validation_status = fields.Selection([
        ('pending', 'Pending Validation'),
        ('valid', 'All Products Mapped'),
        ('invalid', 'Has Unmapped Products'),
        ('retry', 'Ready for Retry')
    ], string='Mapping Status', default='pending', readonly=True)

    # Customer Info
    customer_id = fields.Integer(
        string='Customer ID',
        readonly=True
    )
    customer_name = fields.Char(
        string='Customer Name',
        readonly=True
    )
    customer_email = fields.Char(
        string='Customer Email',
        readonly=True
    )
    customer_mobile = fields.Char(
        string='Customer Mobile',
        readonly=True
    )
    customer_note_field = fields.Text(
        string='Customer Note',
        readonly=True
    )
    customer_verified = fields.Integer(
        string='Customer Verified',
        readonly=True
    )
    customer_type = fields.Char(
        string='Customer Type',
        readonly=True
    )

    # Financial Info
    currency_code = fields.Char(
        string='Currency Code',
        readonly=True
    )
    order_total = fields.Float(
        string='Order Total',
        readonly=True
    )
    order_total_string = fields.Char(
        string='Order Total String',
        readonly=True
    )
    has_different_transaction_currency = fields.Boolean(
        string='Different Transaction Currency',
        readonly=True
    )
    transaction_reference = fields.Char(
        string='Transaction Reference',
        readonly=True
    )
    transaction_amount = fields.Float(
        string='Transaction Amount',
        readonly=True
    )
    transaction_amount_string = fields.Char(
        string='Transaction Amount String',
        readonly=True
    )

    # Payment Info
    payment_status = fields.Selection([
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('refunded', 'Refunded'),
        ('voided', 'Voided')
    ], string='Payment Status', tracking=True)
    payment_method_name = fields.Char(
        string='Payment Method',
        readonly=True
    )
    payment_method_code = fields.Char(
        string='Payment Method Code',
        readonly=True
    )
    payment_method_type = fields.Char(
        string='Payment Type',
        readonly=True
    )
    payment_link = fields.Char(
        string='Payment Link',
        readonly=True
    )

    # Shipping Info
    shipping_method_code = fields.Char(
        string='Shipping Method Code',
        readonly=True
    )
    requires_shipping = fields.Boolean(
        string='Requires Shipping',
        readonly=True
    )
    should_merchant_set_shipping_method = fields.Boolean(
        string='Should Set Shipping Method',
        readonly=True
    )

    # Order Details
    is_marketplace_order = fields.Boolean(
        string='Marketplace Order',
        readonly=True
    )
    is_guest_customer = fields.Boolean(
        string='Guest Customer',
        readonly=True
    )
    is_gift_order = fields.Boolean(
        string='Gift Order',
        readonly=True
    )
    is_quick_checkout_order = fields.Boolean(
        string='Quick Checkout',
        readonly=True
    )
    is_potential_fraud = fields.Boolean(
        string='Potential Fraud',
        readonly=True
    )
    is_reseller_transaction = fields.Boolean(
        string='Reseller Transaction',
        readonly=True
    )
    is_on_demand = fields.Boolean(
        string='On Demand',
        readonly=True
    )
    is_reactivated = fields.Boolean(
        string='Reactivated',
        readonly=True
    )
    cod_confirmed = fields.Boolean(
        string='COD Confirmed',
        readonly=True
    )

    # Source Info
    source = fields.Char(
        string='Source',
        readonly=True
    )
    source_code = fields.Char(
        string='Source Code',
        readonly=True
    )

    # Additional Info
    issue_date = fields.Char(
        string='Issue Date',
        readonly=True
    )
    customer_note = fields.Text(
        string='Customer Note',
        readonly=True
    )
    gift_message = fields.Text(
        string='Gift Message',
        readonly=True
    )
    weight = fields.Float(
        string='Weight',
        readonly=True
    )
    coupon = fields.Char(
        string='Coupon',
        readonly=True
    )
    products_count = fields.Integer(
        string='Products Count',
        readonly=True
    )
    products_sum_total_string = fields.Char(
        string='Products Sum Total',
        readonly=True
    )
    language = fields.Char(
        string='Language',
        readonly=True
    )
    return_policy = fields.Text(
        string='Return Policy',
        readonly=True
    )
    packages_count = fields.Integer(
        string='Packages Count',
        readonly=True
    )
    inventory_address = fields.Char(
        string='Inventory Address',
        readonly=True
    )
    edits_count = fields.Integer(
        string='Edits Count',
        readonly=True
    )
    invoice_link = fields.Char(
        string='Invoice Link',
        readonly=True
    )

    # Dates
    zid_created_at = fields.Datetime(
        string='Created At (Zid)',
        readonly=True
    )
    zid_updated_at = fields.Datetime(
        string='Updated At (Zid)',
        readonly=True
    )
    delivered_at = fields.Datetime(
        string='Delivered At',
        readonly=True
    )
    last_sync_date = fields.Datetime(
        readonly=True
    )

    # Odoo Integration
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        readonly=True,
        ondelete='restrict'
    )
    order_line_ids = fields.One2many(
        related='sale_order_id.order_line',
        string='Order Lines',
        readonly=True
    )
    zid_product_lines = fields.Text(
        string='Zid Products',
        compute='_compute_zid_product_lines',
        readonly=True,
        help='Products from the original Zid order'
    )
    raw_data = fields.Text(
        string='Raw Data (JSON)',
        readonly=True
    )
    processed_data = fields.Text(
        string='Processed Data (JSON)',
        readonly=True
    )

    # Computed Fields
    display_name = fields.Char(
        compute='_compute_display_name',
        store=True
    )
    company_id = fields.Many2one(
        'res.company',
        related='zid_connector_id.company_id',
        store=True,
        readonly=True
    )

    @api.depends('zid_order_id')
    def _compute_zid_order_id_display(self):
        for record in self:
            record.zid_order_id_display = str(record.zid_order_id) if record.zid_order_id else ''

    @api.depends('zid_order_id', 'customer_name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.zid_order_id} - {record.customer_name or 'Guest'}"

    def sync_from_zid(self):
        """Sync order data from Zid"""
        self.ensure_one()
        if not self.zid_connector_id.is_connected:
            raise UserError(_('Zid connector is not connected'))

        try:
            endpoint = f"managers/store/orders/{self.zid_order_id}/view"
            response = self.zid_connector_id.api_request(
                endpoint=endpoint,
                method='GET'
            )

            if response and 'order' in response:
                order_data = response['order']
                wizard = self.env['zid.sale.order.connector']
                vals = wizard._prepare_order_values(order_data)
                vals['last_sync_date'] = fields.Datetime.now()
                self.write(vals)

                self.message_post(
                    body=_('Order synced from Zid at %s') % fields.Datetime.now()
                )

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Order synced successfully'),
                        'type': 'success',
                    }
                }
        except Exception as e:
            _logger.error(f"Failed to sync order: {str(e)}")
            raise UserError(_('Failed to sync order: %s') % str(e))

    def action_view_in_zid(self):
        """Open order in Zid"""
        self.ensure_one()
        if self.order_url:
            return {
                'type': 'ir.actions.act_url',
                'url': self.order_url,
                'target': 'new',
            }
        else:
            raise UserError(_('Order URL not available'))

    def create_sale_order(self):
        """Create Odoo sale order from Zid order"""
        self.ensure_one()
        if self.sale_order_id:
            raise UserError(_('Sale order already exists for this Zid order'))
        
        # Validate product mappings before creating sale order
        is_valid, message = self.validate_product_mappings()
        if not is_valid:
            _logger.warning(f"Cannot create sale order for Zid Order {self.zid_order_id}: {message}")
            raise UserError(f"Cannot create sale order: {message}\n\nPlease map the missing products first, then retry.")
        
        try:
            # Parse order data from raw_data JSON
            order_data = json.loads(self.raw_data) if isinstance(self.raw_data, str) else {}
            
            # If products are not in order_data, fetch full order details from Zid
            if not order_data.get('products'):
                _logger.info(f"Products not found in raw_data, fetching full order details for Zid Order {self.zid_order_id}")
                endpoint = f"managers/store/orders/{self.zid_order_id}/view"
                response = self.zid_connector_id.api_request(
                    endpoint=endpoint,
                    method='GET'
                )
                if response and 'order' in response:
                    order_data = response['order']
                    # Update raw_data with full order details
                    self.raw_data = json.dumps(order_data, ensure_ascii=False)
                else:
                    raise UserError(_('Failed to fetch full order details from Zid'))
            
            # 1. Find or create customer
            partner = self._find_or_create_customer(order_data)
            
            # 2. Create sale order header
            order_vals = {
                'partner_id': partner.id,
                'partner_invoice_id': partner.id,
                'partner_shipping_id': partner.id,
                'date_order': self.zid_created_at or fields.Datetime.now(),
                'client_order_ref': str(self.zid_order_id),
                'note': self.customer_note or '',
                'company_id': self.zid_connector_id.company_id.id,
                'zid_order_ref': str(self.zid_order_id),
                'zid_order_id': self.id,
            }
            
            # Add salesperson and sales team if configured
            if self.zid_connector_id.default_user_id:
                order_vals['user_id'] = self.zid_connector_id.default_user_id.id
            
            if self.zid_connector_id.default_team_id:
                order_vals['team_id'] = self.zid_connector_id.default_team_id.id
            
            sale_order = self.env['sale.order'].create(order_vals)
            _logger.info(f"Created sale order {sale_order.name} for Zid order {self.zid_order_id}")
            
            # 3. Create order lines from products
            self._create_order_lines(sale_order, order_data)
            
            # 4. Create shipping line if applicable
            self._create_shipping_line(sale_order, order_data)
            
            # 5. Link Zid order to Odoo sale order
            self.sale_order_id = sale_order.id
            
            # 6. Apply automation based on connector settings
            self._apply_order_automation(sale_order)
            
            return {
                'name': _('Sale Order'),
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'res_id': sale_order.id,
                'view_mode': 'form',
                'views': [(False, 'form')],
                'target': 'current',
            }
            
        except Exception as e:
            _logger.error(f"Failed to create sale order for Zid order {self.zid_order_id}: {str(e)}")
            raise UserError(_('Failed to create sale order: %s') % str(e))

    def _apply_order_automation(self, sale_order):
        """Apply automation settings from connector configuration"""
        connector = self.zid_connector_id
        
        # Step 1: Auto-confirm order
        if connector.auto_confirm_orders and sale_order.state == 'draft':
            try:
                with self.env.cr.savepoint():
                    sale_order.action_confirm()
                    _logger.info(f"Auto-confirmed sale order {sale_order.name}")
            except Exception as e:
                _logger.error(f"Failed to auto-confirm order {sale_order.name}: {str(e)}")
                # If confirmation fails, we shouldn't attempt invoicing/delivery
                return
        
        # Step 2: Auto-create invoice (only if order is confirmed)
        if connector.auto_create_invoice and sale_order.state == 'sale':
            try:
                with self.env.cr.savepoint():
                    # Use standard Odoo method to create invoices
                    # This handles tax calculation and balancing correctly
                    invoices = sale_order._create_invoices()
                    if invoices:
                        _logger.info(f"Auto-created invoice(s) for order {sale_order.name}")
                        
                        # Step 3: Auto-confirm invoice
                        if connector.auto_confirm_invoice:
                            for invoice in invoices:
                                if invoice.state == 'draft':
                                    invoice.action_post()
                                    _logger.info(f"Auto-confirmed invoice {invoice.name}")
                        
            except Exception as e:
                _logger.error(f"Failed to auto-create/confirm invoice for order {sale_order.name}: {str(e)}")
        
        # Step 4: Auto-validate delivery (only if order is confirmed)
        if connector.auto_validate_delivery and sale_order.state == 'sale':
            try:
                with self.env.cr.savepoint():
                    # Find delivery orders (pickings)
                    pickings = sale_order.picking_ids.filtered(lambda p: p.state in ['assigned', 'confirmed', 'waiting'])
                    
                    for picking in pickings:
                        # Check if all products are available
                        if picking.state == 'assigned' or self._force_assign_picking(picking):
                            # Set quantities done
                            for move in picking.move_ids:
                                # Odoo 17+ uses 'quantity' on move to set done quantity
                                move.quantity = move.product_uom_qty
                            
                            # Validate the picking
                            picking.button_validate()
                            _logger.info(f"Auto-validated delivery {picking.name} for order {sale_order.name}")
                        else:
                            _logger.warning(f"Cannot auto-validate delivery {picking.name} - insufficient stock")
                        
            except Exception as e:
                _logger.error(f"Failed to auto-validate delivery for order {sale_order.name}: {str(e)}")
        
        # Step 5: Auto-register payment (if Zid order is paid and invoice exists)
        if connector.auto_register_payment:
            self._auto_register_payment(sale_order)
    
    def _force_assign_picking(self, picking):
        """Try to force assign picking if possible"""
        try:
            picking.action_assign()
            return picking.state == 'assigned'
        except Exception as e:
            _logger.warning(f"Could not force assign picking {picking.name}: {str(e)}")
            return False
    
    def _auto_register_payment(self, sale_order):
        """Auto-register payment based on Zid order payment status"""
        try:
            # Only process if Zid order is marked as paid
            if self.payment_status != 'paid':
                _logger.info(f"Zid order {self.zid_order_id} payment status is '{self.payment_status}', skipping payment registration")
                return
            
            # Find posted invoices for this order
            invoices = sale_order.invoice_ids.filtered(lambda inv: inv.state == 'posted' and inv.move_type == 'out_invoice')
            
            if not invoices:
                _logger.warning(f"No posted invoices found for order {sale_order.name}, cannot register payment")
                return
            
            # Get payment journal from mapping or default
            payment_journal = self._get_payment_journal()
            
            if not payment_journal:
                _logger.error(f"No payment journal configured for payment method '{self.payment_method_code}'")
                return
            
            # Register payment for each invoice
            for invoice in invoices:
                # Check if payment already exists
                # Use 'memo' (Odoo 17+) or 'communication' (Older) safely
                payment_ref_field = 'memo' if hasattr(self.env['account.payment'], 'memo') else 'communication'
                
                existing_payments = self.env['account.payment'].search([
                    (payment_ref_field, 'like', f'Zid Order {self.zid_order_id}'),
                    ('partner_id', '=', invoice.partner_id.id),
                    ('amount', '=', invoice.amount_total)
                ])
                
                if existing_payments:
                    _logger.info(f"Payment already exists for invoice {invoice.name}")
                    continue
                
                # Create payment
                payment_vals = {
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'partner_id': invoice.partner_id.id,
                    'amount': invoice.amount_total,
                    'currency_id': invoice.currency_id.id,
                    'journal_id': payment_journal.id,
                    'date': self.zid_created_at or fields.Date.today(),
                    payment_ref_field: f'Zid Order {self.zid_order_id} - {self.payment_method_name}',
                    'reconciled_invoice_ids': [(6, 0, [invoice.id])],
                }
                
                payment = self.env['account.payment'].create(payment_vals)
                payment.action_post()
                
                _logger.info(f"Auto-registered payment {payment.name} for invoice {invoice.name}")
                
                # Auto-reconcile if enabled
                if self.zid_connector_id.auto_reconcile_payment:
                    self._auto_reconcile_payment(payment, invoice)
                    
        except Exception as e:
            _logger.error(f"Failed to auto-register payment for order {sale_order.name}: {str(e)}")
    
    def _get_payment_journal(self):
        """Get payment journal based on Zid payment method mapping"""
        # First try to find specific mapping
        mapping = self.env['zid.payment.mapping'].search([
            ('zid_connector_id', '=', self.zid_connector_id.id),
            ('payment_method_code', '=', self.payment_method_code)
        ], limit=1)
        
        if mapping:
            return mapping.payment_journal_id
        
        # Fallback to default journal
        return self.zid_connector_id.default_payment_journal_id
    
    def _auto_reconcile_payment(self, payment, invoice):
        """Auto-reconcile payment with invoice"""
        try:
            # Find matching move lines to reconcile
            # Odoo 17+ compatibility: payment lines are on payment.move_id.line_ids
            payment_lines = getattr(payment, 'line_ids', self.env['account.move.line'])
            if not payment_lines and hasattr(payment, 'move_id'):
                payment_lines = payment.move_id.line_ids
                
            payment_line = payment_lines.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
            invoice_line = invoice.line_ids.filtered(lambda l: l.account_id.account_type == 'asset_receivable')
            
            if payment_line and invoice_line:
                (payment_line + invoice_line).reconcile()
                _logger.info(f"Auto-reconciled payment {payment.name} with invoice {invoice.name}")
            else:
                _logger.warning(f"Could not find matching lines to reconcile payment {payment.name} with invoice {invoice.name}")
                
        except Exception as e:
            _logger.error(f"Failed to auto-reconcile payment {payment.name}: {str(e)}")

    def action_update_status(self):
        """Open wizard to update order status"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'zid.order.status.updater',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_zid_order_id': self.id,
                'default_current_status': self.order_status
            }
        }

    def action_add_note(self):
        """Open wizard to add note"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'zid.order.note.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_zid_order_id': self.id}
        }

    @api.model
    def cron_sync_orders_simple(self):
        """Simple cron job to sync orders from Zid (legacy method)"""
        connectors = self.env['zid.connector'].search([
            ('authorization_status', '=', 'connected'),
            ('active', '=', True)
        ])

        for connector in connectors:
            try:
                wizard = self.env['zid.sale.order.connector'].create({
                    'zid_connector_id': connector.id,
                    'import_mode': 'all'
                })
                wizard.action_import_orders()
                _logger.info(f"Successfully synced orders for connector: {connector.app_name}")
            except Exception as e:
                _logger.error(f"Failed to sync orders for {connector.app_name}: {str(e)}")

    def get_credit_notes(self):
        """Fetch credit notes for this order"""
        self.ensure_one()
        if not self.zid_connector_id.is_connected:
            raise UserError(_('Zid connector is not connected'))

        try:
            endpoint = f"managers/store/orders/{self.zid_order_id}/credit-notes"
            response = self.zid_connector_id.api_request(
                endpoint=endpoint,
                method='GET'
            )

            if response:
                # Display credit notes (could be saved to a separate model)
                message = json.dumps(response, indent=2)
                raise UserError(_('Credit Notes:\n%s') % message)
        except Exception as e:
            _logger.error(f"Failed to fetch credit notes: {str(e)}")
            raise UserError(_('Failed to fetch credit notes: %s') % str(e))

    @api.model
    def _get_order_status_sequence(self):
        """Get order status sequence for validation"""
        return {
            'new': 0,
            'preparing': 1,
            'ready': 2,
            'indelivery': 3,
            'delivered': 4,
            'cancelled': 5,
            'reversed': 6,
            'refunded': 7,
            'reverse_in_progress': 8,
            'ready_for_reverse': 9,
            'partially_reversed': 10
        }

    def _check_status_transition(self, new_status):
        """Check if status transition is valid"""
        if not self.order_status:
            return True

        sequence = self._get_order_status_sequence()
        current_seq = sequence.get(self.order_status, 0)
        new_seq = sequence.get(new_status, 0)

        # Can always cancel
        if new_status == 'cancelled':
            return True

        # Can't go from cancelled to anything
        if self.order_status == 'cancelled':
            return False

        # Can't go backwards except to cancel
        return new_seq >= current_seq

    def _find_or_create_customer(self, order_data):
        """Find existing customer or create new one based on connector configuration"""
        partner_obj = self.env['res.partner']
        partner = False
        mode = self.zid_connector_id.customer_match_by
        
        # Always create new customer
        if mode == 'always_create':
            partner = False
        
        # Find by email
        elif mode in ['email', 'both']:
            if self.customer_email:
                partner = partner_obj.search([
                    ('email', '=', self.customer_email),
                    '|', ('company_id', '=', False), 
                    ('company_id', '=', self.zid_connector_id.company_id.id)
                ], limit=1)
        
        # Find by mobile
        if not partner and mode in ['mobile', 'both']:
            if self.customer_mobile:
                partner = partner_obj.search([
                    ('mobile', '=', self.customer_mobile),
                    '|', ('company_id', '=', False),
                    ('company_id', '=', self.zid_connector_id.company_id.id)
                ], limit=1)
        
        # Create new customer if not found
        if not partner:
            partner_vals = {
                'name': self.customer_name or 'Guest Customer',
                'email': self.customer_email or False,
                'mobile': self.customer_mobile or False,
                'phone': self.customer_mobile or False,
                'customer_rank': 1,
                'company_id': self.zid_connector_id.company_id.id,
            }
            partner = partner_obj.create(partner_vals)
            _logger.info(f"Created new customer: {partner.name} (mode: {mode})")
        else:
            _logger.info(f"Found existing customer: {partner.name}")
        
        return partner
    
    def _create_order_lines(self, sale_order, order_data):
        """Create sale order lines from Zid order products based on connector configuration"""
        products_data = order_data.get('products', [])
        
        if not products_data:
            raise UserError(_('No products found in Zid order data'))
        
        for product_data in products_data:
            # Use the enhanced product matching logic
            odoo_product = self._find_mapped_product(product_data)
            
            if not odoo_product:
                product_name = product_data.get('name', {})
                if isinstance(product_name, dict):
                    product_name = product_name.get('en') or product_name.get('ar', '')
                raise UserError(_(f'Could not find mapped product for: {product_name} (ID: {product_data.get("id")})'))
            
            # Get quantity and price
            quantity = float(product_data.get('quantity', 1))
            price = float(product_data.get('price', 0))
            
            # Create sale order line
            line_vals = {
                'order_id': sale_order.id,
                'product_id': odoo_product.id,
                'name': product_data.get('name', odoo_product.name),
                'product_uom_qty': quantity,
                'price_unit': price,
                'tax_id': [(6, 0, odoo_product.taxes_id.ids)] if odoo_product.taxes_id else False,
            }
            
            self.env['sale.order.line'].create(line_vals)
            _logger.info(f"Created order line: {odoo_product.name} x {quantity}")
    
    def _create_shipping_line(self, sale_order, order_data):
        """Create shipping line based on order data"""
        shipping_data = order_data.get('shipping', {}) or {}
        shipping_cost = float(shipping_data.get('cost', 0) or order_data.get('shipping_cost', 0))
        
        if shipping_cost <= 0:
            return
        
        # Get shipping product from connector configuration
        shipping_product = self.zid_connector_id.default_shipping_product_id
        
        if not shipping_product:
            # Fallback to default product search
            shipping_product = self.env['product.product'].search([
                ('default_code', '=', 'ZID_SHIPPING')
            ], limit=1) or self.env['product.product'].search([
                ('name', '=', 'Shipping Cost (Zid)'),
                ('type', '=', 'service')
            ], limit=1)
            
            if not shipping_product:
                shipping_product = self.env['product.product'].create({
                    'name': 'Shipping Cost (Zid)',
                    'default_code': 'ZID_SHIPPING',
                    'type': 'service',
                    'list_price': 0,
                    'sale_ok': True,
                    'purchase_ok': False,
                    'company_id': self.zid_connector_id.company_id.id,
                })
        
        # Create shipping line
        line_vals = {
            'order_id': sale_order.id,
            'product_id': shipping_product.id,
            'name': f"Shipping - {shipping_data.get('method', {}).get('name', 'Standard')}" if shipping_data.get('method') else 'Shipping',
            'product_uom_qty': 1,
            'price_unit': shipping_cost,
        }
        
        self.env['sale.order.line'].create(line_vals)
        _logger.info(f"Created shipping line for order {sale_order.name}: {shipping_cost}")

    @api.model
    def cron_sync_orders(self):
        """Cron job to sync orders from Zid via proxy with auto-recovery"""
        _logger.info("Starting Zid order sync cron...")
        
        # First, check and reset any expired locks
        self.env['zid.connector'].cron_check_expired_locks()
        
        # Get all connectors for diagnostic logging
        all_connectors = self.env['zid.connector'].search([])
        _logger.info(f"Total Zid connectors found: {len(all_connectors)}")
        
        for conn in all_connectors:
            _logger.info(f"Connector '{conn.app_name}' (ID: {conn.id}): "
                        f"status='{conn.authorization_status}', "
                        f"active={conn.active}, "
                        f"import_in_progress={conn.order_import_in_progress}")

        # Get all connected connectors that are not busy
        connectors = self.env['zid.connector'].search([
            ('authorization_status', '=', 'connected'),
            ('active', '=', True),
            ('order_import_in_progress', '=', False)  # Only process if not already running
        ])
        
        if not connectors:
            _logger.info("No active Zid connectors found or all are busy.")
            return
            
        for connector in connectors:
            try:
                # Set lock with timestamp using new method
                connector._set_import_lock('order')
                
                _logger.info(f"Syncing orders for connector: {connector.app_name}")
                
                # Determine the start date for import
                if connector.last_order_import_date:
                    start_date = connector.last_order_import_date
                    _logger.info(f"Using incremental sync from last import: {start_date}")
                elif connector.order_import_start_date:
                    start_date = connector.order_import_start_date
                    _logger.info(f"Using configured start date for first import: {start_date}")
                else:
                    start_date = fields.Datetime.now() - timedelta(days=7)
                    _logger.info(f"Using fallback start date (7 days ago): {start_date}")
                
                # Create wizard and trigger import
                wizard = self.env['zid.sale.order.connector'].create({
                    'zid_connector_id': connector.id,
                    'import_mode': 'new',
                    'order_status': 'all',
                    'payment_status': 'all',
                    'date_from': start_date
                })
                
                # This calls proxy instead of Zid directly!
                wizard.action_start_import()
                
                # Update ONLY the last import date
                connector.write({'last_order_import_date': fields.Datetime.now()})
                
                _logger.info(f"Successfully synced orders for connector: {connector.app_name}")
                
            except Exception as e:
                _logger.error(f"Error syncing orders for connector {connector.app_name}: {str(e)}")
            finally:
                # Always release the lock using new method
                connector._release_import_lock('order')

    def validate_product_mappings(self):
        """Validate that all products in the order can be mapped to Odoo products"""
        self.ensure_one()
        
        if not self.raw_data:
            return False, "No order data available"
        
        try:
            order_data = json.loads(self.raw_data)
            products = order_data.get('products', [])
            
            if not products:
                return True, "No products in order"
            
            unmapped_products = []
            product_model = self.env['product.product']
            
            for product_data in products:
                product_id = str(product_data.get('id', ''))
                sku = product_data.get('sku', '')
                barcode = product_data.get('barcode', '')
                name = product_data.get('name', {})
                
                if isinstance(name, dict):
                    product_name = name.get('en', '') or name.get('ar', '')
                else:
                    product_name = str(name) if name else ''
                
                # Try to find mapped Odoo product using the existing matching logic
                odoo_product = self._find_mapped_product(product_data)
                
                if not odoo_product:
                    unmapped_products.append({
                        'zid_id': product_id,
                        'sku': sku,
                        'barcode': barcode,
                        'name': product_name,
                        'quantity': product_data.get('quantity', 0)
                    })
            
            if unmapped_products:
                # Update order with unmapped product info
                unmapped_info = "Unmapped Products:\n"
                for prod in unmapped_products:
                    unmapped_info += f"- ID: {prod['zid_id']}, SKU: {prod['sku']}, Name: {prod['name']}\n"
                
                self.write({
                    'has_unmapped_products': True,
                    'unmapped_products_info': unmapped_info,
                    'mapping_validation_status': 'invalid'
                })
                
                return False, f"Found {len(unmapped_products)} unmapped products"
            else:
                self.write({
                    'has_unmapped_products': False,
                    'unmapped_products_info': '',
                    'mapping_validation_status': 'valid'
                })
                return True, "All products are mapped"
                
        except Exception as e:
            _logger.error(f"Error validating product mappings for order {self.zid_order_id}: {str(e)}")
            return False, f"Validation error: {str(e)}"

    def _find_mapped_product(self, product_data):
        """Find mapped Odoo product using the connector's matching strategy"""
        if not self.zid_connector_id:
            return False
            
        product_id = str(product_data.get('id', ''))
        sku = product_data.get('sku', '')
        barcode = product_data.get('barcode', '')
        
        product_model = self.env['product.product']
        
        # Use the connector's product matching priority
        match_priority = self.zid_connector_id.product_match_priority or 'mapping_first'
        
        if match_priority == 'mapping_first':
            # 1. Try Zid Variant mapping first
            zid_variant = self.env['zid.variant'].search([
                ('zid_variant_id', '=', product_id),
                ('zid_connector_id', '=', self.zid_connector_id.id),
                ('odoo_product_id', '!=', False)
            ], limit=1)
            
            if zid_variant and zid_variant.odoo_product_id:
                return zid_variant.odoo_product_id
            
            # 2. Try Zid Product mapping
            zid_product = self.env['zid.product'].search([
                ('zid_product_id', '=', product_id),
                ('zid_connector_id', '=', self.zid_connector_id.id),
                ('odoo_product_id', '!=', False)
            ], limit=1)
            
            if zid_product and zid_product.odoo_product_id:
                return zid_product.odoo_product_id
            
            # 3. Try direct SKU/Barcode matching
            if sku:
                odoo_product = product_model.search([('default_code', '=', sku)], limit=1)
                if odoo_product:
                    return odoo_product
            
            if barcode:
                odoo_product = product_model.search([('barcode', '=', barcode)], limit=1)
                if odoo_product:
                    return odoo_product
                    
        elif match_priority == 'direct_only':
            # Only direct SKU/Barcode matching
            if sku:
                odoo_product = product_model.search([('default_code', '=', sku)], limit=1)
                if odoo_product:
                    return odoo_product
            
            if barcode:
                odoo_product = product_model.search([('barcode', '=', barcode)], limit=1)
                if odoo_product:
                    return odoo_product
                    
        elif match_priority == 'mapping_only':
            # Only Zid mapping (no direct matching)
            zid_variant = self.env['zid.variant'].search([
                ('zid_variant_id', '=', product_id),
                ('zid_connector_id', '=', self.zid_connector_id.id),
                ('odoo_product_id', '!=', False)
            ], limit=1)
            
            if zid_variant and zid_variant.odoo_product_id:
                return zid_variant.odoo_product_id
            
            zid_product = self.env['zid.product'].search([
                ('zid_product_id', '=', product_id),
                ('zid_connector_id', '=', self.zid_connector_id.id),
                ('odoo_product_id', '!=', False)
            ], limit=1)
            
            if zid_product and zid_product.odoo_product_id:
                return zid_product.odoo_product_id
        
        return False

    def action_retry_create_sale_order(self):
        """Retry creating sale order after product mapping is resolved"""
        self.ensure_one()
        
        # First validate product mappings
        is_valid, message = self.validate_product_mappings()
        
        if not is_valid:
            raise UserError(f"Cannot create sale order: {message}")
        
        # If validation passes, try to create the sale order
        try:
            self.create_sale_order()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'Sale order created successfully!',
                    'type': 'success',
                }
            }
        except Exception as e:
            raise UserError(f"Failed to create sale order: {str(e)}")

    @api.depends('raw_data')
    def _compute_zid_product_lines(self):
        """Compute Zid product lines from raw order data"""
        for record in self:
            if not record.raw_data:
                record.zid_product_lines = "No product data available"
                continue
                
            try:
                order_data = json.loads(record.raw_data) if isinstance(record.raw_data, str) else record.raw_data
                products = order_data.get('products', [])
                
                if not products:
                    record.zid_product_lines = "No products found in order data"
                    continue
                
                # Format products for display
                lines = []
                for i, product in enumerate(products, 1):
                    product_id = product.get('id', 'N/A')
                    name = product.get('name', 'N/A')
                    sku = product.get('sku', 'N/A')
                    barcode = product.get('barcode', 'N/A')
                    quantity = product.get('quantity', 'N/A')
                    price = product.get('price', 'N/A')
                    
                    # Handle name if it's a dict (multilingual)
                    if isinstance(name, dict):
                        name = name.get('en') or name.get('ar') or str(name)
                    
                    line = f"{i}. {name}\n"
                    line += f"   • ID: {product_id}\n"
                    line += f"   • SKU: {sku}\n"
                    line += f"   • Barcode: {barcode}\n"
                    line += f"   • Quantity: {quantity}\n"
                    line += f"   • Price: {price}\n"
                    
                    lines.append(line)
                
                record.zid_product_lines = "\n".join(lines)
                
            except Exception as e:
                record.zid_product_lines = f"Error parsing product data: {str(e)}"
    def fetch_full_order_details(self):
        """Manually fetch full order details from Zid API and update raw_data"""
        self.ensure_one()
        
        try:
            _logger.info(f"Manually fetching full order details for Zid Order {self.zid_order_id}")
            endpoint = f"managers/store/orders/{self.zid_order_id}/view"
            
            response = self.zid_connector_id.api_request(
                endpoint=endpoint,
                method='GET'
            )
            
            if response and 'order' in response:
                full_order_data = response['order']
                
                # Update raw_data with full order details
                self.raw_data = json.dumps(full_order_data, ensure_ascii=False)
                
                # Check if products are now available
                products = full_order_data.get('products', [])
                
                self.message_post(
                    body=f"Full order details fetched successfully. Found {len(products)} products."
                )
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': f'Full order details fetched. Found {len(products)} products. Check the "Zid Products" tab.',
                        'type': 'success',
                        'sticky': True,
                    }
                }
            else:
                error_msg = f"Failed to fetch full order details. API Response: {response}"
                _logger.error(error_msg)
                
                self.message_post(body=f"Failed to fetch full order details: {error_msg}")
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': 'Failed to fetch full order details from Zid API.',
                        'type': 'danger',
                    }
                }
                
        except Exception as e:
            error_msg = f"Error fetching full order details: {str(e)}"
            _logger.error(error_msg)
            
            self.message_post(body=error_msg)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Error: {str(e)}',
                    'type': 'danger',
                }
            }
    @api.model
    def cron_sync_order_status(self):
        """Cron job to sync order status from Zid for recent orders with auto-recovery"""
        _logger.info("Starting Zid order status sync cron...")
        
        # First, check and reset any expired locks
        self.env['zid.connector'].cron_check_expired_locks()
        
        # Get all connectors for diagnostic logging
        all_connectors = self.env['zid.connector'].search([])
        for conn in all_connectors:
            _logger.info(f"Status Sync Diagnostic - Connector '{conn.app_name}': "
                        f"status='{conn.authorization_status}', "
                        f"active={conn.active}, "
                        f"auto_sync={conn.auto_sync_order_status}, "
                        f"status_sync_in_progress={conn.order_status_sync_in_progress}, "
                        f"order_import_in_progress={conn.order_import_in_progress}")

        # Get all active connectors with status sync enabled that are not busy
        connectors = self.env['zid.connector'].search([
            ('authorization_status', '=', 'connected'),
            ('active', '=', True),
            ('auto_sync_order_status', '=', True),
            ('order_status_sync_in_progress', '=', False),  # Only process if not already running
            ('order_import_in_progress', '=', False)  # Don't run if order import is running
        ])
        
        if not connectors:
            _logger.info("No active connectors available for status sync (all busy or disabled).")
            return
        
        total_checked = 0
        total_updated = 0
        
        for connector in connectors:
            try:
                # Set lock with timestamp using new method
                connector._set_import_lock('status')
                connector.write({'last_status_sync_date': fields.Datetime.now()})
                
                _logger.info(f"Syncing order status for connector: {connector.app_name}")
                
                # Calculate date range based on connector settings
                days_back = connector.status_sync_days_back or 7
                cutoff_date = fields.Datetime.now() - timedelta(days=days_back)
                
                # Get orders that might need status updates
                domain = [('zid_connector_id', '=', connector.id)]
                
                if connector.sync_all_pending_orders:
                    # Include ALL non-final orders regardless of age
                    domain.append(('order_status', 'not in', ['delivered', 'cancelled', 'returned']))
                    _logger.info(f"Checking ALL pending orders for connector {connector.app_name}")
                else:
                    # Use hybrid approach: recent updates OR non-final orders
                    domain.extend([
                        '|',
                        # Recently updated orders in Zid
                        ('zid_updated_at', '>=', cutoff_date),
                        # OR orders that are not in final status (regardless of age)
                        ('order_status', 'not in', ['delivered', 'cancelled', 'returned'])
                    ])
                    _logger.info(f"Checking recent + pending orders for connector {connector.app_name}")
                
                orders_to_check = self.search(domain)
                
                _logger.info(f"Found {len(orders_to_check)} orders to check for status updates")
                
                checked, updated = self._batch_sync_order_status(orders_to_check)
                total_checked += checked
                total_updated += updated
                
                _logger.info(f"Connector {connector.app_name}: Checked {checked} orders, updated {updated}")
                
            except Exception as e:
                _logger.error(f"Error syncing order status for connector {connector.app_name}: {str(e)}")
            finally:
                # Always release the lock using new method
                connector._release_import_lock('status')
        
        _logger.info(f"Order status sync completed. Total checked: {total_checked}, Total updated: {total_updated}")
    
    def _batch_sync_order_status(self, orders):
        """Batch sync order status for multiple orders"""
        if not orders:
            return 0, 0
        
        connector = orders[0].zid_connector_id
        checked_count = 0
        updated_count = 0
        
        # Process orders in batches to avoid API rate limits
        batch_size = 20
        for i in range(0, len(orders), batch_size):
            batch = orders[i:i + batch_size]
            
            try:
                # Get order IDs for batch API call
                order_ids = [str(order.zid_order_id) for order in batch]
                
                # Batch API call to get current status
                current_statuses = self._get_orders_status_batch(connector, order_ids)
                
                # Update orders that have status changes
                for order in batch:
                    checked_count += 1
                    order_id_str = str(order.zid_order_id)
                    
                    if order_id_str in current_statuses:
                        current_status = current_statuses[order_id_str]
                        
                        if current_status != order.order_status:
                            _logger.info(f"Order {order.zid_order_id}: Status changed from '{order.order_status}' to '{current_status}'")
                            
                            # Update Zid order status
                            order.order_status = current_status
                            
                            # Update related Odoo sale order if exists
                            if order.sale_order_id:
                                self._update_sale_order_status(order.sale_order_id, current_status)
                            
                            # Log the change
                            order.message_post(
                                body=f"Order status automatically updated from '{order.order_status}' to '{current_status}' via cron sync"
                            )
                            
                            updated_count += 1
                
                # Small delay between batches to respect API limits
                if i + batch_size < len(orders):
                    time.sleep(1)
                    
            except Exception as e:
                _logger.error(f"Error processing batch {i//batch_size + 1}: {str(e)}")
        
        return checked_count, updated_count
    
    def _get_orders_status_batch(self, connector, order_ids):
        """Get current status for multiple orders from Zid API"""
        statuses = {}
        
        # For now, we'll call individual order endpoints
        # In the future, this could be optimized with a batch API if Zid provides one
        for order_id in order_ids:
            try:
                endpoint = f"managers/store/orders/{order_id}/view"
                response = connector.api_request(endpoint=endpoint, method='GET')
                
                if response and 'order' in response:
                    order_data = response['order']
                    status_info = order_data.get('order_status', {})
                    
                    if isinstance(status_info, dict):
                        current_status = status_info.get('code', 'unknown')
                    else:
                        current_status = str(status_info)
                    
                    statuses[order_id] = current_status
                
                # Small delay between API calls
                time.sleep(0.2)
                
            except Exception as e:
                _logger.warning(f"Failed to get status for order {order_id}: {str(e)}")
        
        return statuses
    
    def _update_sale_order_status(self, sale_order, zid_status):
        """Update Odoo sale order based on Zid status"""
        try:
            # Status mapping from Zid to Odoo actions
            status_actions = {
                'new': None,  # Keep as is
                'preparing': 'confirm',  # Confirm order
                'ready': 'confirm',  # Confirm order
                'shipped': 'done',  # Mark as done
                'delivered': 'done',  # Mark as done
                'cancelled': 'cancel',  # Cancel order
                'returned': 'cancel',  # Cancel order (or handle returns separately)
                'partially_returned': None,  # Keep as is, handle returns separately
            }
            
            action = status_actions.get(zid_status)
            
            if action == 'confirm' and sale_order.state == 'draft':
                sale_order.action_confirm()
                _logger.info(f"Confirmed sale order {sale_order.name} due to Zid status '{zid_status}'")
                
            elif action == 'done' and sale_order.state in ['draft', 'sent']:
                # First confirm, then mark as done
                if sale_order.state == 'draft':
                    sale_order.action_confirm()
                
                # Auto-validate delivery if configured
                connector = self.zid_connector_id
                if connector.auto_validate_delivery:
                    self._auto_validate_delivery_for_status_sync(sale_order)
                
                _logger.info(f"Processed sale order {sale_order.name} for Zid status '{zid_status}'")
                
            elif action == 'cancel' and sale_order.state not in ['cancel', 'done']:
                sale_order.action_cancel()
                _logger.info(f"Cancelled sale order {sale_order.name} due to Zid status '{zid_status}'")
        
        except Exception as e:
            _logger.error(f"Failed to update sale order {sale_order.name} for status '{zid_status}': {str(e)}")
    
    def _auto_validate_delivery_for_status_sync(self, sale_order):
        """Auto-validate delivery when order status changes to shipped/delivered"""
        try:
            pickings = sale_order.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel'])
            
            for picking in pickings:
                if picking.state == 'assigned' or self._force_assign_picking(picking):
                    # Set quantities done
                    for move in picking.move_ids:
                        for move_line in move.move_line_ids:
                            move_line.quantity = move_line.reserved_quantity
                    
                    # Validate the picking
                    picking.button_validate()
                    _logger.info(f"Auto-validated delivery {picking.name} due to status sync")
                else:
                    _logger.warning(f"Cannot auto-validate delivery {picking.name} - insufficient stock")
        
        except Exception as e:
            _logger.error(f"Failed to auto-validate delivery for order {sale_order.name}: {str(e)}")
    
    def sync_status_during_import(self, connector):
        """Sync order status for recent orders during import process"""
        if not connector.sync_order_status_on_import:
            return
        
        try:
            _logger.info("Syncing order status during import...")
            
            # Get orders imported in the last 48 hours
            cutoff_date = fields.Datetime.now() - timedelta(hours=48)
            
            recent_orders = self.search([
                ('zid_connector_id', '=', connector.id),
                ('create_date', '>=', cutoff_date),
                ('order_status', 'not in', ['delivered', 'cancelled', 'returned'])
            ])
            
            if recent_orders:
                checked, updated = self._batch_sync_order_status(recent_orders)
                _logger.info(f"Import-time status sync: Checked {checked} orders, updated {updated}")
        
        except Exception as e:
            _logger.error(f"Error during import-time status sync: {str(e)}")
    def action_sync_status_from_zid(self):
        """Manual action to sync status for selected orders"""
        for order in self:
            try:
                _logger.info(f"Manually syncing status for order {order.zid_order_id}")
                
                # Get current status from Zid
                endpoint = f"managers/store/orders/{order.zid_order_id}/view"
                response = order.zid_connector_id.api_request(endpoint=endpoint, method='GET')
                
                if response and 'order' in response:
                    order_data = response['order']
                    status_info = order_data.get('order_status', {})
                    
                    if isinstance(status_info, dict):
                        current_status = status_info.get('code', 'unknown')
                    else:
                        current_status = str(status_info)
                    
                    if current_status != order.order_status:
                        old_status = order.order_status
                        order.order_status = current_status
                        
                        # Update related Odoo sale order if exists
                        if order.sale_order_id:
                            order._update_sale_order_status(order.sale_order_id, current_status)
                        
                        # Log the change
                        order.message_post(
                            body=f"Order status manually synced from '{old_status}' to '{current_status}'"
                        )
                        
                        _logger.info(f"Order {order.zid_order_id}: Status updated from '{old_status}' to '{current_status}'")
                    else:
                        order.message_post(body="Status sync: No changes detected")
                        _logger.info(f"Order {order.zid_order_id}: Status unchanged ({current_status})")
                else:
                    raise UserError(_('Failed to fetch order details from Zid API'))
                    
            except Exception as e:
                error_msg = f"Failed to sync status: {str(e)}"
                order.message_post(body=error_msg)
                _logger.error(f"Manual status sync failed for order {order.zid_order_id}: {str(e)}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Status Sync Complete',
                'message': f'Status sync completed for {len(self)} order(s). Check individual order logs for details.',
                'type': 'success',
                'sticky': True,
            }
        }
    
    @api.model
    def action_bulk_sync_all_pending(self):
        """Action to sync all pending orders across all connectors (admin use)"""
        _logger.info("Starting bulk sync of all pending orders...")
        
        # Get all active connectors
        connectors = self.env['zid.connector'].search([
            ('authorization_status', '=', 'connected'),
            ('active', '=', True)
        ])
        
        total_checked = 0
        total_updated = 0
        
        for connector in connectors:
            try:
                # Get ALL non-final orders for this connector
                pending_orders = self.search([
                    ('zid_connector_id', '=', connector.id),
                    ('order_status', 'not in', ['delivered', 'cancelled', 'returned'])
                ])
                
                if pending_orders:
                    _logger.info(f"Bulk syncing {len(pending_orders)} pending orders for {connector.app_name}")
                    checked, updated = self._batch_sync_order_status(pending_orders)
                    total_checked += checked
                    total_updated += updated
                
            except Exception as e:
                _logger.error(f"Bulk sync failed for connector {connector.app_name}: {str(e)}")
        
        _logger.info(f"Bulk sync completed. Checked: {total_checked}, Updated: {total_updated}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Bulk Sync Complete',
                'message': f'Bulk status sync completed. Checked {total_checked} orders, updated {total_updated}.',
                'type': 'success',
                'sticky': True,
            }
        }
    @api.model
    def reset_connector_locks(self):
        """Reset all connector lock fields - use this if cron jobs are stuck"""
        connectors = self.env['zid.connector'].search([
            '|', '|',
            ('order_import_in_progress', '=', True),
            ('order_status_sync_in_progress', '=', True),
            ('product_import_in_progress', '=', True)
        ])
        
        if connectors:
            connectors.write({
                'order_import_in_progress': False,
                'order_import_started_at': False,
                'order_status_sync_in_progress': False,
                'order_status_sync_started_at': False,
                'product_import_in_progress': False,
                'product_import_started_at': False,
            })
            _logger.info(f"Reset locks for {len(connectors)} connectors: {[c.app_name for c in connectors]}")
            return f"Reset locks for {len(connectors)} connectors"
        else:
            _logger.info("No locked connectors found")
            return "No locked connectors found"