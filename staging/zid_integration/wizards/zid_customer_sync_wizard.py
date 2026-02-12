from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class ZidCustomerSyncWizard(models.TransientModel):
    _name = 'zid.customer.sync.wizard'
    _description = 'Bulk Zid Customer Sync'

    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        domain=[('authorization_status', '=', 'connected')]
    )

    sync_mode = fields.Selection([
        ('import', 'Import from Zid'),
        # ('export', 'Export to Zid') # Reserved for future use
    ], string='Sync Mode', default='import', required=True)

    date_from = fields.Datetime(string='Updated Since')

    def action_sync_customers(self):
        """Execute selected sync operation"""
        self.ensure_one()
        
        if self.sync_mode == 'import':
            return self._import_customers()
        return False

    def _import_customers(self):
        """Import customers from Zid API"""
        connector = self.zid_connector_id
        
        # Prepare params
        page = 1
        per_page = 50
        total_synced = 0
        total_failed = 0
        
        while True:
            params = {
                'page': page,
                'per_page': per_page
            }
            # Note: Zid API might use different filters
            
            try:
                # Call Proxy/Zid API
                response = connector.api_request(
                    endpoint='managers/store/customers',
                    method='GET',
                    data=params # GET params
                )
                
                customers = response.get('customers', []) if response else []
                
                if not customers:
                    break
                    
                for cust_data in customers:
                    try:
                        self._create_or_update_partner(cust_data)
                        total_synced += 1
                    except Exception as e:
                        _logger.error(f"Failed to sync customer {cust_data.get('id')}: {str(e)}")
                        total_failed += 1
                
                # Check pagination
                pagination = response.get('pagination', {})
                if page >= pagination.get('total_pages', 1):
                    break
                    
                page += 1
                
            except Exception as e:
                raise UserError(_('API Error: %s') % str(e))
                
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Customer Sync Completed'),
                'message': _('Synced: %d, Failed: %d') % (total_synced, total_failed),
                'type': 'success',
            }
        }

    def _create_or_update_partner(self, data):
        """Create or update Odoo partner from Zid customer data"""
        partner_obj = self.env['res.partner']
        
        # Extract key fields
        zid_id = str(data.get('id'))
        name = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
        email = data.get('email')
        mobile = data.get('mobile')
        
        if not name: 
            name = 'Unknown Zid Customer'

        # Find existing partner
        domain = []
        if email:
            domain = ['|', ('email', '=', email)]
        if mobile:
            if domain:
                domain.append(('mobile', '=', mobile))
                domain.insert(0, '|')
            else:
                domain = [('mobile', '=', mobile)]
        
        # Scope to company
        if domain:
            domain = ['&', ('company_id', 'in', [False, self.zid_connector_id.company_id.id])] + domain
            partner = partner_obj.search(domain, limit=1)
        else:
            partner = False

        vals = {
            'name': name,
            'email': email,
            'mobile': mobile,
            'company_id': self.zid_connector_id.company_id.id,
            'customer_rank': 1,
            # Store Zid ID in reference or a custom field if we added one (we haven't added zid_customer_id to res.partner yet, using comment for now)
            'comment': f"Zid Customer ID: {zid_id}"
        }

        if partner:
            partner.write(vals)
        else:
            partner_obj.create(vals)
