from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ZidAttributeConnector(models.TransientModel):
    _name = 'zid.attribute.connector'
    _description = 'Zid Attribute Import Wizard'

    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        default=lambda self: self._get_default_connector()
    )

    total_attributes = fields.Integer(
        string='Total Attributes',
        readonly=True,
        help='Total attributes found in Zid'
    )

    imported_count = fields.Integer(
        string='Imported',
        readonly=True
    )

    updated_count = fields.Integer(
        string='Updated',
        readonly=True
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('fetching', 'Fetching...'),
        ('done', 'Done'),
        ('error', 'Error')
    ], default='draft', string='Status')

    error_message = fields.Text(
        string='Error Message',
        readonly=True
    )

    attribute_ids = fields.Many2many(
        'zid.attribute',
        string='Imported Attributes',
        readonly=True
    )

    auto_create_odoo_attributes = fields.Boolean(
        string='Auto Create Odoo Attributes',
        default=True,
        help='Automatically create corresponding Odoo product attributes'
    )

    @api.model
    def _get_default_connector(self):
        """Get default connector from context"""
        connector_id = self.env.context.get('default_zid_connector_id')
        if connector_id:
            return connector_id

        # أو أول connector متصل
        connector = self.env['zid.connector'].search([
            ('authorization_status', '=', 'connected')
        ], limit=1)
        return connector.id if connector else False

    def action_fetch_attributes(self):
        """Fetch attributes from Zid API"""
        self.ensure_one()

        if not self.zid_connector_id:
            raise UserError(_('Please select a Zid Connector'))

        if not self.zid_connector_id.is_connected:
            raise UserError(_('Connector is not connected to Zid'))

        self.state = 'fetching'

        try:
            # استدعاء API
            response = self.zid_connector_id.api_request(
                endpoint='attributes/',
                method='GET'
            )

            _logger.info(f"Fetched attributes response: {response}")

            if not response:
                raise UserError(_('No response from Zid API'))

            total_count = response.get('count', 0)
            self.total_attributes = total_count

            # معالجة النتائج
            results = response.get('results', [])
            imported_attrs, updated_attrs = self._process_attributes(results)

            # التعامل مع الصفحات المتعددة (Pagination)
            next_page = response.get('next')
            while next_page:
                # استخراج endpoint من الـ URL
                import urllib.parse
                parsed_url = urllib.parse.urlparse(next_page)
                endpoint = f"{parsed_url.path.lstrip('/')}"
                if parsed_url.query:
                    endpoint += f"?{parsed_url.query}"

                next_response = self.zid_connector_id.api_request(
                    endpoint=endpoint,
                    method='GET'
                )

                if next_response and 'results' in next_response:
                    imp, upd = self._process_attributes(next_response['results'])
                    imported_attrs.extend(imp)
                    updated_attrs.extend(upd)

                next_page = next_response.get('next')

            self.imported_count = len(imported_attrs)
            self.updated_count = len(updated_attrs)
            self.attribute_ids = [(6, 0, imported_attrs + updated_attrs)]
            self.state = 'done'

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'zid.attribute.connector',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'context': {'form_view_initial_mode': 'readonly'}
            }

        except Exception as e:
            _logger.error(f"Error fetching attributes: {str(e)}")
            self.state = 'error'
            self.error_message = str(e)
            raise UserError(_('Failed to fetch attributes: %s') % str(e))

    def _process_attributes(self, attributes_data):
        """Process and save attributes"""
        attribute_model = self.env['zid.attribute']
        imported_ids = []
        updated_ids = []

        for attr_data in attributes_data:
            # البحث عن attribute موجودة
            existing = attribute_model.search([
                ('zid_attribute_id', '=', attr_data.get('id')),
                ('zid_connector_id', '=', self.zid_connector_id.id)
            ], limit=1)

            vals = {
                'zid_connector_id': self.zid_connector_id.id,
                'zid_attribute_id': attr_data.get('id'),
                'name_ar': attr_data.get('name', {}).get('ar', ''),
                'name_en': attr_data.get('name', {}).get('en', ''),
                'slug': attr_data.get('slug', ''),
                'value_ar': attr_data.get('value', {}).get('ar', ''),
                'value_en': attr_data.get('value', {}).get('en', ''),
            }

            if existing:
                existing.write(vals)
                updated_ids.append(existing.id)

                # تحديث Odoo attribute إذا كان موجود
                if self.auto_create_odoo_attributes and existing.odoo_attribute_id:
                    existing._update_odoo_attribute()
            else:
                new_attr = attribute_model.create(vals)
                imported_ids.append(new_attr.id)

                # إنشاء Odoo attribute
                if self.auto_create_odoo_attributes:
                    new_attr._create_odoo_attribute()

        return imported_ids, updated_ids

    def action_view_attributes(self):
        """View imported attributes"""
        self.ensure_one()

        return {
            'name': _('Imported Attributes'),
            'type': 'ir.actions.act_window',
            'res_model': 'zid.attribute',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.attribute_ids.ids)],
            'context': {'create': False}
        }

    def action_close(self):
        """Close wizard"""
        return {'type': 'ir.actions.act_window_close'}