/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { _t } from "@web/core/l10n/translation";

patch(PosStore.prototype, {
    createNewOrder() {
        const order = super.createNewOrder(...arguments);
        const preselectedProducts = this.models["product.product"].filter((p) => p.is_preselected_in_pos);
        for (const product of preselectedProducts){
            this.addLineToOrder({ 
                product_id: product.id,
                order_id: order,
            }, order, {}, true);
        }
        return order;
    },
});
