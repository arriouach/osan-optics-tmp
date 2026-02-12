{
    "name": "PSAE POS Salespeople",
    "summary": "Show salespoeple on POS receipts",
    "category": "Point Of Sale",
    "version": "18.0.1.0.0",
    "author": "Odoo PS",
    "website": "https://www.odoo.com",
    "license": "OEEL-1",
    "depends": ["point_of_sale", "pos_hr"],
    "data": [
        # Views
        "views/pos_config_views.xml",
        "views/pos_order_report_views.xml",
        "views/pos_order_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "psae_pos_salesperson/static/src/**/*",
        ]
    },
    "installable": True,
    "auto_install": True,
    "application": False,
    "task_id": [5382730],
}
