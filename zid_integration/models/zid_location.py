from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class ZidLocation(models.Model):
    _name = 'zid.location'
    _description = 'Zid Store Locations'
    _rec_name = 'display_name'
    _order = 'is_default desc, fulfillment_priority, name_en'

    # =============== Connector ===============
    zid_connector_id = fields.Many2one(
        'zid.connector',
        string='Zid Connector',
        required=True,
        ondelete='cascade',
        help='The Zid connector this location belongs to'
    )

    # =============== Basic Information ===============
    zid_location_id = fields.Char(
        string='Zid Location ID',
        required=True,
        readonly=True,
        help='UUID of the location in Zid'
    )

    name_ar = fields.Char(
        string='Name (Arabic)',
        help='Location name in Arabic'
    )

    name_en = fields.Char(
        string='Name (English)',
        help='Location name in English'
    )

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    # =============== Location Type ===============
    location_type = fields.Char(
        string='Location Type',
        help='Type of location (e.g., PHYSICAL)'
    )

    # =============== Address Information ===============
    full_address = fields.Text(
        string='Full Address',
        help='Complete address of the location'
    )

    # City Information
    city_id_zid = fields.Integer(
        string='City ID (Zid)',
        help='City ID in Zid system'
    )

    city_name = fields.Char(
        string='City Name',
        help='City name in English'
    )

    city_name_ar = fields.Char(
        string='City Name (Arabic)',
        help='City name in Arabic'
    )

    # Country Information
    country_id_zid = fields.Integer(
        string='Country ID (Zid)',
        help='Country ID in Zid system'
    )

    country_name = fields.Char(
        string='Country Name',
        help='Country name in English'
    )

    country_name_ar = fields.Char(
        string='Country Name (Arabic)',
        help='Country name in Arabic'
    )

    country_iso_code_2 = fields.Char(
        string='Country ISO Code 2',
        size=2,
        help='2-letter country code'
    )

    country_iso_code_3 = fields.Char(
        string='Country ISO Code 3',
        size=3,
        help='3-letter country code'
    )

    # =============== Coordinates ===============
    latitude = fields.Float(
        string='Latitude',
        digits=(10, 6),
        help='Geographic latitude'
    )

    longitude = fields.Float(
        string='Longitude',
        digits=(10, 6),
        help='Geographic longitude'
    )

    # =============== Settings ===============
    fulfillment_priority = fields.Integer(
        string='Fulfillment Priority',
        help='Priority for fulfillment (lower number = higher priority, 1 is highest)'
    )

    is_default = fields.Boolean(
        string='Is Default',
        default=False,
        help='This is the default location'
    )

    is_private = fields.Boolean(
        string='Is Private',
        default=False,
        help='This location is private'
    )

    is_enabled = fields.Boolean(
        string='Is Enabled',
        default=True,
        help='This location is enabled for use'
    )

    has_stocks = fields.Boolean(
        string='Has Stocks',
        default=False,
        help='This location has inventory stocks'
    )

    # =============== Channels ===============
    channels = fields.Text(
        string='Channels',
        help='JSON array of channels (catalog, online, physical_store, direct_sales)'
    )

    channel_catalog = fields.Boolean(
        string='Catalog Channel',
        compute='_compute_channels',
        store=True
    )

    channel_online = fields.Boolean(
        string='Online Channel',
        compute='_compute_channels',
        store=True
    )

    channel_physical_store = fields.Boolean(
        string='Physical Store Channel',
        compute='_compute_channels',
        store=True
    )

    channel_direct_sales = fields.Boolean(
        string='Direct Sales Channel',
        compute='_compute_channels',
        store=True
    )

    # =============== Metadata ===============
    raw_data = fields.Text(
        string='Raw Data',
        help='Original JSON response from Zid'
    )

    last_sync_date = fields.Datetime(
        string='Last Sync Date',
        readonly=True
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    # =============== Computed Fields ===============
    @api.depends('name_en', 'name_ar')
    def _compute_display_name(self):
        for location in self:
            if location.name_en and location.name_ar:
                location.display_name = f"{location.name_en} - {location.name_ar}"
            elif location.name_en:
                location.display_name = location.name_en
            elif location.name_ar:
                location.display_name = location.name_ar
            else:
                location.display_name = location.zid_location_id or 'Unknown Location'

    @api.depends('channels')
    def _compute_channels(self):
        for location in self:
            channels_list = []
            if location.channels:
                try:
                    channels_list = json.loads(location.channels)
                except (json.JSONDecodeError, TypeError):
                    channels_list = []

            location.channel_catalog = 'catalog' in channels_list
            location.channel_online = 'online' in channels_list
            location.channel_physical_store = 'physical_store' in channels_list
            location.channel_direct_sales = 'direct_sales' in channels_list

    # =============== Constraints ===============
    _sql_constraints = [
        ('unique_zid_location_connector',
         'UNIQUE(zid_location_id, zid_connector_id)',
         'Location ID must be unique per connector!'),
    ]

    # =============== Methods ===============
    @api.model
    def create_or_update_from_zid(self, location_data, connector_id):
        """Create or update location from Zid API response"""
        if not location_data.get('id'):
            return False

        # Search for existing location
        existing = self.search([
            ('zid_location_id', '=', location_data.get('id')),
            ('zid_connector_id', '=', connector_id)
        ], limit=1)

        # Prepare values
        vals = self._prepare_location_values(location_data, connector_id)

        if existing:
            existing.write(vals)
            return existing
        else:
            return self.create(vals)

    def _prepare_location_values(self, location_data, connector_id):
        """Prepare values from Zid API response"""
        vals = {
            'zid_connector_id': connector_id,
            'zid_location_id': location_data.get('id'),
            'location_type': location_data.get('type'),
            'full_address': location_data.get('full_address'),
            'fulfillment_priority': location_data.get('fulfillment_priority'),
            'is_default': location_data.get('is_default', False),
            'is_private': location_data.get('is_private', False),
            'is_enabled': location_data.get('is_enabled', True),
            'has_stocks': location_data.get('has_stocks', False),
            'raw_data': json.dumps(location_data, indent=2),
            'last_sync_date': fields.Datetime.now(),
        }

        # Name
        if location_data.get('name'):
            vals['name_ar'] = location_data['name'].get('ar')
            vals['name_en'] = location_data['name'].get('en')

        # City
        if location_data.get('city'):
            city = location_data['city']
            vals['city_id_zid'] = city.get('id')
            vals['city_name'] = city.get('name')
            vals['city_name_ar'] = city.get('ar_name')

            # Country
            if city.get('country'):
                country = city['country']
                vals['country_id_zid'] = country.get('id')
                vals['country_name'] = country.get('name')
                vals['country_name_ar'] = country.get('ar_name')
                vals['country_iso_code_2'] = country.get('iso_code_2')
                vals['country_iso_code_3'] = country.get('iso_code_3')

        # Coordinates
        if location_data.get('coordinates'):
            coords = location_data['coordinates']
            vals['latitude'] = coords.get('latitude')
            vals['longitude'] = coords.get('longitude')

        # Channels
        if location_data.get('channels'):
            vals['channels'] = json.dumps(location_data['channels'])

        return vals

    def open_in_map(self):
        """Open location in Google Maps"""
        self.ensure_one()
        if self.latitude and self.longitude:
            url = f"https://www.google.com/maps/search/?api=1&query={self.latitude},{self.longitude}"
            return {
                'type': 'ir.actions.act_url',
                'url': url,
                'target': 'new',
            }
        else:
            raise UserError(_('No coordinates available for this location'))
