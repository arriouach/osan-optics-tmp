from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import json

_logger = logging.getLogger(__name__)

class ZidAbandonedCart(models.Model):
    _name = 'zid.abandoned.cart'
    _description = 'Zid Abandoned Cart'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'customer_name'
    _order = 'date_abandoned desc'

    # Connection
    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        ondelete='cascade'
    )

    # Cart Details
    zid_cart_id = fields.Char(
        string='Zid Cart ID',
        required=True,
        readonly=True
    )

    date_abandoned = fields.Datetime(
        string='Date Abandoned',
        readonly=True
    )
    
    currency_code = fields.Char(string='Currency', readonly=True)
    total_amount = fields.Float(string='Total Amount', readonly=True)
    
    # Customer
    customer_id = fields.Integer(string='Zid Customer ID', readonly=True)
    customer_name = fields.Char(string='Customer Name', readonly=True)
    customer_email = fields.Char(string='Customer Email', readonly=True)
    customer_mobile = fields.Char(string='Customer Mobile', readonly=True)
    
    # Odoo Customer Link
    partner_id = fields.Many2one(
        'res.partner',
        string='Odoo Customer',
        help='Linked Odoo customer'
    )

    # Lines
    cart_lines_data = fields.Text(string='Cart Lines (JSON)', readonly=True)
    
    # Recovery
    cart_url = fields.Char(string='Recovery URL', readonly=True)
    recovery_status = fields.Selection([
        ('new', 'New'),
        ('email_sent', 'Email Sent'),
        ('converted', 'Converted'),
        ('lost', 'Lost')
    ], string='Recovery Status', default='new', tracking=True)

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Converted Order',
        readonly=True
    )

    def action_fetch_abandoned_carts(self):
        """Fetch abandoned carts from Zid - opens wizard"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fetch Abandoned Carts'),
            'res_model': 'zid.abandoned.cart.fetch.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_zid_connector_id': self.zid_connector_id.id if hasattr(self, 'zid_connector_id') else False,
            }
        }

    def action_create_quotation(self):
        """Convert abandoned cart to Odoo Quotation"""
        self.ensure_one()
        if self.sale_order_id:
            raise UserError(_('This cart has already been converted to an order.'))

        # logic to create SO
        # 1. Ensure partner
        if not self.partner_id:
            self._find_or_create_partner()
            
        # 2. Create SO Header
        vals = {
            'partner_id': self.partner_id.id,
            'state': 'draft',
            'note': f"Recovered from Zid Abandoned Cart {self.zid_cart_id}"
        }
        order = self.env['sale.order'].create(vals)
        
        # 3. Create Lines (simplified)
        try:
            lines = json.loads(self.cart_lines_data)
            for line in lines:
                product_data = line.get('product', {})
                sku = product_data.get('sku')
                
                product = self.env['product.product'].search([('default_code', '=', sku)], limit=1)
                if not product:
                    continue # Skip or log warning
                    
                self.env['sale.order.line'].create({
                    'order_id': order.id,
                    'product_id': product.id,
                    'product_uom_qty': line.get('quantity', 1),
                    'price_unit': line.get('price', 0)
                })
        except Exception as e:
            _logger.error(f"Failed to parse lines: {e}")
            
        self.sale_order_id = order.id
        self.recovery_status = 'converted'
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': order.id,
            'view_mode': 'form',
            'target': 'current'
        }

    def _find_or_create_partner(self):
        """Helper to find or create partner from cart data"""
        self.ensure_one()
        
        if self.partner_id:
            return self.partner_id
        
        # Try to find by email
        if self.customer_email:
            partner = self.env['res.partner'].search([
                ('email', '=', self.customer_email)
            ], limit=1)
            if partner:
                self.partner_id = partner
                return partner
        
        # Try to find by mobile
        if self.customer_mobile:
            partner = self.env['res.partner'].search([
                ('mobile', '=', self.customer_mobile)
            ], limit=1)
            if partner:
                self.partner_id = partner
                return partner
        
        # Create new partner
        partner_vals = {
            'name': self.customer_name or self.customer_email or 'Unknown Customer',
            'email': self.customer_email,
            'mobile': self.customer_mobile,
            'customer_rank': 1,
        }
        partner = self.env['res.partner'].create(partner_vals)
        self.partner_id = partner
        return partner 

    @api.model
    def sync_abandoned_carts(self, connector_id):
        """Cron job logic to sync"""
        connector = self.env['zid.connector'].browse(connector_id)
        try:
            # Note: Endpoint path is hypothetical, need to check Zid Docs for "Abandoned Checkouts"
            # Often it's `managers/store/carts?status=abandoned` or similar
            response = connector.api_request('managers/store/carts?status=abandoned', method='GET')
            # ... process response ...
        except Exception as e:
            _logger.error(f"Failed to sync carts: {e}")
