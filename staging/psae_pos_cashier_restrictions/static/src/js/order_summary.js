import { AlertDialog } from '@web/core/confirmation_dialog/confirmation_dialog';
import { OrderSummary } from '@point_of_sale/app/screens/product_screen/order_summary/order_summary';
import { _t } from '@web/core/l10n/translation';
import { patch } from '@web/core/utils/patch';

patch(OrderSummary.prototype, {
	async updateSelectedOrderline({ buffer, key }) {
		const { can_change_price, can_discount, can_change_quantity, can_remove_line } =
			this.pos.get_cashier();

		const accessCheck = {
			price: can_change_price ?? true,
			discount: can_discount ?? true,
			quantity: (can_change_quantity || can_remove_line && key === 'Backspace') ?? true,
		};

		if (!accessCheck[this.pos.numpadMode]) {
			return this.dialog.add(AlertDialog, {
				title: _t('Access Error'),
				body: _t('Please contact your administrator to modify an item.'),
			});
		}

		return super.updateSelectedOrderline(...arguments);
	},
});
