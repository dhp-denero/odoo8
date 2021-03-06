# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from openerp.osv import fields, osv

class stock_location_path(osv.osv):
    _inherit = "stock.location.path"
    _columns = {
        'invoice_state': fields.selection([
            ("invoiced", "Invoiced"),
            ("2binvoiced", "To Be Invoiced"),
            ("none", "Not Applicable")], "Invoice Status",),
    }
    _defaults = {
        'invoice_state': '',
    }

    def _prepare_push_apply(self, cr, uid, rule, move, context=None):
        res = super(stock_location_path, self)._prepare_push_apply(cr, uid, rule, move, context=context)
        res['invoice_state'] = rule.invoice_state or 'none'
        return res

#----------------------------------------------------------
# Procurement Rule
#----------------------------------------------------------
class procurement_rule(osv.osv):
    _inherit = 'procurement.rule'
    _columns = {
        'invoice_state': fields.selection([
            ("invoiced", "Invoiced"),
            ("2binvoiced", "To Be Invoiced"),
            ("none", "Not Applicable")], "Invoice Status",),
        }
    _defaults = {
        'invoice_state': '',
    }

#----------------------------------------------------------
# Procurement Order
#----------------------------------------------------------


class procurement_order(osv.osv):
    _inherit = "procurement.order"
    _columns = {
        'invoice_state': fields.selection([("invoiced", "Invoiced"),
            ("2binvoiced", "To Be Invoiced"),
            ("none", "Not Applicable")
         ], "Invoice Control"),
        }

    def _run_move_create(self, cr, uid, procurement, context=None):
        res = super(procurement_order, self)._run_move_create(cr, uid, procurement, context=context)
        res.update({'invoice_state': procurement.rule_id.invoice_state or procurement.invoice_state or 'none'})
        return res


#----------------------------------------------------------
# Move
#----------------------------------------------------------

class stock_move(osv.osv):
    _inherit = "stock.move"
    _columns = {
        'invoice_state': fields.selection([("invoiced", "Invoiced"),
            ("2binvoiced", "To Be Invoiced"),
            ("none", "Not Applicable")], "Invoice Control",
            select=True, required=True, track_visibility='onchange',
            states={'draft': [('readonly', False)]}),
        }
    _defaults = {
        'invoice_state': lambda *args, **argv: 'none'
    }

    def _get_master_data(self, cr, uid, move, inv_type, context=None):
        ''' returns a tuple (browse_record(res.partner), ID(res.users), ID(res.currency)'''
        currency = move.company_id.currency_id.id
        partner = move.picking_id and move.picking_id.partner_id
        if partner and partner.property_product_pricelist and inv_type in ('out_invoice', 'out_refund'):
            currency = partner.property_product_pricelist.currency_id.id
        return partner, uid, currency

    def _get_price_unit_invoice(self, cr, uid, move_line, type, context=None):
        """ Gets price unit for invoice
        @param move_line: Stock move lines
        @param type: Type of invoice
        @return: The price unit for the move line
        """
        if context is None:
            context = {}
        if type in ('in_invoice', 'in_refund'):
            return move_line.price_unit
        else:
            # If partner given, search price in its sale pricelist
            if move_line.partner_id and move_line.partner_id.property_product_pricelist:
                pricelist_obj = self.pool.get("product.pricelist")
                pricelist = move_line.partner_id.property_product_pricelist.id
                price = pricelist_obj.price_get(cr, uid, [pricelist],
                        move_line.product_id.id, move_line.product_uom_qty, move_line.partner_id.id, {
                            'uom': move_line.product_uom.id,
                            'date': move_line.date,
                            })[pricelist]
                if price:
                    return price
        return move_line.product_id.list_price

    def _get_invoice_line_vals(self, cr, uid, move, partner, inv_type, context=None):
        fp_obj = self.pool.get('account.fiscal.position')
        # Get account_id
        if inv_type in ('out_invoice', 'out_refund'):
            account_id = move.product_id.property_account_income_id.id
            if not account_id:
                account_id = move.product_id.categ_id.property_account_income_categ_id.id
        else:
            account_id = move.product_id.property_account_expense_id.id
            if not account_id:
                account_id = move.product_id.categ_id.property_account_expense_categ_id.id
        fiscal_position = partner.property_account_position_id
        account_id = fp_obj.map_account(cr, uid, fiscal_position, account_id)

        # set UoS if it's a sale and the picking doesn't have one
        uos_id = move.product_uom.id
        quantity = move.product_uom_qty
        if move.product_uos:
            uos_id = move.product_uos.id
            quantity = move.product_uos_qty

        taxes_ids = self._get_taxes(cr, uid, move, context=context)

        return {
            'name': move.name,
            'account_id': account_id,
            'product_id': move.product_id.id,
            'uos_id': uos_id,
            'quantity': quantity,
            'price_unit': self._get_price_unit_invoice(cr, uid, move, inv_type),
            'invoice_line_tax_ids': [(6, 0, taxes_ids)],
            'discount': 0.0,
            'account_analytic_id': False,
            'move_id': move.id,
        }

    def _get_moves_taxes(self, cr, uid, moves, inv_type, context=None):
        #extra moves with the same picking_id and product_id of a move have the same taxes
        extra_move_tax = {}
        is_extra_move = {}
        for move in moves:
            if move.picking_id:
                is_extra_move[move.id] = True
                if not (move.picking_id, move.product_id) in extra_move_tax:
                    extra_move_tax[move.picking_id, move.product_id] = 0
            else:
                is_extra_move[move.id] = False
        return (is_extra_move, extra_move_tax)

#----------------------------------------------------------
# Picking
#----------------------------------------------------------

class stock_picking(osv.osv):
    _inherit = 'stock.picking'
    def __get_invoice_state(self, cr, uid, ids, name, arg, context=None):
        result = {}
        for pick in self.browse(cr, uid, ids, context=context):
            result[pick.id] = 'none'
            for move in pick.move_lines:
                if move.invoice_state == 'invoiced':
                    result[pick.id] = 'invoiced'
                elif move.invoice_state == '2binvoiced':
                    result[pick.id] = '2binvoiced'
                    break
        return result

    def __get_picking_move(self, cr, uid, ids, context={}):
        res = []
        for move in self.pool.get('stock.move').browse(cr, uid, ids, context=context):
            if move.picking_id and move.invoice_state != move.picking_id.invoice_state:
                res.append(move.picking_id.id)
        return res

    def _set_inv_state(self, cr, uid, picking_id, name, value, arg, context=None):
        pick = self.browse(cr, uid, picking_id, context=context)
        moves = [x.id for x in pick.move_lines]
        move_obj= self.pool.get("stock.move")
        move_obj.write(cr, uid, moves, {'invoice_state': value}, context=context)

    _columns = {
        'invoice_state': fields.function(__get_invoice_state, type='selection', selection=[
            ("invoiced", "Invoiced"),
            ("2binvoiced", "To Be Invoiced"),
            ("none", "Not Applicable")
          ], string="Invoice Control", required=True,
        fnct_inv = _set_inv_state,
        store={
            'stock.picking': (lambda self, cr, uid, ids, c={}: ids, ['state'], 10),
            'stock.move': (__get_picking_move, ['picking_id', 'invoice_state'], 10),
        },
        ),
    }
    _defaults = {
        'invoice_state': lambda *args, **argv: 'none'
    }

    def _create_invoice_from_picking(self, cr, uid, picking, vals, context=None):
        ''' This function simply creates the invoice from the given values. It is overriden in delivery module to add the delivery costs.
        '''
        invoice_obj = self.pool.get('account.invoice')
        return invoice_obj.create(cr, uid, vals, context=context)

    def _get_partner_to_invoice(self, cr, uid, picking, context=None):
        """ Gets the partner that will be invoiced
            Note that this function is inherited in the sale and purchase modules
            @param picking: object of the picking for which we are selecting the partner to invoice
            @return: object of the partner to invoice
        """
        return picking.partner_id and picking.partner_id.id
        
    def action_invoice_create(self, cr, uid, ids, journal_id, group=False, type='out_invoice', context=None):
        """ Creates invoice based on the invoice state selected for picking.
        @param journal_id: Id of journal
        @param group: Whether to create a group invoice or not
        @param type: Type invoice to be created
        @return: Ids of created invoices for the pickings
        """
        context = context or {}
        todo = {}
        anglo_saxon_accounting = False
        for picking in self.browse(cr, uid, ids, context=context):
            if picking.company_id.anglo_saxon_accounting:
                anglo_saxon_accounting = True
            partner = self._get_partner_to_invoice(cr, uid, picking, context)
            #grouping is based on the invoiced partner
            if group:
                key = partner
            else:
                key = picking.id
            for move in picking.move_lines:
                if move.invoice_state == '2binvoiced':
                    if (move.state != 'cancel') and not move.scrapped:
                        todo.setdefault(key, [])
                        todo[key].append(move)
        invoices = []
        for moves in todo.values():
            invoices += self._invoice_create_line(cr, uid, moves, journal_id, type, context=context)
        
        #For anglo-saxon accounting
        if anglo_saxon_accounting:
            if type in ('in_invoice', 'in_refund'):
                for inv in self.pool.get('account.invoice').browse(cr, uid, invoices, context=context):
                    for ol in inv.invoice_line_ids:
                        if ol.product_id.type != 'service':
                            oa = ol.product_id.property_stock_account_input and ol.product_id.property_stock_account_input.id
                            if not oa:
                                oa = ol.product_id.categ_id.property_stock_account_input_categ_id and ol.product_id.categ_id.property_stock_account_input_categ_id.id        
                            if oa:
                                fpos = ol.invoice_id.fiscal_position_id or False
                                a = self.pool.get('account.fiscal.position').map_account(cr, uid, fpos, oa)
                                self.pool.get('account.invoice.line').write(cr, uid, [ol.id], {'account_id': a})
        return invoices

    def _get_invoice_vals(self, cr, uid, key, inv_type, journal_id, moves, context=None):
        if context is None:
            context = {}
        partner, currency_id, company_id, user_id = key
        if inv_type in ('out_invoice', 'out_refund'):
            account_id = partner.property_account_receivable_id.id
            payment_term = partner.property_payment_term_id.id or False
        else:
            account_id = partner.property_account_payable_id.id
            payment_term = partner.property_supplier_payment_term_id.id or False
        return {
            'origin': ','.join(list(set([x.picking_id.name for x in moves]))),
            'date_invoice': context.get('date_inv', False),
            'user_id': user_id,
            'partner_id': partner.id,
            'account_id': account_id,
            'payment_term_id': payment_term,
            'type': inv_type,
            'fiscal_position_id': partner.property_account_position_id.id,
            'company_id': company_id,
            'currency_id': currency_id,
            'journal_id': journal_id,
        }

    def get_service_line_vals(self, cr, uid, moves, partner, inv_type, context=None):
        return []

    def _invoice_create_line(self, cr, uid, moves, journal_id, inv_type='out_invoice', context=None):
        invoice_obj = self.pool.get('account.invoice')
        move_obj = self.pool.get('stock.move')
        invoices = {}
        is_extra_move, extra_move_tax = move_obj._get_moves_taxes(cr, uid, moves, inv_type, context=context)

        product_price_unit = {}
        invoices_moves = {}
        for move in moves:
            company = move.company_id
            origin = move.picking_id.name
            partner, _user_id, currency_id = move_obj._get_master_data(cr, uid, move, inv_type, context=context)
            # Force user_id to be current user, to avoid creating multiple invoices when lines
            # have been sold by different salesmen
            _user_id = uid
            key = (partner, currency_id, company.id, _user_id)
            if key not in invoices_moves:
                invoices_moves[key] = [move]
            else:
                invoices_moves[key] += [move]

        inv_moves={}
        for key in invoices_moves.keys():
            moves_key = invoices_moves[key]
            invoice_vals = self._get_invoice_vals(cr, uid, key, inv_type, journal_id, moves_key, context=context)
            partner = key[0]
            invoice_line_vals = []
            for move in moves_key:
                line_vals = move_obj._get_invoice_line_vals(cr, uid, move, partner, inv_type, context=context)
                if not is_extra_move[move.id]:
                    product_price_unit[line_vals['product_id'], line_vals['uos_id']] = line_vals['price_unit']
                if is_extra_move[move.id] and (line_vals['product_id'], line_vals['uos_id']) in product_price_unit:
                    line_vals['price_unit'] = product_price_unit[line_vals['product_id'], line_vals['uos_id']]
                if is_extra_move[move.id]:
                    desc = (inv_type in ('out_invoice', 'out_refund') and move.product_id.product_tmpl_id.description_sale) or \
                        (inv_type in ('in_invoice','in_refund') and move.product_id.product_tmpl_id.description_purchase)
                    line_vals['name'] += ' ' + desc if desc else ''
                    if extra_move_tax[move.picking_id, move.product_id]:
                        line_vals['invoice_line_tax_ids'] = extra_move_tax[move.picking_id, move.product_id]
                    #the default product taxes
                    elif (0, move.product_id) in extra_move_tax:
                        line_vals['invoice_line_tax_ids'] = extra_move_tax[0, move.product_id]
                invoice_line_vals += [(0, 0, line_vals)]
            invoice_vals['invoice_line_ids'] = invoice_line_vals
            invoice_vals['invoice_line_ids'] += self.get_service_line_vals(cr, uid, moves_key, partner, inv_type, context=context)
            invoice_id = invoice_obj.create(cr, uid, invoice_vals, context=context)
            move_obj.write(cr, uid, [x.id for x in moves_key], {'invoice_state': 'invoiced'}, context=context)
            inv_moves[invoice_id] = moves_key
        return inv_moves

    def _prepare_values_extra_move(self, cr, uid, op, product, remaining_qty, context=None):
        """
        Need to pass invoice_state of picking when an extra move is created which is not a copy of a previous
        """
        res = super(stock_picking, self)._prepare_values_extra_move(cr, uid, op, product, remaining_qty, context=context)
        res.update({'invoice_state': op.picking_id.invoice_state})
        if op.linked_move_operation_ids:
            res.update({'price_unit': op.linked_move_operation_ids[-1].move_id.price_unit})
        return res


class stock_picking_type(osv.Model):
    _inherit = "stock.picking.type"

    def _compute_count_picking_invoiced(self, cr, uid, ids, field_name, arg, context=None):
        result = dict.fromkeys(ids, 0)
        picking_data = self.pool['stock.picking'].read_group(
            cr, uid, [('picking_type_id', 'in', ids), ('invoice_state', '=', '2binvoiced'), ('state', '=', 'done')],
            ['picking_type_id'], ['picking_type_id'], context=context)
        for data in picking_data:
            result[data['picking_type_id'][0]] = data['picking_type_id_count']
        return result

    _columns = {
        'count_picking_invoiced': fields.function(_compute_count_picking_invoiced, type='integer'),
    }
