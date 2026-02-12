{
    "name": "Warehouse Record Rules",
    "version": "18.0.0.1.0",
    "summary": "Warehouse Record Rules: Inventory",
    "category": "Inventory",
    "author": "Odoo PS",
    "website": "https://www.odoo.com",
    "license": "OEEL-1",
    "depends": ["base_record_rules", "stock"],
    "data": [
        "views/stock_warehouse_views.xml",
        "views/stock_picking_views.xml",
        "views/stock_location_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}
