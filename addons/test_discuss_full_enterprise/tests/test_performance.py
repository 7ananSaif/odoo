# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.test_discuss_full.tests.test_performance import TestDiscussFullPerformance

# Queries for _query_count_init_store:
#   1: odoobot format:
#       - search ai_agent (_compute_im_status ai override)
#   1: fetch voip_provider (_res_users_settings_format)
#   1: search mail_activity_type (voip_config)
#   1: search_count voip_call (_get_number_of_missed_calls)
TestDiscussFullPerformance._query_count_init_store += 4
# Queries for _query_count_init_messaging:
#   1: _process_request_for_all: channel add: member _to_store: partner _to_store:
#       - search ai_agent (_compute_im_status ai override)
TestDiscussFullPerformance._query_count_init_messaging += 1
# Queries for _query_count_init_messaging:
#   1: channel _to_store_defaults: member _to_store: partner _to_store:
#       - search ai_agent (_compute_im_status ai override)
TestDiscussFullPerformance._query_count_discuss_channels += 1

old_get_init_store_data_result = TestDiscussFullPerformance._get_init_store_data_result


def _get_init_store_data_result(self):
    res = old_get_init_store_data_result(self)
    provider = self.env.ref("voip.default_voip_provider").sudo()
    channel_types_with_seen_infos = res["Store"]["channel_types_with_seen_infos"] + ["whatsapp"]
    res["Store"].update(
        {
            "channel_types_with_seen_infos": sorted(channel_types_with_seen_infos),
            "hasDocumentsUserGroup": False,
            "helpdesk_livechat_active": False,
            "has_access_create_ticket": False,
            "voipConfig": {
                "callActivityTypeId": self.env.ref("mail.mail_activity_data_call").id,
                "mode": "demo",
                "missedCalls": 0,
                "pbxAddress": "localhost",
                "recordingPolicy": provider.recording_policy or "disabled",
                "webSocketUrl": provider.ws_server or "ws://localhost",
                "transcriptionPolicy": provider.transcription_policy or "disabled",
            },
        }
    )
    res["Store"]["settings"].update(
        {
            "homemenu_config": False,
            "how_to_call_on_mobile": "ask",
            "do_not_disturb_until_dt": False,
            "external_device_number": False,
            "onsip_auth_username": False,
            "should_call_from_another_device": False,
            "voip_provider_id": (provider.id, provider.name),
            "voip_secret": False,
            "voip_username": False,
            "is_discuss_sidebar_category_whatsapp_open": True,
            "color_scheme": "system",
        }
    )
    return res


TestDiscussFullPerformance._get_init_store_data_result = _get_init_store_data_result
