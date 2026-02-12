from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class ZidSetupWizard(models.TransientModel):
    _name = 'zid.setup.wizard'
    _description = 'Zid Integration Setup Wizard'

    # Step tracking
    step = fields.Selection([
        ('welcome', 'Welcome'),
        ('connector', 'Connector Setup'),
        ('connection', 'Connection Test'),
        ('configuration', 'Configuration'),
        ('complete', 'Complete')
    ], default='welcome', string='Step')

    # Connector fields
    store_id = fields.Char(
        string='Store ID',
        help='Your Zid Store ID (numeric)'
    )
    proxy_url = fields.Char(
        string='Proxy URL',
        default='https://www.cloudmen.ae',
        help='Zid Proxy Server URL'
    )
    license_key = fields.Char(
        string='License Key',
        help='Your Zid Integration License Key'
    )
    
    # Configuration fields
    import_products = fields.Boolean(
        string='Import Products',
        default=True,
        help='Import products from Zid during setup'
    )
    import_customers = fields.Boolean(
        string='Import Customers',
        default=True,
        help='Import customers from Zid during setup'
    )
    import_orders = fields.Boolean(
        string='Import Orders',
        default=False,
        help='Import recent orders from Zid during setup'
    )
    
    # Business configuration
    customer_match_by = fields.Selection([
        ('email', 'Email'),
        ('mobile', 'Mobile'),
        ('email_mobile', 'Email or Mobile')
    ], default='email', string='Match Customers By')
    
    product_match_by = fields.Selection([
        ('sku', 'SKU'),
        ('barcode', 'Barcode'),
        ('name', 'Name')
    ], default='sku', string='Match Products By')
    
    auto_confirm_orders = fields.Boolean(
        string='Auto Confirm Orders',
        default=False,
        help='Automatically confirm orders imported from Zid'
    )
    
    # Results
    connector_id = fields.Many2one('zid.connector', string='Created Connector')
    setup_complete = fields.Boolean(default=False)
    
    @api.constrains('store_id')
    def _check_store_id(self):
        for record in self:
            if record.store_id and not record.store_id.isdigit():
                raise ValidationError(_('Store ID must be numeric'))
    
    @api.constrains('proxy_url')
    def _check_proxy_url(self):
        for record in self:
            if record.proxy_url:
                if not record.proxy_url.startswith(('http://', 'https://')):
                    raise ValidationError(_('Proxy URL must start with http:// or https://'))
    
    def action_next_step(self):
        """Move to next step"""
        self.ensure_one()
        
        if self.step == 'welcome':
            self.step = 'connector'
        elif self.step == 'connector':
            self._validate_connector_data()
            self._create_connector()
            self.step = 'connection'
        elif self.step == 'connection':
            self._test_connection()
            self.step = 'configuration'
        elif self.step == 'configuration':
            self._apply_configuration()
            self.step = 'complete'
            self.setup_complete = True
        
        return self._return_wizard()
    
    def action_previous_step(self):
        """Move to previous step"""
        self.ensure_one()
        
        if self.step == 'connector':
            self.step = 'welcome'
        elif self.step == 'connection':
            self.step = 'connector'
        elif self.step == 'configuration':
            self.step = 'connection'
        elif self.step == 'complete':
            self.step = 'configuration'
        
        return self._return_wizard()
    
    def _validate_connector_data(self):
        """Validate connector data"""
        if not self.store_id:
            raise UserError(_('Store ID is required'))
        if not self.proxy_url:
            raise UserError(_('Proxy URL is required'))
        if not self.license_key:
            raise UserError(_('License Key is required'))
    
    def _create_connector(self):
        """Create Zid connector"""
        if self.connector_id:
            # Update existing
            self.connector_id.write({
                'store_id': self.store_id,
                'proxy_url': self.proxy_url.rstrip('/'),
                'license_key': self.license_key,
            })
        else:
            # Create new
            self.connector_id = self.env['zid.connector'].create({
                'name': f'Zid Store {self.store_id}',
                'store_id': self.store_id,
                'proxy_url': self.proxy_url.rstrip('/'),
                'license_key': self.license_key,
                'active': True,
            })
    
    def _test_connection(self):
        """Test connection to Zid"""
        if not self.connector_id:
            raise UserError(_('No connector created'))
        
        try:
            # Try to connect
            result = self.connector_id.connect_to_zid()
            if not self.connector_id.is_connected:
                raise UserError(_('Connection failed. Please check your credentials.'))
        except Exception as e:
            raise UserError(_('Connection test failed: %s') % str(e))
    
    def _apply_configuration(self):
        """Apply business configuration"""
        if not self.connector_id:
            return
        
        # Update connector configuration
        self.connector_id.write({
            'customer_match_by': self.customer_match_by,
            'product_match_by': self.product_match_by,
            'auto_confirm_orders': self.auto_confirm_orders,
        })
    
    def action_import_data(self):
        """Import initial data"""
        self.ensure_one()
        
        if not self.connector_id or not self.connector_id.is_connected:
            raise UserError(_('Please complete the connection setup first'))
        
        actions = []
        
        try:
            if self.import_products:
                # Open products import wizard
                actions.append({
                    'name': _('Import Products'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'zid.products.connector',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_zid_connector_id': self.connector_id.id,
                        'default_import_mode': 'new_and_update',
                        'default_update_images': True,
                    }
                })
            
            if self.import_customers:
                # Open customer sync wizard
                actions.append({
                    'name': _('Import Customers'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'zid.customer.sync.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_zid_connector_id': self.connector_id.id,
                    }
                })
            
            if self.import_orders:
                # Open order import wizard
                actions.append({
                    'name': _('Import Orders'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'zid.sale.order.connector',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_zid_connector_id': self.connector_id.id,
                    }
                })
            
            if actions:
                # Return first action, others can be accessed from menus
                return actions[0]
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Setup Complete'),
                        'message': _('Zid integration setup completed successfully!'),
                        'type': 'success',
                    }
                }
        
        except Exception as e:
            _logger.error(f"Setup import failed: {str(e)}")
            raise UserError(_('Import failed: %s') % str(e))
    
    def action_finish_setup(self):
        """Finish setup and go to connector"""
        self.ensure_one()
        
        if self.connector_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Zid Connector'),
                'res_model': 'zid.connector',
                'res_id': self.connector_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Zid Connectors'),
                'res_model': 'zid.connector',
                'view_mode': 'list,form',
                'target': 'current',
            }
    
    def _return_wizard(self):
        """Return to wizard view"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Zid Integration Setup'),
            'res_model': 'zid.setup.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
