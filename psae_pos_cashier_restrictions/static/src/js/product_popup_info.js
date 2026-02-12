/** @odoo-module */

import { ProductInfoPopup } from '@point_of_sale/app/screens/product_screen/product_info_popup/product_info_popup';
import { patch } from '@web/core/utils/patch';

patch(ProductInfoPopup.prototype, {
	_hasMarginsCostsAccessRights() {
		return this.pos.get_cashier().can_see_cost_margin;
	},
});
