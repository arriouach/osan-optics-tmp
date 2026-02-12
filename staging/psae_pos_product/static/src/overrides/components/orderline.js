/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { Orderline } from "@point_of_sale/app/generic_components/orderline/orderline";

patch(Orderline.props.line.shape, {
        hide_on_pos_receipt: { type: Boolean, optional: true },
});
