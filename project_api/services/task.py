# -*- coding: utf-8 -*-
# Copyright 2016 Akretion (http://www.akretion.com)
# Benoit Guillot <benoit.guillot@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.addons.component.core import Component
from odoo.addons.base_rest.components.service import to_bool
from odoo.exceptions import UserError, MissingError
import json


class ExternalTaskService(Component):
    _inherit = 'base.rest.service'
    _name = 'external.task.service'
    _collection = 'project.project'
    _usage = 'project_task'

    @property
    def project(self):
        return self.work.project

    def search(self, args, offset, limit, order, count):
        domain = json.loads(args)
        domain += [('project_id', '=', self.project.id)]
        tasks = self.env['project.task'].search(
            domain,
            offset=offset,
            limit=limit,
            order=json.loads(order),
            count=count)
        if tasks:
            if count:
                return tasks.ids
            return tasks.ids
        return self.env['project.tasks'].browse([])

    def read(self, ids, fields, load):
        tasks = self.env['project.task'].search(
            [('id', 'in', json.loads(ids)),
             ('project_id', '=', self.project.id)])
        tasks = tasks.read(
            fields=json.loads(fields),
            load=load)
        if tasks:
            return tasks
        return self.env['project.tasks'].browse([])

    def read_group(self, domain, fields, groupby, offset=0,
            limit=None, orderby=False, lazy=True):
        domain = json.loads(domain)
        domain += [('project_id', '=', self.project.id)]
        groupby = json.loads(groupby)
        fields = json.loads(fields)
        tasks = self.env['project.task'].read_group(
            domain,
            fields,
            groupby,
            offset=offset,
            limit=limit,
            orderby=json.loads(orderby),
            lazy=lazy)
        # Order stages from stage id order and add fold parameter
        if 'stage_name' in groupby:
            ordered_tasks = []
            groupby = ['stage_id']
            fields.append('stage_id')
            stage_tasks = self.env['project.task'].read_group(
                domain,
                fields,
                groupby,
                offset=offset,
                limit=limit,
                orderby=json.loads(orderby),
                lazy=lazy)
            for stage_task in stage_tasks:
                for task in tasks:
                    if task['stage_name'] == stage_task['stage_id'][1]:
                        ordered_task = task
                        ordered_task['__fold'] = stage_task['__fold']
                        ordered_tasks.append(ordered_task)
            tasks = ordered_tasks
        return tasks

    def create(self, **params):
        params['project_id'] = self.project.id
        return self.env['project.task'].create(params).id

    def update(self, _id, vals):
        tasks = self.env['project.task'].search(
            [('id', '=', _id),
             ('project_id', '=', self.project.id)])
        return tasks.write(vals)

    def get_message(self, params):
        messages = self.env['mail.message'].message_read(
            ids=json.loads(params['ids']),
            domain=json.loads(params['domain']),
            message_unload_ids=json.loads(params['message_unload_ids']),
            thread_level=params['thread_level'],
            parent_id=params['parent_id'],
            limit=params['limit'])
        if messages:
            return messages
        return []

    def create_message(self, params):
        kwargs = params['kwargs']
        message = self.pool['project.task'].message_post(
            self._cr, self._uid,
            thread_id=params['thread_id'],
            body=params['body'],
            subject=params['subject'],
            type=params['type'],
            subtype=params['subtype'],
            parent_id=params['parent_id'],
            attachments=params['attachments'],
            context=self._context,
            content_subtype=params['content_subtype'],
            **kwargs)
        if message:
            return message
        return []

    # Validator
    def _validator_read(self):
        return {
            'ids': {'type': 'string'},
            'fields': {'type': 'string'},
            'load': {'type': 'string'},
            'context': {'type': 'string'},
            }

    def _validator_search(self):
        return {
            'args': {'type': 'string'},
            'offset': {'coerce': int},
            'limit': {'coerce': int, 'nullable': True, 'default': 0},
            'order': {'type': 'string'},
            'context': {'type': 'string'},
            'count': {'coerce': to_bool, 'nullable': True},
        }

    def _validator_read_group(self):
        return {
            'domain': {'type': 'string'},
            'offset': {'coerce': int},
            'limit': {'coerce': int, 'nullable': True, 'default': 0},
            'orderby': {'type': 'string'},
            'groupby': {'type': 'string'},
            'fields': {'type': 'string'},
            'context': {'type': 'string'},
            'lazy': {'coerce': to_bool, 'nullable': True},
        }

    def _validator_create(self):
        return {
            'name': {'type': 'string', 'required': True},
            'description': {'type': 'string', 'required': True},
            'external_reviewer_id': {
                'type': 'integer', 'nullable': True, 'default': 0},
            'external_user_id': {'type': 'integer', 'required': True},
            'contact_email': {'type': 'string', 'required': True},
            'contact_mobile': {'type': 'string', 'nullable': True},
            'model_reference': {'type': 'string'},
            'action_id': {'type': 'integer'},
        }

    def _validator_update(self):
        return {
            'vals': {
                'type': 'dict',
                'schema': {
                    'name': {'type': 'string'},
                    'stage_name': {'type': 'string'},
                    'description': {'type': 'string'},
                    'external_reviewer_id': {
                        'type': 'integer', 'nullable': True, 'default': 0},
                }
            }
        }

    def _validator_get_message(self):
        return {
            'ids': {'type': 'string'},
            'domain': {'type': 'string'},
            'message_unload_ids': {'type': 'string'},
            'thread_level': {'coerce': int, 'nullable': True, 'default': 0},
            'context': {'type': 'string'},
            'parent_id': {'coerce': int, 'nullable': True, 'default': 0},
            'limit': {'coerce': int, 'nullable': True, 'default': 0},
            }

    def _validator_create_message(self):
        return {
            'thread_id': {
                'anyof_type': ['integer', 'list'],
                'nullable': True,
                'default': 0},
            'body': {'type': 'string'},
            'subject': {'type': 'string', 'nullable': True},
            'type': {'type': 'string'},
            'subtype': {'type': 'string'},
            'parent_id': {'coerce': int, 'nullable': True, 'default': 0},
            'attachments': {'type': 'string', 'nullable': True},
            'content_subtype': {'type': 'string'},
            'kwargs': {
                'type': 'dict',
                'schema': {
                    'partner_ids': {'type': 'list'},
                    'attachment_ids': {'type': 'list'}
                    }
                }
            }
