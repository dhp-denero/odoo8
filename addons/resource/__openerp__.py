# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name' : 'Resource',
    'version' : '1.1',
    'author' : 'OpenERP SA',
    'category' : 'Hidden/Dependency',
    'website' : 'http://www.openerp.com',
    'description': """
Module for resource management.
===============================

A resource represent something that can be scheduled (a developer on a task or a
work center on manufacturing orders). This module manages a resource calendar
associated to every resource. It also manages the leaves of every resource.
    """,
    'author': 'OpenERP SA',
    'website': 'http://www.openerp.com',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'security/resource_security.xml',
        'resource_view.xml',
    ],
    'demo': ['resource_demo.xml'],
    'test': [
        'test/resource.yml',
        'test/duplicate_resource.yml',
    ],
    'installable': True,
    'auto_install': False,
}
