# Part of Odoo. See LICENSE file for full copyright and licensing details.

from functools import partial

from odoo import fields, models, _
from odoo.addons.sale_subscription.models.sale_order import SUBSCRIPTION_PROGRESS_STATE
from dateutil.relativedelta import relativedelta


class AccountMove(models.Model):
    _inherit = 'account.move'

    def write(self, vals):
        res = super().write(vals)
        if 'matched_payment_ids' in vals:
            for move in self.filtered_domain([('payment_state', 'in', ['paid', 'in_payment'])]):
                move._reopen_paid_churned_subscription()
        return res

    def _post(self, soft=True):
        posted_moves = super()._post(soft=soft)
        automatic_invoice = self.env.context.get('recurring_automatic')
        all_subscription_ids = set()
        log_date_values = {"upsell": {}, "subscription": {}}
        for move in posted_moves:
            if not move.invoice_line_ids.subscription_id:
                continue
            if move.move_type != 'out_invoice':
                if move.move_type == 'out_refund':
                    body = _("The following refund %s has been made on this contract. Please check the next invoice date if necessary.", move._get_html_link())
                    for so in move.invoice_line_ids.subscription_id:
                        # Normally, only one subscription_id per move, but we handle multiple contracts as a precaution
                        so.message_post(body=body)
                continue

            log_order_ids = []
            for aml in move.invoice_line_ids:
                if not aml.subscription_id or aml.is_downpayment:
                    continue
                # check if the sale order linked to the invoice is an upsell
                # Upsells don't update the next_invoice_date. Historical data could be unaligned and they could mess up periods.
                sale_order = aml.sale_line_ids.order_id
                upsell_so = sale_order.filtered(lambda so: so.subscription_state == '7_upsell')
                subscription = aml.subscription_id - upsell_so.subscription_id
                all_subscription_ids.add(subscription.id)
                log_order_ids.append(aml.subscription_id.id)
                if upsell_so:
                    log_date_values["upsell"][upsell_so] = {
                        'effective_date': aml.deferred_start_date or move.date,
                        'event_date':  upsell_so.date_order.date(),
                    }
                if subscription:
                    log_date_values["subscription"][subscription] = {
                        'effective_date': aml.deferred_start_date or move.date,
                        'event_date': subscription.date_order.date(),
                    }

        all_subscriptions = self.env['sale.order'].browse(all_subscription_ids)
        for subscription in all_subscriptions:
            # Invoice validation will increment the next invoice date
            if subscription.subscription_state in SUBSCRIPTION_PROGRESS_STATE + ['6_churn']:
                # We increment the next invoice date for progress sub and churn one.
                # Churn sub are reopened in the _post_process of payment transaction.
                # Renewed sub should not be incremented as the renewal is the running contract.
                # Invoices for renewed contract can be posted when the delivered products arrived after the renewal date.
                last_invoice_end_date = subscription.invoice_ids.invoice_line_ids.filtered(lambda aml: aml.subscription_id == subscription)._get_max_invoiced_date()
                subscription.next_invoice_date = last_invoice_end_date + relativedelta(days=1) if last_invoice_end_date else subscription.start_date
                if subscription.order_line._is_all_postpaid():
                    # If all recurring lines are postpaid, we don't rely on deferred_end_date
                    subscription.next_invoice_date += subscription.plan_id.billing_period
                subscription.last_reminder_date = False
            subscription.pending_transaction = False
            if subscription.user_pause_start:
                subscription.user_pause_start = False
        if all_subscriptions:
            # update the renewal quotes to start at the next invoice date values
            renewal_quotes = self.env['sale.order'].search([
                ('subscription_id', 'in', all_subscriptions.ids),
                ('subscription_state', '=', '2_renewal'),
                ('state', 'in', ['draft', 'sent'])])
            for quote in renewal_quotes:
                next_invoice_date = quote.subscription_id.next_invoice_date
                if not quote.start_date or quote.start_date < next_invoice_date:
                    quote.update({
                        'next_invoice_date': next_invoice_date,
                        'start_date': next_invoice_date,
                    })
        if not automatic_invoice:
            all_subscriptions._post_invoice_hook()

        self.env.cr.precommit.add(partial(self.env['sale.order.log']._update_effective_date, log_date_values))
        return posted_moves

    def _message_auto_subscribe_followers(self, updated_values, subtype_ids):
        """ Assignment emails are sent when an account.move is created with a
        different user_id than the current one. For subscriptions it can send
        thousands of email depending on the database size.
        This override prevent the assignment emails to be sent to the
        salesperson.
        """
        res = super()._message_auto_subscribe_followers(updated_values, subtype_ids)
        user_id = updated_values.get('user_id')
        if user_id and self.invoice_line_ids.subscription_id:
            for move in self:
                salesperson = move.invoice_line_ids.subscription_id.user_id
                if salesperson and user_id in salesperson.ids and user_id != self.env.user.id:
                    partner_ids = salesperson.partner_id.ids
                    res = [(v[0], v[1], False) for v in res if v[0] in partner_ids and v[2] == 'mail.message_user_assigned']
        return res

    def _reopen_paid_churned_subscription(self):
        # Re-open churned subscriptions after payment.
        sub_order = self.line_ids.subscription_id
        for order in sub_order:
            cutoff_date = fields.Date.today() - relativedelta(days=order.plan_id.auto_close_limit)
            # Prevent reopening churned subscriptions if cutoff_date is after next_invoice_date
            if order.subscription_state == '6_churn' and order.next_invoice_date >= cutoff_date:
                order.set_open()
