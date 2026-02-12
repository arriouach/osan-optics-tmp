from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class ZidProductUpdateWizard(models.TransientModel):
    _name = 'zid.product.update.wizard'
    _description = 'Update Product Data in Zid'

    # =============== Relation Fields ===============
    product_id = fields.Many2one(
        'product.template',
        string='Product',
        required=True,
        readonly=True
    )

    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        related='product_id.zid_connector_id',
        readonly=True
    )

    zid_product_id = fields.Char(
        string='Zid Product ID',
        related='product_id.zid_product_id',
        readonly=True
    )

    # =============== Basic Information ===============
    update_name = fields.Boolean(
        string='Update Name',
        default=False
    )

    name_ar = fields.Char(
        string='Name (Arabic)',
        help='Product name in Arabic'
    )

    name_en = fields.Char(
        string='Name (English)',
        help='Product name in English'
    )

    # =============== Pricing ===============
    update_price = fields.Boolean(
        string='Update Price',
        default=False
    )

    price = fields.Float(
        string='Price',
        help='Regular price'
    )

    sale_price = fields.Float(
        string='Sale Price',
        help='Discounted sale price'
    )

    cost = fields.Float(
        string='Cost',
        help='Product cost'
    )

    # =============== Description ===============
    update_description = fields.Boolean(
        string='Update Description',
        default=False
    )

    description_ar = fields.Text(
        string='Description (Arabic)'
    )

    description_en = fields.Text(
        string='Description (English)'
    )

    short_description_ar = fields.Text(
        string='Short Description (Arabic)'
    )

    short_description_en = fields.Text(
        string='Short Description (English)'
    )

    # =============== SKU & Barcode ===============
    update_sku = fields.Boolean(
        string='Update SKU',
        default=False
    )

    sku = fields.Char(
        string='SKU',
        help='Stock Keeping Unit'
    )

    update_barcode = fields.Boolean(
        string='Update Barcode',
        default=False
    )

    barcode = fields.Char(
        string='Barcode'
    )

    # =============== Weight ===============
    update_weight = fields.Boolean(
        string='Update Weight',
        default=False
    )

    weight_value = fields.Float(
        string='Weight Value'
    )

    weight_unit = fields.Selection([
        ('kg', 'Kilogram'),
        ('g', 'Gram'),
        ('lb', 'Pound'),
        ('oz', 'Ounce')
    ], string='Weight Unit', default='kg')

    # =============== Stock ===============
    update_stock = fields.Boolean(
        string='Update Stock',
        default=False
    )

    stock_quantity = fields.Integer(
        string='Stock Quantity'
    )

    is_infinite_stock = fields.Boolean(
        string='Infinite Stock'
    )

    stock_location= fields.Many2one('zid.location', string = 'Location', ondelete='cascade')



    stock_location_id = fields.Char(
        string='Stock Location UUID',
        help='UUID of the stock location in Zid'
    )

    @api.onchange('stock_location')
    def get_location_uuid(self):
        for wizard in self:
            wizard.stock_location_id = wizard.stock_location.zid_location_id

    # =============== Status Flags ===============
    update_status = fields.Boolean(
        string='Update Status',
        default=False
    )

    is_published = fields.Boolean(
        string='Published',
        default=True
    )

    is_draft = fields.Boolean(
        string='Draft',
        default=False
    )

    is_taxable = fields.Boolean(
        string='Taxable',
        default=True
    )

    requires_shipping = fields.Boolean(
        string='Requires Shipping',
        default=True
    )

    # =============== SEO ===============
    update_seo = fields.Boolean(
        string='Update SEO',
        default=False
    )

    seo_title_ar = fields.Char(
        string='SEO Title (Arabic)'
    )

    seo_title_en = fields.Char(
        string='SEO Title (English)'
    )

    seo_description_ar = fields.Text(
        string='SEO Description (Arabic)'
    )

    seo_description_en = fields.Text(
        string='SEO Description (English)'
    )

    slug = fields.Char(
        string='URL Slug',
        help='SEO-friendly URL slug'
    )

    # =============== Keywords ===============
    update_keywords = fields.Boolean(
        string='Update Keywords',
        default=False
    )

    keywords = fields.Char(
        string='Keywords',
        help='Comma-separated keywords'
    )

    # =============== Badge ===============
    update_badge = fields.Boolean(
        string='Update Badge',
        default=False
    )

    badge_text_ar = fields.Char(
        string='Badge Text (Arabic)'
    )

    badge_text_en = fields.Char(
        string='Badge Text (English)'
    )

    badge_icon = fields.Selection([
        ('free_shipping', 'Free Shipping'),
        ('new', 'New'),
        ('sale', 'Sale'),
        ('hot', 'Hot'),
        ('limited', 'Limited'),
        ('exclusive', 'Exclusive')
    ], string='Badge Icon')

    # =============== Categories ===============
    update_categories = fields.Boolean(
        string='Update Categories',
        default=False
    )

    category_ids = fields.Text(
        string='Category IDs',
        help='Comma-separated Zid category IDs'
    )



    @api.model
    def default_get(self, fields_list):
        """Set default values from current product"""
        res = super().default_get(fields_list)

        # Get product from context
        product_id = self.env.context.get('active_id')
        if product_id:
            product = self.env['product.template'].browse(product_id)

            # Set product reference
            res['product_id'] = product_id

            # Set current values
            res['name_ar'] = product.name
            res['name_en'] = product.name
            res['price'] = product.list_price
            res['cost'] = product.standard_price
            res['sku'] = product.default_code or f'ODOO-{product.id}'
            res['barcode'] = product.barcode
            res['weight_value'] = product.weight
            res['description_ar'] = product.description_sale or ''
            res['description_en'] = product.description_sale or ''

            # Set stock quantity
            if hasattr(product, 'qty_available'):
                res['stock_quantity'] = int(product.qty_available)

            # Set status from Zid if exists
            if product.zid_product_id:
                res['is_published'] = product.zid_is_published
                res['is_draft'] = product.zid_is_draft
                res['is_taxable'] = product.zid_is_taxable
                res['requires_shipping'] = product.zid_requires_shipping
            else:
                res['is_taxable'] = True
                res['requires_shipping'] = product.type == 'product'

            if product.zid_connector_id:
                # Try to get default location
                default_location = product.zid_connector_id.default_location_id
                if default_location:
                    res['stock_location_id'] = default_location.id
                else:
                    # Get first enabled location
                    first_location = self.env['zid.location'].search([
                        ('zid_connector_id', '=', product.zid_connector_id.id),
                        ('is_enabled', '=', True)
                    ], limit=1)
                    if first_location:
                        res['stock_location_id'] = first_location.id

        return res

    def _prepare_update_data(self):
        """Prepare data for Zid API update"""
        data = {}

        # Name
        if self.update_name:
            data['name'] = {
                'ar': self.name_ar or self.name_en,
                'en': self.name_en or self.name_ar
            }

        # Pricing
        if self.update_price:
            if self.price:
                data['price'] = self.price
            if self.sale_price:
                data['sale_price'] = self.sale_price
            if self.cost:
                data['cost'] = self.cost

        # Description
        if self.update_description:
            if self.description_ar or self.description_en:
                data['description'] = {
                    'ar': self.description_ar or '',
                    'en': self.description_en or ''
                }
            if self.short_description_ar or self.short_description_en:
                data['short_description'] = {
                    'ar': self.short_description_ar or '',
                    'en': self.short_description_en or ''
                }

        # SKU
        if self.update_sku and self.sku:
            data['sku'] = self.sku

        # Barcode
        if self.update_barcode:
            data['barcode'] = self.barcode or ''

        # Weight
        if self.update_weight and self.weight_value:
            data['weight'] = {
                'value': self.weight_value,
                'unit': self.weight_unit
            }

        if self.update_stock:
            if not self.stock_location_id:
                if self.zid_connector_id:
                    default_location = self.zid_connector_id.default_location_id
                    if default_location:
                        location_uuid = default_location.zid_location_id
                    else:
                        # Get first enabled location
                        first_location = self.env['zid.location'].search([
                            ('zid_connector_id', '=', self.zid_connector_id.id),
                            ('is_enabled', '=', True)
                        ], limit=1)
                        if first_location:
                            location_uuid = first_location.zid_location_id
                        else:
                            raise UserError(_('No locations available. Please fetch locations from Zid first.'))
                else:
                    raise UserError(_('No Zid connector found.'))
            else:
                location_uuid = self.stock_location.zid_location_id

            stock_data = {
                'available_quantity': self.stock_quantity,
                'is_infinite': self.is_infinite_stock,
                'location': location_uuid
            }

            data['stocks'] = [stock_data]

        # Status
        if self.update_status:
            data['is_published'] = self.is_published
            data['is_draft'] = self.is_draft
            data['is_taxable'] = self.is_taxable
            data['requires_shipping'] = self.requires_shipping

        # SEO
        if self.update_seo:
            seo_data = {}
            if self.seo_title_ar or self.seo_title_en:
                seo_data['title'] = {
                    'ar': self.seo_title_ar or '',
                    'en': self.seo_title_en or ''
                }
            if self.seo_description_ar or self.seo_description_en:
                seo_data['description'] = {
                    'ar': self.seo_description_ar or '',
                    'en': self.seo_description_en or ''
                }
            if seo_data:
                data['seo'] = seo_data

            if self.slug:
                data['slug'] = self.slug

        # Keywords
        if self.update_keywords and self.keywords:
            keywords_list = [k.strip() for k in self.keywords.split(',')]
            data['keywords'] = keywords_list

        # Badge
        if self.update_badge:
            if self.badge_text_ar or self.badge_text_en:
                badge_data = {
                    'body': {
                        'ar': self.badge_text_ar or '',
                        'en': self.badge_text_en or ''
                    }
                }
                if self.badge_icon:
                    badge_data['icon'] = {'code': self.badge_icon}
                data['badge'] = badge_data

        # Categories
        if self.update_categories and self.category_ids:
            categories_list = [{'id': c.strip()} for c in self.category_ids.split(',')]
            data['categories'] = categories_list

        return data

    @api.onchange('update_stock')
    def _onchange_update_stock(self):
        """Check if locations are available when enabling stock update"""
        if self.update_stock and self.zid_connector_id:
            locations_count = self.env['zid.location'].search_count([
            ])
            if locations_count == 0:
                return {
                    'warning': {
                        'title': _('No Locations Available'),
                        'message': _('Please fetch locations from Zid first before updating stock.')
                    }
                }


    def action_update_in_zid(self):
        """Update product in Zid with selected data"""
        self.ensure_one()

        # Validate
        if not self.product_id.zid_product_id:
            raise UserError(_('This product does not exist in Zid yet. Please create it first.'))

        if not self.zid_connector_id or not self.zid_connector_id.is_connected:
            raise UserError(_('The Zid connector is not connected.'))

        # Check if any field is selected for update
        update_fields = [
            self.update_name, self.update_price, self.update_description,
            self.update_sku, self.update_barcode, self.update_weight,
            self.update_stock, self.update_status, self.update_seo,
            self.update_keywords, self.update_badge, self.update_categories
        ]

        if not any(update_fields):
            raise UserError(_('Please select at least one field to update.'))

        # Prepare update data
        update_data = self._prepare_update_data()

        if not update_data:
            raise UserError(_('No data to update. Please fill in the fields you want to update.'))

        try:
            # Make API request
            response = self.zid_connector_id.api_request(
                endpoint=f'products/{self.product_id.zid_product_id}/',
                method='PATCH',
                data=update_data
            )

            # Save response in product
            self.product_id.zid_response = json.dumps(response, indent=2)

            # Update product fields from response
            self.product_id._update_from_zid_response(response)

            # Update sync status
            self.product_id.write({
                'zid_sync_status': 'synced',
                'zid_last_sync': fields.Datetime.now(),
                'zid_error_message': False
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success!'),
                    'message': _('Product updated successfully in Zid'),
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f"Failed to update product in Zid: {str(e)}")
            self.product_id.write({
                'zid_sync_status': 'error',
                'zid_error_message': str(e)
            })
            raise UserError(_('Failed to update product in Zid: %s') % str(e))