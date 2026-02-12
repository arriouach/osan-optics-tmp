/** @odoo-module **/

import { ProductScreen } from '@point_of_sale/app/screens/product_screen/product_screen';
import { _t } from '@web/core/l10n/translation';
import { patch } from '@web/core/utils/patch';

patch(ProductScreen.prototype, {
	getNumpadButtons() {
		let res = super.getNumpadButtons();
		const { can_change_price, can_discount, can_change_quantity, can_remove_line } =
			this.pos.get_cashier();

		const valueMap = {
			quantity: can_change_quantity === false,
			discount: can_discount === false,
			price: can_change_price === false,
			Backspace: can_remove_line === false && can_change_quantity === false,
		};

		res.forEach((button) => {
			if (button.value in valueMap) {
				button.disabled = valueMap[button.value];
			}
		});

		return res;
	},

	onNumpadClick(buttonValue) {
		const selected_orderline = this.currentOrder.get_selected_orderline();
		if (
			buttonValue === 'Backspace' &&
			selected_orderline &&
			!this.pos.get_cashier().can_change_quantity
		) {
			this.currentOrder.removeOrderline(selected_orderline);
			return;
		}
		super.onNumpadClick(buttonValue);
	},
});
