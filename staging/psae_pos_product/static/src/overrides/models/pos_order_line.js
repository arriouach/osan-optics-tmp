/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";

patch(PosOrderline.prototype, {
    getDisplayData() {
        return {
            ...super.getDisplayData(),
            hide_on_pos_receipt: this.get_product().hide_on_pos_receipt,
        };
    },
})
