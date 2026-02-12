from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import requests
import json
import logging
from datetime import datetime, timedelta
import urllib.parse

_logger = logging.getLogger(__name__)


class ZidConnector(models.Model):
    _name = 'zid.connector'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Zid Integration Connector'
    _rec_name = 'app_name'

    # Basic app information
    app_name = fields.Char(
        string='App Name',
        required=True,
        help='Name to identify this Zid integration'
    )

    company_id = fields.Many2one(
        'res.company', 
        string='Company', 
        required=True, 
        default=lambda self: self.env.company
    )

    # Proxy Configuration (Commercial)
    proxy_url = fields.Char(
        string='Proxy Server URL',
        default='https://www.cloudmen.ae',
        required=True,
        help='URL of the Cloudmen proxy server for business logic'
    )
    license_key = fields.Char(
        string='License Key',
        required=True,
        help='Your Zid Integration license key from Cloudmen'
    )
    database_uuid = fields.Char(
        string='Database UUID',
        default=lambda self: self._generate_database_uuid(),
        readonly=True,
        copy=False,
        help='Unique identifier of this Odoo database'
    )
    license_valid = fields.Boolean(
        string='License Valid',
        compute='_compute_license_status',
        store=False,
        help='Current license validation status'
    )
    license_status_message = fields.Char(
        string='License Status',
        compute='_compute_license_status',
        store=False
    )
    
    store_id = fields.Char(
        string='Store ID',
        required=True,
        help='Zid Store ID (numeric)'
    )


    api_base_url = fields.Char(
        string='API Base URL',
        default='https://api.zid.sa/v1',
        required=True,
        readonly=True
    )

    # Connection information
    store_name = fields.Char(
        string='Store Name',
        readonly=True,
        help='Store name from Zid'
    )
    authorization_status = fields.Selection([
        ('not_connected', 'Not Connected'),
        ('connected', 'Connected'),
        ('error', 'Error'),
        ('expired', 'Token Expired')
    ], string='Status', default='not_connected', readonly=True)

    connection_date = fields.Datetime(
        string='Connection Date',
        readonly=True,
        help='Last successful connection date'
    )

    # Tokens are stored ONLY on proxy server for security
    # Client never has access to tokens

    # Additional information

    scopes = fields.Text(
        string='Scopes',
        readonly=True,
        help='Authorized scopes'
    )
    last_sync_date = fields.Datetime(
        string='Last Sync Date',
        readonly=True
    )
    order_import_start_date = fields.Datetime(
        string='Order Fetch Start Date',
        help='Fixed start date for order imports. Set this once to define the earliest date for importing orders. \
              The system will use this for the first import, then use incremental sync for subsequent imports.'
    )
    
    product_import_start_date = fields.Datetime(
        string='Product Fetch Start Date',
        help='Fixed start date for product imports. Set this once to define the earliest date for importing products. \
              The system will use this for the first import, then use incremental sync for subsequent imports.'
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )

    # Store information
    store_url = fields.Char(
        string='Store URL',
        readonly=True
    )
    store_email = fields.Char(
        string='Store Email',
        readonly=True
    )
    store_currency = fields.Char(
        string='Store Currency',
        readonly=True
    )

    # Connection status (tokens managed by proxy server)
    is_connected = fields.Boolean(
        string='Is Connected',
        compute='_compute_is_connected',
        store=False
    )

    webhook_ids = fields.One2many(
        'zid.webhook',
        'zid_connector_id',
        string='Webhooks'
    )

    webhook_secret = fields.Char(
        string='Webhook Secret',
        help='Secret key for webhook verification'
    )

    enable_product_sync = fields.Boolean(
        string='Auto-sync Products',
        default=True,
        help='Automatically create/update products when webhook is received'
    )

    auto_create_sale_order = fields.Boolean(
        string='Auto Create Sale Orders',
        default=True,
        help='Automatically create Odoo sale orders when importing Zid orders'
    )

    auto_process_webhooks = fields.Boolean(
        string='Auto Process Webhooks',
        default=True,
        help='Automatically process webhook data immediately instead of queuing'
    )

    sync_status_to_zid = fields.Boolean(
        string='Sync Status to Zid',
        default=False,
        help='If checked, Odoo will update Zid order status when changed in Odoo'
    )

    # ===== BUSINESS RULES CONFIGURATION (Sent to Proxy) =====
    
    # Commission Settings
    apply_commission = fields.Boolean(
        string='Apply Commission',
        default=False,
        help='Apply commission to product prices during import'
    )
    commission_rate = fields.Float(
        string='Commission Rate (%)',
        default=0.0,
        help='Commission percentage to add to product prices'
    )
    commission_type = fields.Selection([
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount')
    ], string='Commission Type', default='percentage')
    
    # Customer Matching Rules (PRIMARY - Use these)
    customer_match_by = fields.Selection([
        ('email', 'Match by Email'),
        ('mobile', 'Match by Mobile'),
        ('both', 'Match by Email or Mobile'),
        ('always_create', 'Always Create New')
    ], string='Customer Matching', default='both',
       help='How to match existing customers when importing orders:\n'
            '• Email: Search by email address\n'
            '• Mobile: Search by phone number\n'
            '• Both: Search by email OR mobile\n'
            '• Always Create: Never match, always create new customer')
    
    # Product Matching Rules (PRIMARY - Use these)
    product_match_priority = fields.Selection([
        ('mapping_first', 'Zid Mapping First (Recommended)'),
        ('direct_only', 'Direct SKU/Barcode Only'),
        ('mapping_only', 'Zid Mapping Only')
    ], string='Product Matching Priority', default='mapping_first',
       help='Choose the priority for product matching:\n'
            '• Zid Mapping First: Try Zid product/variant mappings first, then fallback to SKU/Barcode\n'
            '• Direct SKU/Barcode Only: Only use SKU/Barcode matching, ignore Zid mappings\n'
            '• Zid Mapping Only: Only use Zid product/variant mappings, never fallback to SKU/Barcode')
    
    product_match_by = fields.Selection([
        ('sku', 'Match by SKU'),
        ('barcode', 'Match by Barcode'),
        ('name', 'Match by Name'),
        ('create_if_not_found', 'Create if Not Found')
    ], string='Product Matching Method', default='sku',
       help='How to match existing products when importing orders:\n'
            '• SKU: Match by product internal reference (default_code)\n'
            '• Barcode: Match by product barcode\n'
            '• Name: Match by product name\n'
            '• Create if Not Found: Create new product if no match')
    
    # Order Processing Rules
    auto_confirm_orders = fields.Boolean(
        string='Auto-Confirm Orders',
        default=False,
        help='Automatically confirm imported orders'
    )
    auto_create_invoice = fields.Boolean(
        string='Auto-Create Invoice',
        default=False,
        help='Automatically create invoice when order is confirmed'
    )
    auto_confirm_invoice = fields.Boolean(
        string='Auto-Confirm Invoice',
        default=False,
        help='Automatically confirm/validate the created invoice'
    )
    auto_validate_delivery = fields.Boolean(
        string='Auto-Validate Delivery',
        default=False,
        help='Automatically validate delivery/picking when order is processed'
    )
    
    # Payment Processing Rules
    auto_register_payment = fields.Boolean(
        string='Auto-Register Payment',
        default=False,
        help='Automatically register payment when Zid order is marked as paid'
    )
    auto_reconcile_payment = fields.Boolean(
        string='Auto-Reconcile Payment',
        default=False,
        help='Automatically reconcile payment with invoice'
    )
    default_payment_journal_id = fields.Many2one(
        'account.journal',
        string='Default Payment Journal',
        domain=[('type', 'in', ('bank', 'cash'))],
        help='Default journal for payments when no specific mapping exists'
    )
    
    # Order Status Sync Configuration
    auto_sync_order_status = fields.Boolean(
        string='Auto Sync Order Status',
        default=True,
        help='Automatically sync order status changes from Zid to Odoo'
    )
    status_sync_frequency = fields.Selection([
        ('15min', 'Every 15 minutes'),
        ('30min', 'Every 30 minutes'),
        ('1hour', 'Every hour'),
        ('4hour', 'Every 4 hours'),
        ('daily', 'Daily')
    ], string='Status Sync Frequency', default='30min',
       help='How often to check for order status changes in Zid')
    
    status_sync_days_back = fields.Integer(
        string='Sync Orders From Last X Days',
        default=7,
        help='Only check orders modified in the last X days for status changes'
    )
    
    sync_order_status_on_import = fields.Boolean(
        string='Sync Status During Import',
        default=True,
        help='Check and update order status when importing new orders'
    )
    
    sync_all_pending_orders = fields.Boolean(
        string='Sync All Pending Orders',
        default=False,
        help='Include all non-final orders regardless of age (may be slower but more comprehensive)'
    )
    
    # Sync Lock Fields (to prevent concurrent operations)
    order_import_in_progress = fields.Boolean(
        string='Order Import In Progress',
        default=False,
        readonly=True,
        help='Indicates if order import is currently running'
    )
    
    order_import_started_at = fields.Datetime(
        string='Order Import Started At',
        readonly=True,
        help='Timestamp when order import was started'
    )
    
    product_import_in_progress = fields.Boolean(
        string='Product Import In Progress',
        default=False,
        readonly=True,
        help='Indicates if product import is currently running'
    )
    
    product_import_started_at = fields.Datetime(
        string='Product Import Started At',
        readonly=True,
        help='Timestamp when product import was started'
    )
    
    order_status_sync_in_progress = fields.Boolean(
        string='Order Status Sync In Progress', 
        default=False,
        readonly=True,
        help='Indicates if order status sync is currently running'
    )
    
    order_status_sync_started_at = fields.Datetime(
        string='Order Status Sync Started At',
        readonly=True,
        help='Timestamp when order status sync was started'
    )
    
    # Timeout Configuration
    import_timeout_minutes = fields.Integer(
        string='Import Timeout (Minutes)',
        default=60,
        help='Maximum time allowed for import operations before auto-reset (0 = no timeout)'
    )
    
    last_order_import_date = fields.Datetime(
        string='Last Order Import',
        readonly=True,
        help='When orders were last imported'
    )
    
    last_product_import_date = fields.Datetime(
        string='Last Product Import',
        readonly=True,
        help='When products were last imported'
    )
    
    last_status_sync_date = fields.Datetime(
        string='Last Status Sync',
        readonly=True,
        help='When order statuses were last synced'
    )
    
    # Sales Team Configuration
    default_user_id = fields.Many2one(
        'res.users',
        string='Default Salesperson',
        help='Default salesperson to assign to imported orders'
    )
    default_team_id = fields.Many2one(
        'crm.team',
        string='Default Sales Team',
        help='Default sales team to assign to imported orders'
    )
    
    min_order_amount = fields.Float(
        string='Minimum Order Amount',
        default=0.0,
        help='Reject orders below this amount (0 = no minimum)'
    )
    max_order_amount = fields.Float(
        string='Maximum Order Amount (Requires Approval)',
        default=0.0,
        help='Orders above this amount require manual approval (0 = no limit)'
    )
    
    # Stock Sync Rules
    sync_negative_stock = fields.Boolean(
        string='Sync Negative Stock',
        default=False,
        help='Allow syncing negative stock quantities to Zid'
    )
    stock_rounding = fields.Selection([
        ('down', 'Round Down'),
        ('up', 'Round Up'),
        ('nearest', 'Round to Nearest')
    ], string='Stock Rounding', default='down',
       help='How to round stock quantities when syncing to Zid')
    safety_stock_days = fields.Integer(
        string='Safety Stock (Days)',
        default=0,
        help='Reserve stock for X days (reduces synced quantity)'
    )
    
    # Shipping Settings
    shipping_tax_rate = fields.Float(
        string='Shipping Tax Rate (%)',
        default=0.0,
        help='Tax rate to apply to shipping costs'
    )
    default_shipping_product_id = fields.Many2one(
        'product.product',
        string='Default Shipping Product',
        domain=[('type', '=', 'service')],
        help='Product to use for shipping line items'
    )
    
    # Category Settings
    auto_create_categories = fields.Boolean(
        string='Auto-Create Categories',
        default=True,
        help='Automatically create product categories if they don\'t exist'
    )
    default_category_id = fields.Many2one(
        'product.category',
        string='Default Category',
        help='Default category for products without a category'
    )

    # Dashboard Metrics
    order_count = fields.Integer(compute='_compute_dashboard_metrics')
    product_count = fields.Integer(compute='_compute_dashboard_metrics')
    customer_count = fields.Integer(compute='_compute_dashboard_metrics')
    
    # Enhanced Analytics
    today_orders = fields.Integer(string="Today's Orders", compute='_compute_dashboard_metrics')
    week_orders = fields.Integer(string="This Week's Orders", compute='_compute_dashboard_metrics')
    month_revenue = fields.Float(string="This Month's Revenue", compute='_compute_dashboard_metrics')
    pending_orders = fields.Integer(string='Pending Orders', compute='_compute_dashboard_metrics')
    low_stock_products = fields.Integer(string='Low Stock Products', compute='_compute_dashboard_metrics')
    sync_errors = fields.Integer(string='Sync Errors', compute='_compute_dashboard_metrics')
    last_sync_status = fields.Char(string='Last Sync Status', compute='_compute_dashboard_metrics')
    sync_health_score = fields.Integer(string='Sync Health %', compute='_compute_dashboard_metrics')
    
    color = fields.Integer(string='Color Index')
    
    def _compute_dashboard_metrics(self):
        from datetime import datetime, timedelta
        
        for record in self:
            # Basic counts
            record.order_count = self.env['zid.sale.order'].search_count([('zid_connector_id', '=', record.id)])
            record.product_count = self.env['zid.product'].search_count([('zid_connector_id', '=', record.id)])
            record.customer_count = self.env['res.partner'].search_count([
                ('company_id', '=', record.company_id.id),
                ('customer_rank', '>', 0)
            ])
            
            # Time-based analytics
            today = datetime.now().date()
            week_start = today - timedelta(days=today.weekday())
            month_start = today.replace(day=1)
            
            # Today's orders
            record.today_orders = self.env['zid.sale.order'].search_count([
                ('zid_connector_id', '=', record.id),
                ('create_date', '>=', datetime.combine(today, datetime.min.time()))
            ])
            
            # This week's orders
            record.week_orders = self.env['zid.sale.order'].search_count([
                ('zid_connector_id', '=', record.id),
                ('create_date', '>=', datetime.combine(week_start, datetime.min.time()))
            ])
            
            # This month's revenue
            month_orders = self.env['zid.sale.order'].search([
                ('zid_connector_id', '=', record.id),
                ('create_date', '>=', datetime.combine(month_start, datetime.min.time()))
            ])
            record.month_revenue = sum(month_orders.mapped('order_total'))
            
            # Pending orders
            record.pending_orders = self.env['zid.sale.order'].search_count([
                ('zid_connector_id', '=', record.id),
                ('order_status', 'in', ['new', 'preparing'])
            ])
            
            # Low stock products (qty < 10)
            low_stock = 0
            for product in self.env['zid.product'].search([('zid_connector_id', '=', record.id)]):
                if product.odoo_product_id and product.odoo_product_id.qty_available < 10:
                    low_stock += 1
            record.low_stock_products = low_stock
            
            # Sync errors (last 7 days)
            seven_days_ago = today - timedelta(days=7)
            record.sync_errors = self.env['zid.stock.update.log'].search_count([
                ('zid_connector_id', '=', record.id),
                ('status', '=', 'failed'),
                ('create_date', '>=', datetime.combine(seven_days_ago, datetime.min.time()))
            ])
            
            # Last sync status
            last_log = self.env['zid.stock.update.log'].search([
                ('zid_connector_id', '=', record.id)
            ], order='create_date desc', limit=1)
            
            if last_log:
                record.last_sync_status = f"{last_log.status.title()} - {last_log.create_date.strftime('%H:%M')}"
            else:
                record.last_sync_status = 'No sync yet'
            
            # Sync health score (0-100)
            total_logs = self.env['zid.stock.update.log'].search_count([
                ('zid_connector_id', '=', record.id),
                ('create_date', '>=', datetime.combine(seven_days_ago, datetime.min.time()))
            ])
            
            if total_logs > 0:
                success_logs = total_logs - record.sync_errors
                record.sync_health_score = int((success_logs / total_logs) * 100)
            else:
                record.sync_health_score = 100

    def _generate_database_uuid(self):
        """Generate unique database identifier"""
        import hashlib
        import uuid
        # Use combination of database name and a random UUID for uniqueness
        db_name = self.env.cr.dbname
        unique_string = f"{db_name}-{uuid.uuid4()}"
        return hashlib.md5(unique_string.encode()).hexdigest()

    def _compute_license_status(self):
        """Check license validity with proxy server"""
        for record in self:
                
            if not record.license_key or not record.proxy_url:
                record.license_valid = False
                record.license_status_message = 'License key or proxy URL not set'
                continue
            
            try:
                url = f"{record.proxy_url}/api/zid/validate-license"
                payload = {
                    'license_key': record.license_key,
                    'database_uuid': record.database_uuid
                }
                
                _logger.info("=" * 80)
                _logger.info("SENDING LICENSE VALIDATION REQUEST")
                _logger.info(f"URL: {url}")
                _logger.info(f"License Key: {record.license_key}")
                _logger.info(f"Database UUID: {record.database_uuid}")
                _logger.info(f"Payload: {payload}")
                
                response = requests.post(
                    url,
                    json=payload,
                    timeout=5
                )
                
                _logger.info(f"Response Status: {response.status_code}")
                _logger.info(f"Response Body: {response.text}")
                
                if response.status_code == 200:
                    response_data = response.json()
                    _logger.info(f"Parsed Result: {response_data}")
                    
                    # Handle JSON-RPC wrapped response
                    result = response_data.get('result', response_data)
                    _logger.info(f"Extracted result: {result}")
                    
                    record.license_valid = result.get('valid', False)
                    
                    if result.get('valid'):
                        expiry = result.get('expiry_date', 'Unknown')
                        remaining = result.get('api_calls_remaining', 0)
                        record.license_status_message = f"Valid until {expiry} ({remaining} API calls remaining)"
                        _logger.info("LICENSE VALID!")
                    else:
                        error_msg = result.get('error', 'Invalid license')
                        record.license_status_message = error_msg
                        _logger.warning(f"LICENSE INVALID: {error_msg}")
                else:
                    record.license_valid = False
                    record.license_status_message = f'Server error: {response.status_code}'
                    _logger.error(f"Server returned error: {response.status_code}")
                
                _logger.info("=" * 80)
            
            except Exception as e:
                _logger.error(f"License validation error: {str(e)}", exc_info=True)
                record.license_valid = False
                record.license_status_message = f'Connection error: {str(e)}'

    def _get_business_config(self):
        """Get business configuration to send to proxy"""
        self.ensure_one()
        return {
            # Commission
            'apply_commission': self.apply_commission,
            'commission_rate': self.commission_rate,
            'commission_type': self.commission_type,
            
            # Matching
            'customer_match_by': self.customer_match_by,
            'product_match_by': self.product_match_by,
            
            # Order Processing
            'auto_confirm_orders': self.auto_confirm_orders,
            'min_order_amount': self.min_order_amount,
            'max_order_amount': self.max_order_amount,
            
            # Stock
            'sync_negative_stock': self.sync_negative_stock,
            'stock_rounding': self.stock_rounding,
            'safety_stock_days': self.safety_stock_days,
            
            # Shipping
            'shipping_tax_rate': self.shipping_tax_rate,
            'default_shipping_product_id': self.default_shipping_product_id.id if self.default_shipping_product_id else None,
            
            # Categories
            'auto_create_categories': self.auto_create_categories,
            'default_category_id': self.default_category_id.id if self.default_category_id else None,
            'auto_create_sale_order': self.auto_create_sale_order,
        }

    def call_proxy_api(self, endpoint, data=None):
        """Helper to call proxy server APIs with license validation"""
        self.ensure_one()
        
        if not self.license_valid:
            raise UserError(_('Invalid or expired license. Please contact support.'))
        
        if not data:
            data = {}
        
        # Always include license credentials and business configuration
        data.update({
            'license_key': self.license_key,
            'database_uuid': self.database_uuid,
            'business_config': self._get_business_config()  # ← Client's settings
        })
        
        try:
            url = f"{self.proxy_url}{endpoint}"
            
            _logger.info("=" * 80)
            _logger.info(f"📡 CALLING PROXY API")
            _logger.info(f"🔗 URL: {url}")
            _logger.info(f"📤 Request data: {data}")
            _logger.info("=" * 80)
            
            # All proxy endpoints use JSON-RPC format (type='json' in Odoo)
            # Wrap request in JSON-RPC envelope
            payload = {
                'jsonrpc': '2.0',
                'method': 'call',
                'params': data,
                'id': 1
            }
            
            _logger.info(f"📤 Sending JSON-RPC payload: {payload}")
            
            response = requests.post(
                url,
                json=payload,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                timeout=120  # Increased for order processing
            )
            
            _logger.info(f"📥 Response content-type: {response.headers.get('Content-Type')}")
            
            _logger.info(f"📥 Response status code: {response.status_code}")
            _logger.info(f"📥 Response headers: {dict(response.headers)}")
            
            if response.status_code != 200:
                _logger.error(f"❌ Proxy returned error status: {response.status_code}")
                _logger.error(f"❌ Response text: {response.text[:500]}")  # Limit to 500 chars
                
                # Check if it's HTML (404 page)
                if response.text.strip().startswith('<!DOCTYPE') or response.text.strip().startswith('<html'):
                    raise UserError(_(
                        'Proxy endpoint not found. The zid_proxy module may not be installed or Odoo needs restart on production server.\n\n'
                        'Endpoint: %s\n'
                        'Status: %s'
                    ) % (url, response.status_code))
                else:
                    raise UserError(_('Proxy server error: %s') % response.text[:200])
            
            response_data = response.json()
            _logger.info(f"📥 Response JSON: {response_data}")
            
            # Handle JSON-RPC wrapped response
            result = response_data.get('result', response_data)
            _logger.info(f"📦 Extracted result: {result}")
            
            # Check for errors
            if result.get('error'):
                error_msg = result.get('error', 'Unknown error')
                _logger.error(f"❌ Proxy returned error: {error_msg}")
                raise UserError(_('Proxy processing error: %s') % error_msg)
            
            # Check for success field (if present)
            if 'success' in result and not result.get('success'):
                error_msg = result.get('error', 'Unknown error')
                _logger.error(f"❌ Proxy returned success=False: {error_msg}")
                raise UserError(_('Proxy processing error: %s') % error_msg)
            
            _logger.info("✅ Proxy API call successful")
            _logger.info("=" * 80)
            
            return result
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"❌ Proxy API call failed with exception: {str(e)}")
            import traceback
            _logger.error(traceback.format_exc())
            raise UserError(_('Failed to connect to proxy server: %s') % str(e))

    def action_validate_license(self):
        """Manual action to validate license"""
        self.ensure_one()
        self._compute_license_status()
        
        if self.license_valid:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('License Valid'),
                    'message': self.license_status_message,
                    'type': 'success',
                }
            }
        else:
            raise UserError(_(self.license_status_message))




    def action_view_orders(self):
        self.ensure_one()
        return {
            'name': _('Zid Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'zid.sale.order',
            'view_mode': 'list,form',
            'domain': [('zid_connector_id', '=', self.id)],
            'context': {'default_zid_connector_id': self.id},
        }

    def action_view_products(self):
        self.ensure_one()
        return {
            'name': _('Zid Products'),
            'type': 'ir.actions.act_window',
            'res_model': 'zid.product',
            'view_mode': 'list,kanban,form',
            'domain': [('zid_connector_id', '=', self.id)],
            'context': {'default_zid_connector_id': self.id},
        }
        
    def action_view_customers(self):
        self.ensure_one()
        return {
            'name': _('Customers'),
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'domain': [('company_id', '=', self.company_id.id)],
        }

    def action_open_settings(self):
        self.ensure_one()
        return {
            'name': _('Settings'),
            'type': 'ir.actions.act_window',
            'res_model': 'zid.connector',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_import_orders(self):
        self.ensure_one()
        return {
            'name': _('Import Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'zid.sale.order.connector',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_zid_connector_id': self.id},
        }


    def setup_webhooks(self):
        """Setup default webhooks for product and order sync"""
        self.ensure_one()

        if not self.is_connected:
            raise UserError(_('Please connect to Zid first'))

        webhook_model = self.env['zid.webhook']
        
        # Events to setup
        target_events = [
            ('product.create', 'Product Created'),
            ('order.create', 'Order Created'),
            ('order.status.update', 'Order Status Updated'),
        ]

        for event_code, event_name in target_events:
            existing = webhook_model.search([
                ('zid_connector_id', '=', self.id),
                ('event', '=', event_code)
            ])

            if not existing:
                # Create and register webhook
                webhook = webhook_model.create({
                    'zid_connector_id': self.id,
                    'event': event_code,
                    'is_active': True
                })
                try:
                    webhook.register_webhook()
                except Exception as e:
                    _logger.error(f"Failed to register webhook {event_code}: {str(e)}")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Webhooks configured and registered successfully'),
                'type': 'success',
            }
        }

    def list_zid_webhooks(self):
        """List all webhooks registered in Zid"""
        self.ensure_one()

        if not self.is_connected:
            raise UserError(_('Not connected to Zid'))

        try:
            response = self.api_request(
                endpoint='webhooks/',
                method='GET'
            )

            # Log the webhooks
            _logger.info(f"Zid webhooks: {json.dumps(response, indent=2)}")

            # Show in a message
            if response:
                webhook_list = json.dumps(response, indent=2)
                raise UserError(_('Registered Webhooks:\n%s') % webhook_list)
            else:
                raise UserError(_('No webhooks found'))

        except Exception as e:
            _logger.error(f"Failed to list webhooks: {str(e)}")
            raise







    def _compute_redirect_url(self):
        """Compute redirect URL from system base URL"""
        for record in self:
            record.redirect_url = "https://www.cloudmen.ae/api/zid/oauth/callback"

    @api.depends('authorization_status')
    def _compute_is_connected(self):
        """Check connection status - tokens are on proxy, not here"""
        for record in self:
            record.is_connected = (record.authorization_status == 'connected')

    # Token status is managed by proxy server

    @api.constrains('store_id')
    def _check_store_id(self):
        """Validate store ID is numeric"""
        for record in self:
            if record.store_id and not record.store_id.isdigit():
                raise ValidationError(_('Store ID must be numeric'))
    
    @api.constrains('proxy_url')
    def _check_proxy_url(self):
        """Validate proxy URL format"""
        for record in self:
            if record.proxy_url:
                if not record.proxy_url.startswith(('http://', 'https://')):
                    raise ValidationError(_('Proxy URL must start with http:// or https://'))
                if record.proxy_url.endswith('/'):
                    record.proxy_url = record.proxy_url.rstrip('/')

    def _fetch_store_info(self):
        """Fetch store information from Zid API through PROXY"""
        self.ensure_one()

        if not self.is_connected:
            _logger.warning("Cannot fetch store info - not connected")
            return

        try:
            _logger.info("Fetching store profile through proxy...")
            
            # Use secure proxy API call
            store_data = self.api_request('managers/account/profile', method='GET')
            
            if store_data:
                _logger.info(f"Store data received: {store_data.keys() if isinstance(store_data, dict) else 'not a dict'}")
                self._update_store_info(store_data)
                _logger.info("✅ Store information updated successfully")
            else:
                _logger.warning("⚠️ No store data received")

        except Exception as e:
            _logger.error(f"❌ Error fetching store info: {str(e)}")

    def _update_store_info(self, store_data):
        """Update store information from API response"""
        self.ensure_one()

        # Update store information based on Zid API response structure
        # This will be modified according to actual API response structure

        update_vals = {
            'last_sync_date': fields.Datetime.now()
        }

        if 'store' in store_data:
            store_info = store_data['store']
            update_vals.update({
                'store_name': store_info.get('name'),
                'store_url': store_info.get('url'),
                'store_email': store_info.get('email'),
                'store_currency': store_info.get('currency'),
                'store_id': str(store_info.get('id', ''))
            })

        self.write(update_vals)

    def test_connection(self):
        """Test API connection by making a simple API call"""
        self.ensure_one()

        if not self.is_connected:
            raise UserError(_('Please connect to Zid first'))

        try:
            # Make a simple API call to test connection
            result = self.api_request('managers/store', method='GET')
            
            if result:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Test Successful'),
                        'message': _('Successfully connected to Zid API'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(_('No response from Zid API'))
                
        except Exception as e:
            _logger.error(f"Connection test failed: {str(e)}")
            raise UserError(_('Connection test failed: %s') % str(e))

    def disconnect(self):
        """Disconnect from Zid - clears connection status only (tokens are on proxy)"""
        self.ensure_one()

        self.write({
            'authorization_status': 'not_connected',
            'connection_date': False,
            'store_name': False,
            'store_url': False,
            'store_email': False,
            'store_currency': False,
            'scopes': False,
            'last_sync_date': False,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Disconnected'),
                'message': _('Successfully disconnected from Zid. Note: To fully revoke access, disconnect from proxy server.'),
                'type': 'warning'
            }
        }

    def connect_to_zid(self):
        """Connect to Zid via proxy - fully automated"""
        self.ensure_one()
        
        _logger.info("=" * 80)
        _logger.info("🔵 CONNECT_TO_ZID CALLED")
        _logger.info(f"Connector ID: {self.id}")
        _logger.info(f"Connector Name: {self.app_name}")
        _logger.info(f"Store ID: {self.store_id}")
        _logger.info(f"License Key: {'***' + self.license_key[-4:] if self.license_key else 'NOT SET'}")
        _logger.info(f"Proxy URL: {self.proxy_url}")
        _logger.info(f"Current Status: {self.authorization_status}")
        _logger.info("=" * 80)
        
        if not self.store_id:
            _logger.error("❌ Store ID is missing")
            raise UserError(_('Please enter Store ID before connecting'))
        
        if not self.license_key or not self.proxy_url:
            _logger.error("❌ License Key or Proxy URL is missing")
            raise UserError(_('Please configure License Key and Proxy URL first'))
        
        try:
            # Get the base URL of this Odoo instance
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            callback_url = f"{base_url}/zid/callback"
            
            _logger.info(f"📍 Base URL: {base_url}")
            _logger.info(f"📍 Callback URL: {callback_url}")
            
            # Prepare request data
            request_data = {
                'store_id': self.store_id,
                'connector_id': self.id,
                'callback_url': callback_url,
            }
            
            _logger.info(f"📤 Sending to proxy: {request_data}")
            
            # Call proxy to initiate connection
            result = self.call_proxy_api('/api/zid/connect-store', request_data)
            
            _logger.info(f"📥 Proxy response received:")
            _logger.info(f"   - connected: {result.get('connected')}")
            _logger.info(f"   - requires_authorization: {result.get('requires_authorization')}")
            _logger.info(f"   - auth_url present: {bool(result.get('auth_url'))}")
            _logger.info(f"   - message: {result.get('message')}")
            
            if result.get('connected'):
                _logger.info("✅ Already connected!")
                # Already connected
                self.write({
                    'authorization_status': 'connected',
                    'connection_date': fields.Datetime.now(),
                    'store_name': result.get('store_name'),
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Already Connected'),
                        'message': _('Store is already connected to Zid'),
                        'type': 'success',
                    }
                }
            
            if result.get('requires_authorization'):
                # Need to authorize - open Zid auth page
                auth_url = result.get('auth_url')
                
                _logger.info(f"🔐 Authorization required")
                _logger.info(f"🔗 Auth URL: {auth_url}")
                
                if not auth_url:
                    _logger.error("❌ No auth_url in response!")
                    raise UserError(_('No authorization URL received from proxy'))
                
                # Show notification with instructions
                self.message_post(
                    body=_('''<p><strong>Authorization Required</strong></p>
                    <p>Please follow these steps:</p>
                    <ol>
                        <li>Click OK to open the Zid authorization page</li>
                        <li>Log in to your Zid account and authorize the app</li>
                        <li>After authorization, return to Odoo and click "Refresh Connection Status"</li>
                    </ol>'''),
                    subject=_('Zid Connection - Action Required'),
                    message_type='notification'
                )
                
                _logger.info("✅ Returning action to open auth URL")
                
                return {
                    'type': 'ir.actions.act_url',
                    'url': auth_url,
                    'target': 'new',
                }
            
            _logger.error(f"❌ Unexpected response from proxy: {result}")
            raise UserError(_('Unexpected response from proxy'))
            
        except Exception as e:
            _logger.error(f"❌ Connection failed with exception: {str(e)}")
            import traceback
            _logger.error(traceback.format_exc())
            raise UserError(_('Failed to connect: %s') % str(e))
    
    def check_zid_connection(self):
        """Check connection status with proxy"""
        self.ensure_one()
        
        _logger.info("=" * 80)
        _logger.info("🔍 CHECK_ZID_CONNECTION CALLED")
        _logger.info(f"Connector ID: {self.id}")
        _logger.info(f"Connector Name: {self.app_name}")
        _logger.info(f"Store ID: {self.store_id}")
        _logger.info(f"Current Status: {self.authorization_status}")
        _logger.info("=" * 80)
        
        if not self.license_key or not self.proxy_url:
            _logger.error("❌ License Key or Proxy URL is missing")
            raise UserError(_('Please configure License Key and Proxy URL first'))
        
        try:
            request_data = {
                'store_id': self.store_id,
                'connector_id': self.id,
            }
            
            _logger.info(f"📤 Checking connection with proxy: {request_data}")
            
            result = self.call_proxy_api('/api/zid/check-connection', request_data)
            
            _logger.info(f"📥 Check connection response:")
            _logger.info(f"   - connected: {result.get('connected')}")
            _logger.info(f"   - store_name: {result.get('store_name')}")
            _logger.info(f"   - message: {result.get('message')}")
            _logger.info(f"   - Full result: {result}")
            
            if result.get('connected'):
                _logger.info("✅ Connection confirmed!")
                
                # Get store info from proxy response
                store_name = result.get('store_name') or f'Zid Store {self.store_id}'
                store_url = result.get('store_url') or ''
                
                # Update connection details
                self.write({
                    'authorization_status': 'connected',
                    'store_name': store_name,
                    'store_url': store_url,
                    'connection_date': fields.Datetime.now(),
                })
                
                self.message_post(
                    body=_('Successfully connected to Zid store: %s') % store_name,
                    subject=_('Connection Successful')
                )
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connected!'),
                        'message': _('Successfully connected to Zid store: %s') % store_name,
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                _logger.warning("⚠️ Not connected yet")
                self.authorization_status = 'not_connected'
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Not Connected'),
                        'message': _('Store is not yet authorized. Please complete the authorization process in Zid.'),
                        'type': 'warning',
                        'sticky': False,
                    }
                }
                
        except Exception as e:
            _logger.error(f"Check connection failed: {str(e)}")
            return False

    # Token refresh and expiry check handled automatically by proxy server

    def api_request(self, endpoint, method='GET', data=None, params=None):
        """Make authenticated API request to Zid through PROXY (SECURE)"""
        self.ensure_one()

        if not self.license_key or not self.proxy_url:
            raise UserError(_('Proxy not configured. Please configure License Key and Proxy URL.'))

        # ALL API calls go through proxy - tokens never exposed to client
        try:
            # Use the existing /api/zid/request endpoint (should exist on production)
            result = self.call_proxy_api('/api/zid/request', {
                'endpoint': endpoint,
                'method': method,
                'data': data,
                'params': params,
                'store_id': self.store_id,
            })
            
            if result.get('error'):
                raise UserError(_('API Error: %s') % result.get('error'))
            
            return result.get('data', {})
            
        except Exception as e:
            _logger.error(f"Proxy API request failed: {str(e)}")
            raise UserError(_('API request failed: %s') % str(e))


    # --------------------- Locations ------------------------------

    zid_location_ids = fields.One2many(
        'zid.location',
        'zid_connector_id',
        string='Zid Locations'
    )

    zid_locations_count = fields.Integer(
        string='Locations Count',
        compute='_compute_locations_count'
    )

    zid_locations_response = fields.Text(
        string='Locations Response',
        readonly=True,
        help='Last locations API response from Zid'
    )

    default_location_id = fields.Many2one(
        'zid.location',
        string='Default Location',
        compute='_compute_default_location',
        store=True
    )

    @api.depends('zid_location_ids')
    def _compute_locations_count(self):
        for connector in self:
            connector.zid_locations_count = len(connector.zid_location_ids)

    @api.depends('zid_location_ids', 'zid_location_ids.is_default')
    def _compute_default_location(self):
        for connector in self:
            default = connector.zid_location_ids.filtered('is_default')
            connector.default_location_id = default[0] if default else False

    def update_order_status(self, zid_order_id, status_code):
        """Update order status in Zid"""
        self.ensure_one()
        
        if not self.is_connected:
            _logger.warning("Cannot update order status - not connected")
            return False
            
        try:
            endpoint = f"managers/store/orders/{zid_order_id}/change-order-status"
            payload = {'order_status': status_code}
            
            response = self.api_request(
                endpoint=endpoint,
                method='POST',
                data=payload
            )
            
            _logger.info(f"Updated Zid order {zid_order_id} status to {status_code}")
            return True
            
        except Exception as e:
            _logger.error(f"Failed to update Zid order status: {str(e)}")
            return False

    def get_zid_locations(self):
        """Fetch locations from Zid API"""
        self.ensure_one()

        if not self.is_connected:
            raise UserError(_('Not connected to Zid. Please connect first.'))

        try:
            # Use generic request endpoint (should exist on production)
            result = self.call_proxy_api('/api/zid/request', {
                'endpoint': 'locations/',
                'method': 'GET',
                'store_id': self.store_id,
            })
            
            if result.get('error'):
                raise UserError(_('Failed to fetch locations: %s') % result.get('error'))
            
            response = result.get('data', {})

            # Log the response type and content for debugging
            _logger.info(f"Zid locations response type: {type(response)}")
            _logger.info(f"Zid locations response: {response}")

            # Save raw response
            self.zid_locations_response = json.dumps(response, indent=2)

            # Handle different response formats
            locations_list = []

            if isinstance(response, dict):
                # Response might be wrapped in an object
                if 'locations' in response:
                    locations_list = response.get('locations', [])
                elif 'data' in response:
                    locations_list = response.get('data', [])
                elif 'results' in response:
                    locations_list = response.get('results', [])
                else:
                    # If response is a single location, wrap it in a list
                    if response.get('id'):
                        locations_list = [response]
                    else:
                        _logger.warning(f"Unknown response structure: {response.keys()}")
                        # Try to handle paginated response
                        for key in response.keys():
                            if isinstance(response[key], list):
                                locations_list = response[key]
                                break
            elif isinstance(response, list):
                locations_list = response
            else:
                _logger.error(f"Unexpected response type: {type(response)}")
                raise UserError(_('Unexpected response format from Zid API'))

            # Create or update locations
            if locations_list:
                self.create_zid_locations(locations_list)

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success!'),
                        'message': _('Fetched %d locations from Zid') % len(locations_list),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                # Even if no locations, it's not an error
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Info'),
                        'message': _('No locations found in Zid'),
                        'type': 'info',
                        'sticky': False,
                    }
                }

        except Exception as e:
            _logger.error(f"Failed to fetch Zid locations: {str(e)}")
            raise UserError(_('Failed to fetch locations from Zid: %s') % str(e))

    def test_get_locations(self):
        """Test fetching locations - for debugging"""
        self.ensure_one()

        if not self.is_connected:
            raise UserError(_('Not connected to Zid. Please connect first.'))

        try:
            # Make API request
            response = self.api_request(
                endpoint='locations/',
                method='GET'
            )

            # Save and display response
            self.zid_locations_response = json.dumps(response, indent=2)

            # Show the response structure
            message = f"""
            Response Type: {type(response)}
            Response Keys: {response.keys() if isinstance(response, dict) else 'N/A (List)'}
            Response Length: {len(response) if isinstance(response, (list, dict)) else 'N/A'}
            """

            raise UserError(_(message))

        except Exception as e:
            _logger.error(f"Test locations error: {str(e)}")
            raise


    def create_zid_locations(self, locations_data):
        """Create or update Zid location records"""
        self.ensure_one()

        if not locations_data:
            return

        location_model = self.env['zid.location']
        created_count = 0
        updated_count = 0

        for location_data in locations_data:
            try:
                # Check if location exists
                existing = location_model.search([
                    ('zid_location_id', '=', location_data.get('id')),
                    ('zid_connector_id', '=', self.id)
                ], limit=1)

                if existing:
                    existing.write(location_model._prepare_location_values(location_data, self.id))
                    updated_count += 1
                else:
                    location_model.create_or_update_from_zid(location_data, self.id)
                    created_count += 1

            except Exception as e:
                _logger.error(f"Failed to create/update location {location_data.get('id')}: {str(e)}")
                continue

        _logger.info(f"Created {created_count} new locations, updated {updated_count} existing locations")

        return True

    def action_view_locations(self):
        """Open locations list view"""
        self.ensure_one()
        return {
            'name': _('Zid Locations'),
            'type': 'ir.actions.act_window',
            'res_model': 'zid.location',
            'view_mode': 'tree,form',
            'domain': [('zid_connector_id', '=', self.id)],
            'context': {'default_zid_connector_id': self.id},
        }

    def action_import_orders(self):
        """Open import orders wizard"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'zid.sale.order.connector',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_zid_connector_id': self.id,
            }
        }

    def action_import_variants(self):
        """Open import variants wizard"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'zid.variant.connector',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_zid_connector_id': self.id,
            }
        }



    def action_reverse_reason_sync(self):
        """Open import orders wizard"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'zid.reverse.reason.sync',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_zid_connector_id': self.id,
            }
        }

    def action_reverse_waybill_create(self):
        """Open import orders wizard"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'zid.reverse.waybill.create',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_zid_connector_id': self.id,
            }
        }

    def action_import_attributes(self):
        """Open import attributes wizard"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'zid.attribute.connector',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_zid_connector_id': self.id,
            }
        }

    def action_sync_products(self):
        """Sync products from Zid"""
        self.ensure_one()
        
        if not self.is_connected:
            raise UserError(_('Please connect to Zid first'))
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'zid.product.sync.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_zid_connector_id': self.id,
            }
        }

    def action_update_stock(self):
        """Update stock to Zid"""
        self.ensure_one()
        
        if not self.is_connected:
            raise UserError(_('Please connect to Zid first'))
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'zid.stock.update.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_zid_connector_id': self.id,
            }
        }







    def update_last_sync_date(self):
        """Update the last sync date - call this after successful sync operations"""
        self.ensure_one()
        self.write({'last_sync_date': fields.Datetime.now()})
        _logger.info(f"Updated last_sync_date for connector {self.name}")

    def action_sync_health_report(self):
        """Open sync health report wizard"""
        self.ensure_one()
        
        wizard = self.env['zid.health.report.wizard'].create({
            'connector_id': self.id,
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sync Health Report'),
            'res_model': 'zid.health.report.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_bulk_sync_all(self):
        """Open bulk sync wizard"""
        self.ensure_one()
        
        if not self.is_connected:
            raise UserError(_('Connector is not connected'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bulk Sync All Data'),
            'res_model': 'zid.bulk.sync.wizard',
            'res_id': False,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_connector_id': self.id,
                'default_sync_products': True,
                'default_sync_orders': True,
                'default_sync_customers': True,
                'default_sync_stock': True,
            }
        }

    def action_reset_sync_locks(self):
        """Reset all synchronization locks for this connector"""
        self.ensure_one()
        self.write({
            'order_import_in_progress': False,
            'order_import_started_at': False,
            'product_import_in_progress': False,
            'product_import_started_at': False,
            'order_status_sync_in_progress': False,
            'order_status_sync_started_at': False,
        })
        _logger.info(f"Manually reset synchronization locks for connector: {self.app_name}")
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Locks Reset'),
                'message': _('Synchronization locks for %s have been reset.') % self.app_name,
                'type': 'success',
            }
        }

    def _check_and_reset_expired_locks(self):
        """Check for expired locks and reset them automatically"""
        self.ensure_one()
        
        if not self.import_timeout_minutes or self.import_timeout_minutes <= 0:
            return False  # No timeout configured
        
        now = fields.Datetime.now()
        timeout_delta = timedelta(minutes=self.import_timeout_minutes)
        reset_count = 0
        
        # Check order import lock
        if (self.order_import_in_progress and self.order_import_started_at and 
            (now - self.order_import_started_at) > timeout_delta):
            _logger.warning(f"Order import lock expired for connector {self.app_name}, auto-resetting")
            self.order_import_in_progress = False
            self.order_import_started_at = False
            reset_count += 1
        
        # Check product import lock
        if (self.product_import_in_progress and self.product_import_started_at and 
            (now - self.product_import_started_at) > timeout_delta):
            _logger.warning(f"Product import lock expired for connector {self.app_name}, auto-resetting")
            self.product_import_in_progress = False
            self.product_import_started_at = False
            reset_count += 1
        
        # Check order status sync lock
        if (self.order_status_sync_in_progress and self.order_status_sync_started_at and 
            (now - self.order_status_sync_started_at) > timeout_delta):
            _logger.warning(f"Order status sync lock expired for connector {self.app_name}, auto-resetting")
            self.order_status_sync_in_progress = False
            self.order_status_sync_started_at = False
            reset_count += 1
        
        if reset_count > 0:
            _logger.info(f"Auto-reset {reset_count} expired locks for connector {self.app_name}")
        
        return reset_count > 0

    def _set_import_lock(self, lock_type):
        """Set import lock with timestamp"""
        self.ensure_one()
        now = fields.Datetime.now()
        
        if lock_type == 'order':
            self.write({
                'order_import_in_progress': True,
                'order_import_started_at': now
            })
        elif lock_type == 'product':
            self.write({
                'product_import_in_progress': True,
                'product_import_started_at': now
            })
        elif lock_type == 'status':
            self.write({
                'order_status_sync_in_progress': True,
                'order_status_sync_started_at': now
            })
    
    def _release_import_lock(self, lock_type):
        """Release import lock and clear timestamp"""
        self.ensure_one()
        
        if lock_type == 'order':
            self.write({
                'order_import_in_progress': False,
                'order_import_started_at': False
            })
        elif lock_type == 'product':
            self.write({
                'product_import_in_progress': False,
                'product_import_started_at': False
            })
        elif lock_type == 'status':
            self.write({
                'order_status_sync_in_progress': False,
                'order_status_sync_started_at': False
            })

    @api.model
    def cron_check_expired_locks(self):
        """Cron job to check and reset expired import locks"""
        _logger.info("Checking for expired import locks...")
        
        connectors = self.search([
            '|', '|',
            ('order_import_in_progress', '=', True),
            ('product_import_in_progress', '=', True),
            ('order_status_sync_in_progress', '=', True)
        ])
        
        total_reset = 0
        for connector in connectors:
            if connector._check_and_reset_expired_locks():
                total_reset += 1
        
        if total_reset > 0:
            _logger.info(f"Auto-reset expired locks for {total_reset} connectors")
        else:
            _logger.info("No expired locks found")
        
        return total_reset
