from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
import json

_logger = logging.getLogger(__name__)


class ZidProductRelinkWizard(models.TransientModel):
    _name = 'zid.product.relink.wizard'
    _description = 'Relink Zid Product with Odoo Product'

    zid_product_id = fields.Many2one(
        'zid.product',
        string='Zid Product',
        required=True
    )

    current_product_id = fields.Many2one(
        'product.product',
        string='Current Linked Product'
    )

    new_product_id = fields.Many2one(
        'product.product',
        string='New Product to Link',
        required=True,
        help='Select the Odoo product to link with this Zid product'
    )

    update_main_image = fields.Boolean(
        string='Update Main Image',
        default=False,
        help='Update Odoo product main image from Zid main image'
    )

    update_sale_price = fields.Boolean(
        string='Update Sales Price',
        default=False,
        help='Update Odoo product list price from Zid sale price'
    )

    sync_zid_media = fields.Boolean(
        string='Sync Zid Media Gallery',
        default=False,
        help='Sync Zid media gallery images to Odoo product extra images'
    )

    product_sku = fields.Char(
        related='zid_product_id.sku',
        string='Product SKU',
        readonly=True
    )

    product_name = fields.Char(
        related='zid_product_id.name',
        string='Product Name',
        readonly=True
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id:
            zid_product = self.env['zid.product'].browse(active_id)
            res.update({
                'zid_product_id': zid_product.id,
                'current_product_id': zid_product.odoo_product_id.id if zid_product.odoo_product_id else False,
                'new_product_id': zid_product.odoo_product_id.id if zid_product.odoo_product_id else False,
            })
        return res

    def _perform_link_and_sync(self, zid_product, new_product, update_main_image, update_sale_price, sync_zid_media):
        """Helper method to perform linking and syncing logic for a single product"""
        new_template = new_product.product_tmpl_id

        # Update the link on Zid Product
        zid_product.write({'odoo_product_id': new_product.id})

        # Prepare update values for Odoo product template
        template_vals = {
            'zid_product_id': zid_product.zid_product_id,
            'zid_connector_id': zid_product.zid_connector_id.id,
            'zid_sku': zid_product.sku,
            'zid_barcode': zid_product.barcode,
            'zid_price': zid_product.price,
            'zid_sale_price': zid_product.sale_price,
            'zid_quantity': zid_product.quantity,
            'zid_is_infinite': zid_product.is_infinite,
            'zid_is_published': zid_product.is_published,
            'zid_is_draft': zid_product.is_draft,
            'zid_is_taxable': zid_product.is_taxable,
            'zid_requires_shipping': zid_product.requires_shipping,
            'zid_has_options': zid_product.has_options,
            'zid_has_fields': zid_product.has_fields,
            'zid_html_url': zid_product.html_url,
            'zid_slug': zid_product.slug,
            'zid_product_class': zid_product.product_class,
            'zid_currency': zid_product.currency_code,
            'zid_currency_symbol': zid_product.currency_symbol,
            'zid_formatted_price': zid_product.formatted_price,
            'zid_formatted_sale_price': zid_product.formatted_sale_price,
            'zid_created_at': zid_product.zid_created_at,
            'zid_updated_at': zid_product.zid_updated_at,
            'zid_last_sync': fields.Datetime.now(),
            'zid_sync_status': 'synced',
            'zid_exists': True,
            'sale_ok': True,
            'active': True,
        }

        if update_main_image and zid_product.main_image:
            template_vals['image_1920'] = zid_product.main_image

        if update_sale_price:
            price = zid_product.sale_price if zid_product.sale_price > 0 else zid_product.price
            if price > 0:
                template_vals['list_price'] = price

        # Update the template
        new_template.write(template_vals)

        # Sync gallery images (always link to custom tab, only force native if selected)
        zid_product._sync_odoo_gallery_images(new_template, force=sync_zid_media)

        # Re-link logic for location lines
        # Remove old lines for THIS Zid Product
        old_lines = self.env['zid.product.line'].search([
            ('zid_product_product_id', '=', zid_product.id)
        ])
        if old_lines:
            old_lines.unlink()

        # Create/Update zid.product.line for each location
        for location_line in zid_product.zid_location_ids:
            self.env['zid.product.line'].create({
                'product_template_id': new_template.id,
                'zid_connector_id': zid_product.zid_connector_id.id,
                'zid_product_product_id': zid_product.id,
                'zid_product_id': zid_product.zid_product_id,
                'zid_sku': zid_product.sku,
                'is_published': zid_product.is_published,
                'zid_price': zid_product.price,
                'zid_quantity': int(location_line.quantity),
                'zid_location_id': location_line.location_id.id,
                'sync_status': 'synced',
                'last_sync_date': fields.Datetime.now(),
            })

    def action_relink(self):
        self.ensure_one()
        if not self.new_product_id:
            raise UserError(_('Please select a product to link.'))

        self._perform_link_and_sync(
            self.zid_product_id,
            self.new_product_id,
            self.update_main_image,
            self.update_sale_price,
            self.sync_zid_media
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Zid product successfully linked to Odoo product: %s') % self.new_product_id.display_name,
                'type': 'success',
                'sticky': False,
            }
        }


class ZidProductBulkRelinkWizard(models.TransientModel):
    _name = 'zid.product.bulk.relink.wizard'
    _description = 'Bulk Relink Zid Products'

    line_ids = fields.One2many(
        'zid.product.bulk.relink.line',
        'wizard_id',
        string='Products to Relink'
    )

    update_main_image = fields.Boolean(
        string='Update Main Image',
        default=False
    )

    update_sale_price = fields.Boolean(
        string='Update Sales Price',
        default=False
    )

    sync_zid_media = fields.Boolean(
        string='Sync Zid Media Gallery',
        default=False
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            lines = []
            for zid_product in self.env['zid.product'].browse(active_ids):
                lines.append((0, 0, {
                    'zid_product_id': zid_product.id,
                    'current_product_id': zid_product.odoo_product_id.id if zid_product.odoo_product_id else False,
                    'new_product_id': zid_product.odoo_product_id.id if zid_product.odoo_product_id else False,
                }))
            res['line_ids'] = lines
        return res

    def action_auto_match(self):
        """Auto-match by SKU"""
        for line in self.line_ids:
            if not line.new_product_id and line.zid_product_id.sku:
                product = self.env['product.product'].search([
                    ('default_code', '=', line.zid_product_id.sku)
                ], limit=1)
                if not product:
                    product = self.env['product.product'].search([
                        ('barcode', '=', line.zid_product_id.sku)
                    ], limit=1)
                if product:
                    line.new_product_id = product.id

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_relink_bulk(self):
        self.ensure_one()
        success_count = 0
        for line in self.line_ids:
            if line.new_product_id:
                # Use a dummy wizard instance to reuse logic
                dummy_wizard = self.env['zid.product.relink.wizard'].new()
                dummy_wizard._perform_link_and_sync(
                    line.zid_product_id,
                    line.new_product_id,
                    self.update_main_image,
                    self.update_sale_price,
                    self.sync_zid_media
                )
                success_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bulk Link Success'),
                'message': _('Successfully linked %d products.') % success_count,
                'type': 'success',
                'sticky': False,
            }
        }


class ZidProductBulkRelinkLine(models.TransientModel):
    _name = 'zid.product.bulk.relink.line'
    _description = 'Bulk Relink Line'

    wizard_id = fields.Many2one(
        'zid.product.bulk.relink.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )

    zid_product_id = fields.Many2one(
        'zid.product',
        string='Zid Product',
        required=True
    )

    product_sku = fields.Char(
        related='zid_product_id.sku',
        string='SKU',
        readonly=True
    )

    product_name = fields.Char(
        related='zid_product_id.name',
        string='Name',
        readonly=True
    )

    current_product_id = fields.Many2one(
        'product.product',
        string='Current Product'
    )

    new_product_id = fields.Many2one(
        'product.product',
        string='New Product'
    )
