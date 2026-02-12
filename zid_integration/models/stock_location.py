from odoo import models, fields, api, _
from datetime import datetime, date, timedelta
from odoo.exceptions import ValidationError
from dateutil import relativedelta


class StockLocation(models.Model):
    _inherit = 'stock.location'

    zid_location_id = fields.Many2one('zid.location', string = 'Zid Location', ondelete='cascade')
