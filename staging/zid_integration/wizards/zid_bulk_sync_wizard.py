from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ZidBulkSyncWizard(models.TransientModel):
    _name = 'zid.bulk.sync.wizard'
    _description = 'Bulk Sync All Data from Zid'

    connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        domain=[('authorization_status', '=', 'connected')]
    )

    # Sync Options
    sync_products = fields.Boolean(
        string='Sync Products',
        default=True,
        help='Import/update products from Zid'
    )

    sync_orders = fields.Boolean(
        string='Sync Orders',
        default=True,
        help='Import/update orders from Zid'
    )

    sync_customers = fields.Boolean(
        string='Sync Customers',
        default=True,
        help='Import/update customers from Zid'
    )

    sync_stock = fields.Boolean(
        string='Sync Stock Levels',
        default=True,
        help='Update stock quantities from Zid'
    )

    sync_categories = fields.Boolean(
        string='Sync Categories',
        default=False,
        help='Import/update product categories'
    )

    sync_attributes = fields.Boolean(
        string='Sync Attributes',
        default=False,
        help='Import/update product attributes'
    )

    # Date Range
    use_date_range = fields.Boolean(
        string='Use Date Range',
        default=False,
        help='Only sync data modified within date range'
    )

    date_from = fields.Datetime(
        string='From Date',
        help='Sync data modified after this date'
    )

    date_to = fields.Datetime(
        string='To Date',
        default=fields.Datetime.now,
        help='Sync data modified before this date'
    )

    # Progress
    state = fields.Selection([
        ('draft', 'Draft'),
        ('syncing', 'Syncing'),
        ('done', 'Done'),
        ('error', 'Error')
    ], default='draft', string='Status')

    progress_log = fields.Text(
        string='Progress Log',
        readonly=True
    )

    # Results
    products_synced = fields.Integer(string='Products Synced', readonly=True)
    orders_synced = fields.Integer(string='Orders Synced', readonly=True)
    customers_synced = fields.Integer(string='Customers Synced', readonly=True)
    stock_synced = fields.Integer(string='Stock Items Synced', readonly=True)
    errors_count = fields.Integer(string='Errors', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_connector_id'):
            res['connector_id'] = self.env.context['default_connector_id']
        return res

    def action_start_sync(self):
        """Start bulk synchronization"""
        self.ensure_one()

        if not self.connector_id.is_connected:
            raise UserError(_('Connector is not connected to Zid'))

        if not any([self.sync_products, self.sync_orders, self.sync_customers, 
                    self.sync_stock, self.sync_categories, self.sync_attributes]):
            raise UserError(_('Please select at least one sync option'))

        self.state = 'syncing'
        self.progress_log = _('Starting bulk synchronization...\n\n')
        self.products_synced = 0
        self.orders_synced = 0
        self.customers_synced = 0
        self.stock_synced = 0
        self.errors_count = 0

        try:
            # Sync Categories first (if enabled)
            if self.sync_categories:
                self._sync_categories()

            # Sync Attributes (if enabled)
            if self.sync_attributes:
                self._sync_attributes()

            # Sync Products
            if self.sync_products:
                self._sync_products()

            # Sync Customers
            if self.sync_customers:
                self._sync_customers()

            # Sync Orders
            if self.sync_orders:
                self._sync_orders()

            # Sync Stock
            if self.sync_stock:
                self._sync_stock()

            self.state = 'done'
            self._add_log(_('\n✅ Bulk synchronization completed successfully!'))

            return self._return_wizard()

        except Exception as e:
            self.state = 'error'
            self.errors_count += 1
            self._add_log(_('\n❌ Bulk synchronization failed: %s') % str(e))
            _logger.error(f"Bulk sync failed: {str(e)}", exc_info=True)
            raise UserError(_('Bulk synchronization failed: %s') % str(e))

    def _sync_categories(self):
        """Sync product categories"""
        self._add_log(_('📁 Syncing Categories...\n'))
        try:
            # Fetch categories from Zid
            response = self.connector_id.api_request(
                endpoint='categories/',
                method='GET'
            )

            if response and isinstance(response, dict):
                categories = response.get('results', [])
                count = 0

                for category_data in categories:
                    try:
                        self.env['zid.product.category'].create_or_update_from_zid(
                            category_data,
                            self.connector_id.id
                        )
                        count += 1
                    except Exception as e:
                        _logger.error(f"Failed to sync category: {str(e)}")
                        self.errors_count += 1

                self._add_log(_('  ✓ Synced %d categories\n') % count)

        except Exception as e:
            self._add_log(_('  ✗ Category sync failed: %s\n') % str(e))
            _logger.error(f"Category sync failed: {str(e)}")
            self.errors_count += 1

    def _sync_attributes(self):
        """Sync product attributes"""
        self._add_log(_('🏷️  Syncing Attributes...\n'))
        try:
            # Create wizard context
            wizard = self.env['zid.attribute.connector'].create({
                'zid_connector_id': self.connector_id.id,
            })

            # Execute sync
            wizard.action_fetch_attributes()
            self._add_log(_('  ✓ Attributes synced\n'))

        except Exception as e:
            self._add_log(_('  ✗ Attribute sync failed: %s\n') % str(e))
            _logger.error(f"Attribute sync failed: {str(e)}")
            self.errors_count += 1

    def _sync_products(self):
        """Sync products"""
        self._add_log(_('📦 Syncing Products...\n'))
        try:
            # Create products connector wizard
            wizard = self.env['zid.products.connector'].create({
                'zid_connector_id': self.connector_id.id,
                'import_mode': 'new_and_update',
                'update_images': True,
                'update_stock': False,  # Stock synced separately
            })

            # Execute import
            wizard.action_import_products()

            # Count synced products
            self.products_synced = len(self.env['zid.product'].search([
                ('zid_connector_id', '=', self.connector_id.id),
                ('write_date', '>=', self.create_date)
            ]))

            self._add_log(_('  ✓ Synced %d products\n') % self.products_synced)

        except Exception as e:
            self._add_log(_('  ✗ Product sync failed: %s\n') % str(e))
            _logger.error(f"Product sync failed: {str(e)}")
            self.errors_count += 1

    def _sync_customers(self):
        """Sync customers"""
        self._add_log(_('👥 Syncing Customers...\n'))
        try:
            # Create customer sync wizard
            wizard = self.env['zid.customer.sync.wizard'].create({
                'zid_connector_id': self.connector_id.id,
            })

            # Execute sync
            wizard.action_sync_customers()

            # Count synced customers
            self.customers_synced = len(self.env['res.partner'].search([
                ('create_date', '>=', self.create_date),
                ('customer_rank', '>', 0)
            ]))

            self._add_log(_('  ✓ Synced %d customers\n') % self.customers_synced)

        except Exception as e:
            self._add_log(_('  ✗ Customer sync failed: %s\n') % str(e))
            _logger.error(f"Customer sync failed: {str(e)}")
            self.errors_count += 1

    def _sync_orders(self):
        """Sync orders"""
        self._add_log(_('🛒 Syncing Orders...\n'))
        try:
            # Create order connector wizard
            wizard_vals = {
                'zid_connector_id': self.connector_id.id,
                'import_mode': 'all',
            }

            if self.use_date_range:
                wizard_vals.update({
                    'date_from': self.date_from,
                    'date_to': self.date_to,
                })

            wizard = self.env['zid.sale.order.connector'].create(wizard_vals)

            # Execute import
            wizard.action_start_import()

            # Count synced orders
            self.orders_synced = len(self.env['zid.sale.order'].search([
                ('zid_connector_id', '=', self.connector_id.id),
                ('write_date', '>=', self.create_date)
            ]))

            self._add_log(_('  ✓ Synced %d orders\n') % self.orders_synced)

        except Exception as e:
            self._add_log(_('  ✗ Order sync failed: %s\n') % str(e))
            _logger.error(f"Order sync failed: {str(e)}")
            self.errors_count += 1

    def _sync_stock(self):
        """Sync stock levels"""
        self._add_log(_('📊 Syncing Stock Levels...\n'))
        try:
            # Get all products with Zid mapping
            products = self.env['product.template'].search([
                ('zid_connector_id', '=', self.connector_id.id),
                ('zid_product_id', '!=', False)
            ])

            count = 0
            for product in products:
                try:
                    # Sync stock for this product
                    product.action_sync_stock_from_zid()
                    count += 1
                except Exception as e:
                    _logger.error(f"Failed to sync stock for product {product.name}: {str(e)}")
                    self.errors_count += 1

            self.stock_synced = count
            self._add_log(_('  ✓ Synced stock for %d products\n') % count)

        except Exception as e:
            self._add_log(_('  ✗ Stock sync failed: %s\n') % str(e))
            _logger.error(f"Stock sync failed: {str(e)}")
            self.errors_count += 1

    def _add_log(self, message):
        """Add message to progress log"""
        if not self.progress_log:
            self.progress_log = ''
        self.progress_log += message
        _logger.info(message.strip())

    def _return_wizard(self):
        """Return to wizard view"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_view_results(self):
        """View sync results"""
        self.ensure_one()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sync Results'),
                'message': _(
                    'Products: %d | Orders: %d | Customers: %d | Stock: %d | Errors: %d'
                ) % (
                    self.products_synced,
                    self.orders_synced,
                    self.customers_synced,
                    self.stock_synced,
                    self.errors_count
                ),
                'type': 'success' if self.errors_count == 0 else 'warning',
                'sticky': True,
            }
        }
