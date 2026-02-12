from odoo import models, fields, api, _
from datetime import datetime, date, timedelta
from odoo.exceptions import ValidationError
from dateutil import relativedelta


class ZidStockSyncLog(models.Model):
    _name = 'zid.stock.sync.log'
    _description = 'Zid Stock Sync History'
    _order = 'create_date desc'

    product_id = fields.Many2one('product.template')
    odoo_location_id = fields.Many2one('stock.location')
    zid_location_id = fields.Many2one('zid.location')
    old_quantity = fields.Float()
    new_quantity = fields.Float()
    sync_status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed')
    ])
    error_message = fields.Text()
    sync_date = fields.Datetime(default=fields.Datetime.now)