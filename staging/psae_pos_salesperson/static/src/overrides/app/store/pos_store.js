/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { makeAwaitable } from "@point_of_sale/app/store/make_awaitable_dialog";

patch(PosStore.prototype, {
    getReceiptHeaderData(order) {
        const result = super.getReceiptHeaderData(...arguments);
        // This method gets called on the event of cash-out/cash-in with no parameters
        // so we need to make sure that it's being called on order completion
        result.salesperson = order?.get_salesperson();
        return result;
    },
    async selectEmployee(currentOrder=null) {
        const order = this.get_order();
        if (!currentOrder && !order) {
            return;
        } else if (!currentOrder) {
            currentOrder = order;
        }
        const currentSalesperson = currentOrder.get_salesperson()
        if (currentSalesperson && currentOrder.getHasRefundLines()) {
            this.dialog.add(AlertDialog, {
                title: _t("Can't change salesperson"),
                body: _t(
                    "This order already has refund lines for %s. We can't change the salesperson associated with it.",
                    currentSalesperson.name
                ),
            });
            return;
        }
        const selectionList = Object.values(this.config.selected_employee_ids).map((employee) => ({
            id: employee.id,
            item: employee,
            label: employee.name,
            isSelected:
                currentOrder.get_salesperson() &&
                employee.id === currentOrder.get_salesperson().id,
        }));
        const employee = await makeAwaitable(this.dialog, SelectionPopup, {
            title: _t('Select Salesperson'),
            list: selectionList,
        });
        if (employee) {
            currentOrder.set_salesperson(employee)
        }
    },
});
