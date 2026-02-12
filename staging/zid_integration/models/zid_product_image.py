from odoo import models, fields, api, _

class ZidProductImage(models.Model):
    _name = 'zid.product.image'
    _description = 'Zid Product Images'
    _order = 'sequence, id'

    product_id = fields.Many2one(
        'zid.product',
        string='Zid Product',
        ondelete='cascade'
    )

    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Odoo Product Template',
        ondelete='cascade'
    )

    variant_id = fields.Many2one(
        'zid.variant',
        string='Variant',
        ondelete='cascade'
    )

    zid_image_id = fields.Char(
        string='Zid Image ID',
        readonly=True
    )

    image = fields.Image(
        string='Image',
        required=True
    )

    image_url = fields.Char(
        string='Image URL',
        readonly=True
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
