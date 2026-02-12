from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class ZidQueueLineEpt(models.Model):
    _name = 'zid.queue.line.ept'
    _description = 'Zid Queue Line'
    
    queue_id = fields.Many2one('zid.queue.ept', string='Queue', required=True, ondelete='cascade')
    zid_connector_id = fields.Many2one('zid.connector', related='queue_id.zid_connector_id', store=True)
    company_id = fields.Many2one('res.company', related='queue_id.company_id', store=True)
    
    zid_id = fields.Char(string='Zid ID', required=True)
    name = fields.Char(string='Name/Reference')
    data = fields.Text(string='Data (JSON)', required=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('failed', 'Failed')
    ], string='Status', default='draft')
    
    processed_at = fields.Datetime(string='Processed At')
    log = fields.Text(string='Log')
    
    def process_queue_line(self):
        """Process individual queue lines"""
        for line in self:
            try:
                with self.env.cr.savepoint():
                    if line.queue_id.model_type == 'order':
                        line._process_order()
                    # Add other types here (product, customer)
                    
                    line.state = 'done'
                    line.processed_at = fields.Datetime.now()
                    line.log = 'Processed successfully'
                
            except Exception as e:
                _logger.error(f"Queue line processing failed: {str(e)}", exc_info=True)
                try:
                    # After an exception, the savepoint has rolled back to before _process_order
                    # but we are STILL in a valid transaction (the savepoint took the hit).
                    # We can now update the state to failed.
                    line.write({
                        'state': 'failed',
                        'log': str(e)
                    })
                except Exception as e2:
                    _logger.error(f"Failed to record failure for queue line {line.id}: {str(e2)}")
            
            # Commit after each line to ensure the state is persisted
            # This prevents losing all progress if a later line or the entire job crashes
            self.env.cr.commit()

    def _process_order(self):
        """Process order import from queue - data is already raw from proxy"""
        self.ensure_one()
        order_data = json.loads(self.data)
        
        # Data is now RAW from Zid (proxy returns raw, not processed)
        # We process it locally with client's business logic
        _logger.info(f"Processing order {self.zid_id} locally with client business logic")
        
        # Apply client's business logic locally
        processed = self._apply_business_logic(order_data)
        
        # Step 2: Check if order already exists in Odoo
        order_model = self.env['zid.sale.order']
        existing = order_model.search([
            ('zid_order_id', '=', self.zid_id),
            ('zid_connector_id', '=', self.zid_connector_id.id)
        ], limit=1)
        
        # Step 3: Prepare values for zid.sale.order (just data storage, no business logic)
        if not self.zid_connector_id:
            raise UserError(_('Queue line missing zid_connector_id'))
            
        wizard = self.env['zid.sale.order.connector'].create({
            'zid_connector_id': self.zid_connector_id.id,
            'import_mode': 'all'
        })
        vals = wizard._prepare_order_values(order_data)
        
        # Ensure zid_connector_id is set (safety check)
        if not vals.get('zid_connector_id'):
            vals['zid_connector_id'] = self.zid_connector_id.id
            _logger.warning(f"Had to manually set zid_connector_id for order {self.zid_id}")
        
        # Step 4: Add processed data from proxy and update raw data if enhanced
        vals.update({
            'processed_data': json.dumps(processed, ensure_ascii=False),  # Store proxy result
            'raw_data': json.dumps(order_data, ensure_ascii=False),  # Store updated raw data (may include full order details)
        })
        
        # Step 5: Create or update zid.sale.order record
        if existing:
            existing.write(vals)
            order = existing
            _logger.info(f"Updated existing Zid order record {order.id}")
        else:
            order = order_model.create(vals)
            _logger.info(f"Created new Zid order record {order.id}")
        
        # Step 6: Create Odoo sale.order from processed data if auto-create is enabled
        if self.zid_connector_id.auto_create_sale_order and not order.sale_order_id:
            self._create_sale_order_from_processed(order, processed)
    
    def _create_sale_order_from_processed(self, zid_order, processed):
        """Create Odoo sale.order from proxy-processed data"""
        try:
            # Customer data from proxy
            customer_data = processed.get('customer', {})
            
            # Find or create customer based on proxy's matching rules
            partner = self._find_or_create_partner(customer_data)
            
            # Create sale order with processed data
            sale_vals = {
                'partner_id': partner.id,
                'partner_invoice_id': partner.id,
                'partner_shipping_id': partner.id,
                'date_order': zid_order.zid_created_at or fields.Datetime.now(),
                'client_order_ref': str(zid_order.zid_order_id),
                'note': zid_order.customer_note or '',
                'company_id': self.zid_connector_id.company_id.id,
                'zid_order_ref': str(zid_order.zid_order_id),
                'zid_order_id': zid_order.id,
            }
            
            # Add salesperson and sales team if configured
            if self.zid_connector_id.default_user_id:
                sale_vals['user_id'] = self.zid_connector_id.default_user_id.id
            
            if self.zid_connector_id.default_team_id:
                sale_vals['team_id'] = self.zid_connector_id.default_team_id.id
            
            sale_order = self.env['sale.order'].create(sale_vals)
            _logger.info(f"Created sale order {sale_order.name} for Zid order {zid_order.zid_order_id}")
            
            # Create order lines from proxy-processed product data
            products = processed.get('products', [])
            _logger.info(f"Processing {len(products)} products for sale order {sale_order.name}")
            for product in products:
                self._create_sale_order_line(sale_order, product)
            
            # Create shipping line if needed
            shipping = processed.get('shipping', {})
            if shipping.get('cost', 0) > 0:
                self._create_shipping_line(sale_order, shipping)
            
            # Link to zid order
            zid_order.sale_order_id = sale_order.id
            
            # Apply automation based on connector settings
            self._apply_order_automation(sale_order)
            
            _logger.info(f"Sale order {sale_order.name} created successfully with {len(processed.get('products', []))} lines")
            
        except Exception as e:
            _logger.error(f"Failed to create sale order: {str(e)}", exc_info=True)
            raise
    
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
                raise UserError(_("Failed to auto-confirm order %s: %s") % (sale_order.name, str(e)))
        
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
                raise UserError(_("Failed to auto-create/confirm invoice for order %s: %s") % (sale_order.name, str(e)))
        
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
                raise UserError(_("Failed to auto-validate delivery for order %s: %s") % (sale_order.name, str(e)))
        
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
            # Find the related Zid order
            zid_order = self.env['zid.sale.order'].search([
                ('sale_order_id', '=', sale_order.id)
            ], limit=1)
            
            if not zid_order:
                _logger.warning(f"No Zid order found for sale order {sale_order.name}")
                return
            
            # Only process if Zid order is marked as paid
            if zid_order.payment_status != 'paid':
                _logger.info(f"Zid order {zid_order.zid_order_id} payment status is '{zid_order.payment_status}', skipping payment registration")
                return
            
            # Find posted invoices for this order
            invoices = sale_order.invoice_ids.filtered(lambda inv: inv.state == 'posted' and inv.move_type == 'out_invoice')
            
            if not invoices:
                _logger.warning(f"No posted invoices found for order {sale_order.name}, cannot register payment")
                return
            
            # Get payment journal from mapping or default
            payment_journal = self._get_payment_journal(zid_order)
            
            if not payment_journal:
                _logger.error(f"No payment journal configured for payment method '{zid_order.payment_method_code}'")
                return
            
            # Register payment for each invoice
            for invoice in invoices:
                # Check if payment already exists
                # Use 'memo' (Odoo 17+) or 'communication' (Older) safely
                payment_ref_field = 'memo' if hasattr(self.env['account.payment'], 'memo') else 'communication'
                
                existing_payments = self.env['account.payment'].search([
                    (payment_ref_field, 'like', f'Zid Order {zid_order.zid_order_id}'),
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
                    'date': zid_order.zid_created_at or fields.Date.today(),
                    payment_ref_field: f'Zid Order {zid_order.zid_order_id} - {zid_order.payment_method_name}',
                    'reconciled_invoice_ids': [(6, 0, [invoice.id])],
                }
                
                payment = self.env['account.payment'].create(payment_vals)
                payment.action_post()
                
                _logger.info(f"Auto-registered payment {payment.name} for invoice {invoice.name}")
                
                # Auto-reconcile if enabled
                if self.zid_connector_id.auto_reconcile_payment:
                    self._auto_reconcile_payment(payment, invoice)
                    
        except Exception as e:
            raise UserError(_("Failed to auto-register payment for order %s: %s") % (sale_order.name, str(e)))
    
    def _get_payment_journal(self, zid_order):
        """Get payment journal based on Zid payment method mapping"""
        # First try to find specific mapping
        mapping = self.env['zid.payment.mapping'].search([
            ('zid_connector_id', '=', zid_order.zid_connector_id.id),
            ('payment_method_code', '=', zid_order.payment_method_code)
        ], limit=1)
        
        if mapping:
            return mapping.payment_journal_id
        
        # Fallback to default journal
        return zid_order.zid_connector_id.default_payment_journal_id
    
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
    
    def _find_or_create_partner(self, customer_data):
        """Find or create partner based on proxy's customer data"""
        partner_model = self.env['res.partner']
        
        # Use proxy's matching strategy
        match_by = customer_data.get('match_by', 'both')
        email = customer_data.get('email')
        mobile = customer_data.get('mobile')
        name = customer_data.get('name', 'Guest Customer')
        
        domain = []
        conditions = []
        if match_by in ['email', 'both'] and email:
            conditions.append(('email', '=', email))
        if match_by in ['mobile', 'both'] and mobile:
            conditions.append(('mobile', '=', mobile))
            
        if not conditions:
            domain = []
        elif len(conditions) == 1:
            domain = conditions
        else:
            domain = ['|'] + conditions
        
        if domain:
            partner = partner_model.search(domain, limit=1)
            if partner:
                return partner
        
        # Create new partner
        return partner_model.create({
            'name': name,
            'email': email,
            'mobile': mobile,
            'customer_rank': 1,
            'company_id': self.zid_connector_id.company_id.id,
        })
    
    def _create_sale_order_line(self, sale_order, product_data):
        """Create sale order line from proxy-processed product data"""
        # Log the product data we're trying to match
        zid_product_id = product_data.get('zid_product_id', '')
        sku = product_data.get('sku', '')
        barcode = product_data.get('barcode', '')
        name = product_data.get('name', '')
        
        _logger.info(f"Attempting to create order line for product: ID={zid_product_id}, SKU={sku}, Barcode={barcode}, Name={name}")
        
        # Find product by matching strategy from proxy
        product = self._find_product(product_data)
        
        if not product:
            _logger.error(f"CRITICAL: Product not found for order line - ID: {zid_product_id}, SKU: {sku}, Barcode: {barcode}, Name: {name}")
            _logger.error(f"Product matching strategy: {product_data.get('match_by', 'sku')}")
            _logger.error(f"Connector product_match_by: {self.zid_connector_id.product_match_by}")
            
            # Check if we have any Zid product mappings
            if zid_product_id:
                variant_count = self.env['zid.variant'].search_count([
                    ('zid_variant_id', '=', str(zid_product_id)),
                    ('zid_connector_id', '=', self.zid_connector_id.id)
                ])
                product_count = self.env['zid.product'].search_count([
                    ('zid_product_id', '=', str(zid_product_id)),
                    ('zid_connector_id', '=', self.zid_connector_id.id)
                ])
                _logger.error(f"Zid mappings found - Variants: {variant_count}, Products: {product_count}")
            
            # Check if we have Odoo products with this SKU/barcode
            if sku:
                odoo_sku_count = self.env['product.product'].search_count([('default_code', '=', sku)])
                _logger.error(f"Odoo products with SKU '{sku}': {odoo_sku_count}")
            if barcode:
                odoo_barcode_count = self.env['product.product'].search_count([('barcode', '=', barcode)])
                _logger.error(f"Odoo products with Barcode '{barcode}': {odoo_barcode_count}")
            
            raise UserError(_("Product not found for order line - SKU: %s, Name: %s. Please map this product or create it in Odoo before reprocessing.") % (sku, name))
        
        _logger.info(f"Successfully found product: {product.display_name} (ID: {product.id})")
        
        line_vals = {
            'order_id': sale_order.id,
            'product_id': product.id,
            'name': product_data.get('name', product.name),
            'product_uom_qty': product_data.get('quantity', 1),
            'price_unit': product_data.get('price', 0),  # Price already processed by proxy (with commission)
            'tax_id': [(6, 0, product.taxes_id.ids)] if product.taxes_id else False,
        }
        
        order_line = self.env['sale.order.line'].create(line_vals)
        _logger.info(f"Created order line: {product.name} x {product_data.get('quantity', 1)} @ {product_data.get('price', 0)}")
    
    def _find_product(self, product_data):
        """Find product based on connector's matching priority and strategy"""
        product_model = self.env['product.product']
        zid_product_id = str(product_data.get('zid_product_id', ''))
        sku = product_data.get('sku')
        barcode = product_data.get('barcode')
        name = product_data.get('name')
        match_by = product_data.get('match_by', self.zid_connector_id.product_match_by)
        priority = self.zid_connector_id.product_match_priority

        _logger.info(f"Finding product with priority '{priority}' and method '{match_by}' - ID: {zid_product_id}, SKU: {sku}, Barcode: {barcode}")

        # Strategy 1: Zid Mapping First (Default - Recommended)
        if priority == 'mapping_first':
            # Try Zid mappings first
            product = self._find_product_by_mapping(zid_product_id)
            if product:
                return product
            
            # Fallback to direct matching
            product = self._find_product_by_direct_match(match_by, sku, barcode, name)
            if product:
                return product

        # Strategy 2: Direct SKU/Barcode Only
        elif priority == 'direct_only':
            _logger.info("Using direct matching only (ignoring Zid mappings)")
            product = self._find_product_by_direct_match(match_by, sku, barcode, name)
            if product:
                return product

        # Strategy 3: Zid Mapping Only
        elif priority == 'mapping_only':
            _logger.info("Using Zid mappings only (no fallback to SKU/Barcode)")
            product = self._find_product_by_mapping(zid_product_id)
            if product:
                return product

        _logger.warning(f"No product found after all matching attempts with priority '{priority}'")
        return None

    def _find_product_by_mapping(self, zid_product_id):
        """Find product using Zid product/variant mappings"""
        if not zid_product_id:
            return None

        # 1. Try to find via Zid Variant mapping first (if it's a variant)
        variant = self.env['zid.variant'].search([
            ('zid_variant_id', '=', zid_product_id),
            ('zid_connector_id', '=', self.zid_connector_id.id)
        ], limit=1)
        if variant and variant.odoo_product_id:
            _logger.info(f"Found Odoo product {variant.odoo_product_id.display_name} via zid.variant mapping")
            return variant.odoo_product_id

        # 2. Try to find via Zid Product mapping second
        zid_product = self.env['zid.product'].search([
            ('zid_product_id', '=', zid_product_id),
            ('zid_connector_id', '=', self.zid_connector_id.id)
        ], limit=1)
        if zid_product and zid_product.odoo_product_id:
            _logger.info(f"Found Odoo product {zid_product.odoo_product_id.display_name} via zid.product mapping")
            return zid_product.odoo_product_id

        return None

    def _find_product_by_direct_match(self, match_by, sku, barcode, name):
        """Find product using direct SKU/Barcode/Name matching"""
        product_model = self.env['product.product']
        # Simplified domain - remove company filter to avoid field issues
        domain = []
        
        if match_by == 'sku' and sku:
            _logger.info(f"Searching for product by SKU: {sku}")
            product = product_model.search([('default_code', '=', sku)] + domain, limit=1)
            if product:
                _logger.info(f"Found product by SKU: {product.display_name}")
                return product
        
        elif match_by == 'barcode' and barcode:
            _logger.info(f"Searching for product by Barcode: {barcode}")
            product = product_model.search([('barcode', '=', barcode)] + domain, limit=1)
            if product:
                _logger.info(f"Found product by Barcode: {product.display_name}")
                return product
        
        elif match_by == 'name' and name:
            if isinstance(name, dict):
                name = name.get('en') or name.get('ar')
            _logger.info(f"Searching for product by Name: {name}")
            product = product_model.search([('name', '=', name)] + domain, limit=1)
            if product:
                _logger.info(f"Found product by Name: {product.display_name}")
                return product

        # Last ditch effort: Try any SKU or Barcode match if we haven't found anything
        _logger.info("Attempting fallback product matching...")
        if sku:
            product = product_model.search([('default_code', '=', sku)] + domain, limit=1)
            if product: 
                _logger.info(f"Found product by fallback SKU search: {product.display_name}")
                return product
            product = product_model.search([('barcode', '=', sku)] + domain, limit=1)
            if product: 
                _logger.info(f"Found product by fallback SKU->Barcode search: {product.display_name}")
                return product
            
        if barcode:
            product = product_model.search([('barcode', '=', barcode)] + domain, limit=1)
            if product: 
                _logger.info(f"Found product by fallback Barcode search: {product.display_name}")
                return product
            product = product_model.search([('default_code', '=', barcode)] + domain, limit=1)
            if product: 
                _logger.info(f"Found product by fallback Barcode->SKU search: {product.display_name}")
                return product

        return None
    
    def _apply_business_logic(self, order_data):
        """Apply client's business logic to raw order data"""
        connector = self.zid_connector_id
        
        # Get client's business configuration
        config = {
            'min_order_amount': connector.min_order_amount or 0,
            'max_order_amount': connector.max_order_amount or 0,
            'auto_confirm_orders': connector.auto_confirm_orders or False,
            'apply_commission': connector.apply_commission or False,
            'commission_rate': connector.commission_rate or 0,
            'commission_type': connector.commission_type or 'percentage',
            'customer_match_by': connector.customer_match_by or 'both',
            'product_match_by': connector.product_match_by or 'sku',
            'shipping_tax_rate': connector.shipping_tax_rate or 0,
        }
        
        # Process order with client's rules
        total = float(order_data.get('total', 0))
        requires_approval = False
        
        # Check min/max amounts
        if config['min_order_amount'] > 0 and total < config['min_order_amount']:
            raise ValueError(f"Order amount {total} below minimum {config['min_order_amount']}")
        
        if config['max_order_amount'] > 0 and total > config['max_order_amount']:
            requires_approval = True
        
        # Process customer
        customer_data = order_data.get('customer', {})
        processed_customer = {
            'name': customer_data.get('name', 'Guest'),
            'email': customer_data.get('email'),
            'mobile': customer_data.get('mobile'),
            'match_by': config['customer_match_by']
        }
        
        # Process products with commission
        products_data = order_data.get('products', [])
        
        # If no products in order data, fetch full order details from Zid
        if not products_data:
            _logger.info(f"No products found in order data, fetching full order details for order {order_data.get('id', 'unknown')}")
            try:
                order_id = order_data.get('id')
                if order_id:
                    endpoint = f"managers/store/orders/{order_id}/view"
                    response = connector.api_request(
                        endpoint=endpoint,
                        method='GET'
                    )
                    if response and 'order' in response:
                        full_order_data = response['order']
                        products_data = full_order_data.get('products', [])
                        _logger.info(f"Fetched full order details, found {len(products_data)} products")
                        
                        # Update the original order_data with full details for future use
                        order_data.update(full_order_data)
                    else:
                        _logger.warning(f"Failed to fetch full order details for order {order_id}")
            except Exception as e:
                _logger.error(f"Error fetching full order details: {str(e)}")
        
        processed_products = []
        for product in products_data:
            price = float(product.get('price', 0))
            
            # Apply commission if enabled
            if config['apply_commission']:
                if config['commission_type'] == 'percentage':
                    price += price * (config['commission_rate'] / 100)
                else:
                    price += config['commission_rate']
            
            processed_products.append({
                'zid_product_id': str(product.get('id')),
                'name': product.get('name'),
                'sku': product.get('sku'),
                'barcode': product.get('barcode'),
                'price': price,
                'quantity': product.get('quantity', 1),
                'match_by': config['product_match_by']
            })
        
        # Process shipping with tax
        shipping = order_data.get('shipping', {})
        shipping_cost = float(shipping.get('cost', 0))
        if config['shipping_tax_rate'] > 0:
            shipping_cost += shipping_cost * (config['shipping_tax_rate'] / 100)
        
        processed_shipping = {
            'method': shipping.get('method', {}),
            'cost': shipping_cost,
        }
        
        return {
            'customer': processed_customer,
            'products': processed_products,
            'shipping': processed_shipping,
            'total': total,
            'requires_approval': requires_approval,
            'auto_confirm': config['auto_confirm_orders'] and not requires_approval
        }
    
    def _create_shipping_line(self, sale_order, shipping_data):
        """Create shipping line with processed cost from proxy"""
        # Use configured shipping product or create generic one
        shipping_product_id = shipping_data.get('product_id')
        
        if shipping_product_id:
            shipping_product = self.env['product.product'].browse(shipping_product_id)
        else:
            # Find or create generic shipping product
            shipping_product = self.env['product.product'].search([
                ('name', '=', 'Shipping Cost (Zid)'),
                ('type', '=', 'service')
            ], limit=1)
            
            if not shipping_product:
                shipping_product = self.env['product.product'].create({
                    'name': 'Shipping Cost (Zid)',
                    'type': 'service',
                    'list_price': 0,
                    'invoice_policy': 'order',
                })
        
        self.env['sale.order.line'].create({
            'order_id': sale_order.id,
            'product_id': shipping_product.id,
            'name': f"Shipping - {shipping_data.get('method', {}).get('name', 'Standard')}",
            'product_uom_qty': 1,
            'price_unit': shipping_data.get('cost', 0),  # Cost already processed by proxy (with tax)
        })
