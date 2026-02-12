{
    "name": "PSAE POS Product",
    "summary": "Preselect specific products in new PoS order and Hide specific products on PoS receipts",
    "category": "Point Of Sale",
    "version": "18.0.1.0.0",
    "author": "Odoo PS",
    "website": "https://www.odoo.com",
    "license": "OEEL-1",
    "depends": ["point_of_sale"],
    "data": [
        "views/product_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "psae_pos_product/static/src/**/*",
        ]
    },
    "installable": True,
    "auto_install": True,
    "application": False,
    "task_id": [5382730],
}
