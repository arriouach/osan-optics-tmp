# -*- coding: utf-8 -*-
{
    'name': 'POS BusinessChat Invoice',
    'version': '1.0.0',
    'category': 'Point of Sale',
    'summary': 'Send POS invoices to BusinessChat webhook',
    'description': """
        This module allows sending POS order invoices to BusinessChat
        via webhook integration with PDF attachment.
    """,
    'author': 'Cloudmen',
    'website': 'https://www.cloudmen.ae',
    'depends': ['point_of_sale', 'account'],
    'data': [
        'views/pos_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
