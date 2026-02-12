/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

patch(PosOrder.prototype, {
    export_for_printing(baseUrl, headerData) {
        return {
            ...super.export_for_printing(...arguments),
            salesperson: this.get_salesperson(),
        };
    },
    set_salesperson(salesperson) {
        if (salesperson) {
            this.update({ salesperson_id: salesperson });
        }
    },
    get_salesperson() {
        return this.salesperson_id;
    }
})
