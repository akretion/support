from odoo import http
from odoo.http import request
from odoo.addons.mail.controllers.discuss import DiscussController

class DiscussControllerSupport(DiscussController):

    @http.route('/mail/thread/messages', methods=['POST'], type='json', auth='user')
    def mail_thread_messages(self, thread_model, thread_id, max_id=None, min_id=None, limit=30, **kwargs):
        if thread_model == "external.task":
            return request.env['mail.message']._message_fetch(domain=[
                ('res_id', '=', int(thread_id)),
                ('model', '=', thread_model),
                ('message_type', '!=', 'user_notification'),
            ], max_id=max_id, min_id=min_id, limit=limit)
        return super().mail_thread_messages(thread_model, thread_id, max_id=max_id, min_id=min_id, limit=limit, **kwargs)

    @http.route('/mail/message/post', methods=['POST'], type='json', auth='public')
    def mail_message_post(self, thread_model, thread_id, post_data, **kwargs):
        if thread_model == "external.task":
            thread = request.env[thread_model].browse(int(thread_id)).exists()
            message = thread.message_post(**{key: value for key, value in post_data.items() if key in self._get_allowed_message_post_params()})
            external_ids = [int(mid.replace("external/", "")) for mid in message.ids]
            return request.env[thread_model].message_get(external_ids)[0]
        else:
            return super().mail_message_post(thread_model, thread_id, post_data, **kwargs)

