/** @odoo-module */

import { ActionpadWidget } from '@point_of_sale/app/screens/product_screen/action_pad/action_pad';
import { patch } from '@web/core/utils/patch';

patch(ActionpadWidget.prototype, {
	// The reason we are usng strict equality with false is
	// Since if multi-employees is not selected, can_refund will be undefined
	// So he should be able to have full access
	
	props: {
		...ActionpadWidget.props,
		isRefundButton: { type: Boolean, optional: true },
	},
	get isActionButtonRestricted() {
		return (
			this.props.actionType === 'refund' &&
			this.pos.get_cashier().can_refund === false
		);
	},
});
