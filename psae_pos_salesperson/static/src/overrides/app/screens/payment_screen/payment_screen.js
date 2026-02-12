/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";


patch(PaymentScreen.prototype, {
    async validateOrder(isForcedValidate){
        if (this.pos.config.is_salesperson_mandatory && !this.pos.get_order().get_salesperson()) {
            await this.dialog.add(AlertDialog, {
                title: _t("Salesperson Not Set"),
                body: _t("Please select a salesperson before proceeding."),
            });
            return;
        }
        return super.validateOrder(...arguments)
    },
})
