from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ZidAttribute(models.Model):
    _name = 'zid.attribute'
    _description = 'Zid Product Attribute'
    _rec_name = 'display_name'
    _order = 'name_en, name_ar'

    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        ondelete='cascade',
        index=True
    )

    zid_attribute_id = fields.Char(
        string='Zid Attribute ID',
        required=True,
        index=True,
        help='Unique ID from Zid'
    )

    name_ar = fields.Char(
        string='Name (Arabic)',
        help='Attribute name in Arabic'
    )

    name_en = fields.Char(
        string='Name (English)',
        help='Attribute name in English'
    )

    slug = fields.Char(
        string='Slug',
        help='SEO friendly identifier'
    )

    value_ar = fields.Char(
        string='Value (Arabic)',
        help='Attribute value in Arabic'
    )

    value_en = fields.Char(
        string='Value (English)',
        help='Attribute value in English'
    )

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    # ربط مع Odoo
    odoo_attribute_id = fields.Many2one(
        'product.attribute',
        string='Odoo Attribute',
        help='Linked Odoo product attribute'
    )

    odoo_value_id = fields.Many2one(
        'product.attribute.value',
        string='Odoo Attribute Value',
        help='Linked Odoo attribute value'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('unique_zid_attribute',
         'UNIQUE(zid_connector_id, zid_attribute_id)',
         'This Zid attribute already exists for this connector!')
    ]

    @api.depends('name_en', 'name_ar', 'value_en', 'value_ar')
    def _compute_display_name(self):
        for record in self:
            name = record.name_en or record.name_ar or 'Unnamed'
            value = record.value_en or record.value_ar or ''
            if value:
                record.display_name = f"{name}: {value}"
            else:
                record.display_name = name

    def _create_odoo_attribute(self):
        """Create corresponding Odoo product attribute"""
        self.ensure_one()

        if self.odoo_attribute_id:
            return self.odoo_attribute_id

        # البحث عن attribute مشابهة
        attribute_name = self.name_en or self.name_ar
        if not attribute_name:
            return False

        odoo_attr = self.env['product.attribute'].search([
            ('name', '=ilike', attribute_name)
        ], limit=1)

        if not odoo_attr:
            # إنشاء attribute جديدة
            odoo_attr = self.env['product.attribute'].create({
                'name': attribute_name,
                'display_type': 'select',
                'create_variant': 'always',
            })
            _logger.info(f"Created Odoo attribute: {attribute_name}")

        self.odoo_attribute_id = odoo_attr.id

        # إنشاء value
        self._create_odoo_attribute_value(odoo_attr)

        return odoo_attr

    def _create_odoo_attribute_value(self, odoo_attribute):
        """Create Odoo attribute value"""
        self.ensure_one()

        if self.odoo_value_id:
            return self.odoo_value_id

        value_name = self.value_en or self.value_ar
        if not value_name:
            return False

        # البحث عن value موجودة
        odoo_value = self.env['product.attribute.value'].search([
            ('attribute_id', '=', odoo_attribute.id),
            ('name', '=ilike', value_name)
        ], limit=1)

        if not odoo_value:
            # إنشاء value جديدة
            odoo_value = self.env['product.attribute.value'].create({
                'attribute_id': odoo_attribute.id,
                'name': value_name,
            })
            _logger.info(f"Created Odoo attribute value: {value_name}")

        self.odoo_value_id = odoo_value.id
        return odoo_value

    def _update_odoo_attribute(self):
        """Update existing Odoo attribute"""
        self.ensure_one()

        if not self.odoo_attribute_id:
            return self._create_odoo_attribute()

        # تحديث الاسم
        attribute_name = self.name_en or self.name_ar
        if attribute_name and self.odoo_attribute_id.name != attribute_name:
            self.odoo_attribute_id.name = attribute_name

        # تحديث القيمة
        if self.odoo_value_id:
            value_name = self.value_en or self.value_ar
            if value_name and self.odoo_value_id.name != value_name:
                self.odoo_value_id.name = value_name
        else:
            self._create_odoo_attribute_value(self.odoo_attribute_id)

    def action_create_odoo_attribute(self):
        """Manual action to create Odoo attribute"""
        for record in self:
            record._create_odoo_attribute()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Odoo attributes created successfully'),
                'type': 'success',
            }
        }