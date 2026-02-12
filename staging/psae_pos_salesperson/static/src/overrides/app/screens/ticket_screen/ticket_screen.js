/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";

patch(TicketScreen.prototype, {
    getSalesperson(order) {
        return order.get_salesperson()?.name || '';
    },
    setSalespersonToRefundOrder(salesperson, destinationOrder) {
        destinationOrder.salesperson_id ||= salesperson;
    },
    _getEmptyOrder(partner, salesperson) {
        let emptyOrder = null;
        const activeOrders = this.pos.models["pos.order"].filter((o) => !o.finalized && !o.lines.length && !o.payment_ids.length);

        for (const order of activeOrders) {
            if (order.get_partner() === partner && order.get_salesperson() === salesperson) {
                return order;
            } 
            if (!order.get_partner() && !emptyOrder) {
                emptyOrder = order;
            }
        }
        return emptyOrder || this.pos.add_new_order();
    },
    async onDoRefund() {
        const order = this.getSelectedOrder();
        const partner = order.get_partner();
        const salesperson = order.get_salesperson();
        const destinationOrder =
            this.props.destinationOrder &&
            partner === this.props.destinationOrder.get_partner() &&
            !this.pos.doNotAllowRefundAndSales()
                ? this.props.destinationOrder
                : this._getEmptyOrder(partner, salesperson);

        this.setSalespersonToRefundOrder(salesperson, destinationOrder);

        return await super.onDoRefund(...arguments);
    }
})
