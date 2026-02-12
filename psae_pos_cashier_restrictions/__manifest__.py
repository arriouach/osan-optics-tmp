{
    "name": "PSAE - POS Cashier Restrictions",
    "summary": """
        Cashier Restrictions on POS.
    """,
    "description": """
        Cashier Restrictions on POS
        ================================
            - Controls if cashiers can refund
            - Controls if cashiers can discount
            - Controls if cashiers can change price
            - Controls if cashiers can change quantity
            - Controls if cashiers can see the profit margin
    """,
    "author": "Odoo PS",
    "license": "OEEL-1",
    "website": "https://www.odoo.com",
    "category": "Point of Sale",
    "version": "18.0.2.1.1",
    "depends": ["pos_hr", "pos_discount"],
    "data": ["views/hr_employee_views.xml"],
    "assets": {
        "point_of_sale._assets_pos": [
            "psae_pos_cashier_restrictions/static/src/**/*",
        ],
    },
    "task_ids": [4193828, 4391900, 4711953, 4788749],
}
