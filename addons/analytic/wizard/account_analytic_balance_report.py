# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
from openerp.osv import fields, osv


class account_analytic_balance(osv.osv_memory):
    _name = 'account.analytic.balance'
    _description = 'Account Analytic Balance'

    _columns = {
        'date1': fields.date('Start of period', required=True),
        'date2': fields.date('End of period', required=True),
        'empty_acc': fields.boolean('Empty Accounts ? ', help='Check if you want to display Accounts with 0 balance too.'),
    }

    _defaults = {
        'date1': lambda *a: time.strftime('%Y-01-01'),
        'date2': lambda *a: time.strftime('%Y-%m-%d')
    }

    def check_report(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        data = self.read(cr, uid, ids)[0]
        datas = {
            'ids': context.get('active_ids', []),
            'model': 'account.analytic.account',
            'form': data
        }

        datas['form']['active_ids'] = context.get('active_ids', False)

        return self.pool['report'].get_action(cr, uid, [], 'account.report_analyticbalance', data=datas, context=context)
