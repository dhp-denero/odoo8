# -*- coding: utf-8 -*-

from openerp.osv import fields, osv
from openerp.tools.translate import _


class crm_team(osv.Model):
    _inherit = 'crm.team'
    _inherits = {'mail.alias': 'alias_id'}

    def _get_default_stage_ids(self, cr, uid, context=None):
        return [
            (0, 0, {
                'name': _('New'),
                'sequence': 1,
                'probability': 10.0,
                'on_change': True,
                'fold': False,
                'type': 'both',
            }),
            (0, 0, {
                'name': _('Won'),
                'sequence': 50,
                'probability': 100.0,
                'on_change': True,
                'fold': True,
                'type': 'both',
            })]

    _columns = {
        'resource_calendar_id': fields.many2one('resource.calendar', "Working Time", help="Used to compute open days"),
        'stage_ids': fields.many2many('crm.stage', 'crm_team_stage_rel', 'team_id', 'stage_id', 'Stages'),
        'use_leads': fields.boolean('Leads',
            help="The first contact you get with a potential customer is a lead you qualify before converting it into a real business opportunity. Check this box to manage leads in this sales team."),
        'use_opportunities': fields.boolean('Opportunities', help="Check this box to manage opportunities in this sales team."),
        'alias_id': fields.many2one('mail.alias', 'Alias', ondelete="restrict", required=True, help="The email address associated with this team. New emails received will automatically create new leads assigned to the team."),
    }

    def _auto_init(self, cr, context=None):
        """Installation hook to create aliases for all lead and avoid constraint errors."""
        return self.pool.get('mail.alias').migrate_to_alias(cr, self._name, self._table, super(crm_team, self)._auto_init,
            'crm.lead', self._columns['alias_id'], 'name', alias_prefix='Lead+', alias_defaults={}, context=context)

    _defaults = {
        'stage_ids': _get_default_stage_ids,
        'use_opportunities': True,
    }

    def onchange_use_leads(self, cr, uid, ids, use_leads, context=None):
        if not use_leads:
            return {'value': {'alias_name': False}}
        return {'value': {}}

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        create_context = dict(context, alias_model_name='crm.lead', alias_parent_model_name=self._name)
        generate_alias_name = self.pool['ir.values'].get_default(cr, uid, 'sales.config.settings', 'generate_sales_team_alias')
        if generate_alias_name and not vals.get('alias_name'):
            vals['alias_name'] = vals.get('name')
        team_id = super(crm_team, self).create(cr, uid, vals, context=create_context)
        team = self.browse(cr, uid, team_id, context=context)
        self.pool.get('mail.alias').write(cr, uid, [team.alias_id.id], {'alias_parent_thread_id': team_id, 'alias_defaults': {'team_id': team_id, 'type': 'lead'}}, context=context)
        return team_id

    def unlink(self, cr, uid, ids, context=None):
        # Cascade-delete mail aliases as well, as they should not exist without the sales team.
        mail_alias = self.pool.get('mail.alias')
        alias_ids = [team.alias_id.id for team in self.browse(cr, uid, ids, context=context) if team.alias_id]
        res = super(crm_team, self).unlink(cr, uid, ids, context=context)
        mail_alias.unlink(cr, uid, alias_ids, context=context)
        return res
