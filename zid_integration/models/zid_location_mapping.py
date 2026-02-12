from odoo import models, fields, api, _
from datetime import datetime, date, timedelta
from odoo.exceptions import ValidationError
from dateutil import relativedelta


class ZidLocationMapping(models.Model):
    _name = 'zid.location.mapping'
    _description = 'Mapping between Odoo and Zid Locations'

    product_id = fields.Many2one('product.template', required=True)
    odoo_location_id = fields.Many2one('stock.location', required=True)
    zid_location_id = fields.Many2one('zid.location', required=True)
    last_synced_qty = fields.Float()
    last_sync_date = fields.Datetime()
    is_active = fields.Boolean(default=True)