"""
Регистрация всех маршрутов приложения.
"""

from aiohttp import web

# Import handlers from modules
from auth.handlers import handle_login, handle_ui_login, handle_ui_session, handle_get_device_tokens, handle_revoke_device_token
from auth.connection_request_handlers import (
    handle_connection_request,
    handle_connection_request_status,
    handle_admin_connection_policy_get,
    handle_admin_connection_policy_patch,
    handle_admin_connection_requests_list,
    handle_admin_connection_request_approve,
    handle_admin_connection_request_reject,
)
from auth.admin_users_handlers import (
    handle_admin_users_list,
    handle_admin_users_post,
    handle_admin_users_get,
    handle_admin_users_patch,
    handle_admin_users_password_post,
    handle_admin_users_deactivate_post,
    handle_users_me_password_post,
)
from agents.handlers import (
    handle_get_agents,
    handle_get_devices,
    handle_get_device,
    handle_get_device_update_diagnostics,
    handle_get_pending_connections,
    handle_device_check,
    handle_delete_device,
)
from agents.agent_builds_handlers import (
    handle_upload_agent_build,
    handle_list_agent_builds,
    handle_delete_agent_build,
    handle_download_agent_build,
    handle_get_agent_rollout_policy,
    handle_patch_agent_rollout_policy,
    handle_get_device_update_recommendation,
    handle_update_device_agent,
    handle_bulk_update_agents,
)
from tickets.public_queue_handlers import (
    handle_public_queues,
    handle_public_queue_tickets,
    handle_public_queue_stats,
)
from tickets.public_ticket_handlers import (
    handle_public_ticket_authorize,
    handle_public_ticket_create,
)
from tickets.form_pack_handlers import (
    handle_ticket_form_pack_current,
    handle_ticket_form_pack_detail,
    handle_ticket_form_pack_save,
    handle_ticket_form_pack_set_preferred,
    handle_ticket_form_packs_list,
)
from tickets.handlers import (
    handle_tickets_create,
    handle_tickets_create_preview,
    handle_ticket_get,
    handle_tickets_list,
    handle_ticket_send_message,
    handle_ticket_close,
    handle_ticket_status,
    handle_ticket_get_snapshot,
    handle_ticket_get_observer_summary,
    handle_ticket_reroute,
    handle_ticket_classify,
    handle_ticket_queue,
    handle_ticket_priority,
    handle_ticket_order,
    handle_ticket_queue_order_reset,
    handle_ticket_assign,
    handle_tickets_archive,
    handle_tickets_bulk_assign,
    handle_ticket_bind_device,
    handle_ticket_mark_read,
    handle_ticket_requester_profile,
    handle_ticket_sla_get,
    handle_ticket_worklogs_post,
    handle_ticket_worklogs_list,
    handle_ticket_worklog_total,
    handle_ticket_links_post,
    handle_ticket_links_list,
    handle_ticket_links_delete,
    handle_ticket_parent_post,
    handle_ticket_parent_delete,
    handle_ticket_watchers_post,
    handle_ticket_watchers_list,
    handle_ticket_watchers_delete,
    handle_ticket_kb_links_post,
    handle_ticket_kb_links_list,
    handle_ticket_kb_links_delete,
    handle_ticket_resolution_codes_list,
    handle_ticket_metrics_backlog,
    handle_ticket_metrics_aging,
    handle_ticket_metrics_sla,
    handle_ticket_metrics_reopen_rate,
    handle_ticket_metrics_top,
    handle_ticket_metrics_status_age,
    handle_notifications_list,
    handle_notifications_unread_count,
    handle_notifications_read_all,
    handle_notification_preferences_get,
    handle_notification_preferences_post,
    handle_notification_mark_read,
    handle_problems_create,
    handle_problems_list,
    handle_problem_get,
    handle_problem_status_post,
    handle_problem_tickets_post,
    handle_problem_tickets_delete,
    handle_ticket_problems_get,
    handle_ticket_change_links_post,
    handle_ticket_change_links_list,
    handle_ticket_change_links_delete,
)
from tools.handlers import handle_get_tools, handle_tools_run
from playbook_handlers import handle_start_playbook_run
from websocket.agent_handler import websocket_handler
from websocket.ui_handler import websocket_ui_handler
from uploads.handlers import handle_upload, handle_artifact_download
from static_pages.handlers import (
    handle_index,
    handle_admin_page,
    handle_login_page,
    handle_support_page,
    handle_favicon,
    handle_web_shared_js,
    handle_admin_css,
    handle_admin_js,
    handle_login_css,
    handle_login_js,
    handle_support_css,
    handle_support_js,
    handle_ticket_page,
    handle_ticket_page_by_id,
    handle_ticket_css,
    handle_ticket_js,
    handle_chat_debug,
    handle_chat_ws,
    handle_test_simple,
    handle_ws_ui_test,
    handle_modules_page,
    handle_public_queue_page,
    handle_public_queue_css,
    handle_public_queue_js,
    handle_help_page,
    handle_help_css,
    handle_help_js,
    handle_admin_modules_workbench_html,
    handle_admin_modules_workbench_js,
    handle_admin_ticket_forms_builder_html,
    handle_admin_ticket_forms_builder_js,
)
from static_pages.webapp_assets import (
    handle_webapp_asset,
    handle_webapp_page,
    handle_webapp_public_asset,
)
from api.admin import handle_admin_run_tool
from tickets.admin_config_handlers import (
    handle_admin_queues_list,
    handle_admin_queues_post,
    handle_admin_queues_get,
    handle_admin_queues_patch,
    handle_admin_queue_members_list,
    handle_admin_queue_members_put,
    handle_admin_queue_members_delete,
    handle_admin_resolution_codes_list,
    handle_admin_resolution_codes_post,
    handle_admin_resolution_codes_patch,
    handle_admin_resolution_codes_delete,
    handle_admin_routing_rules_list,
    handle_admin_routing_rules_post,
    handle_admin_routing_rules_patch,
    handle_admin_sla_policies_list,
    handle_admin_sla_policies_post,
    handle_admin_sla_policies_patch,
    handle_admin_sla_policies_set_default,
    handle_admin_sla_targets_get,
    handle_admin_sla_targets_put,
    handle_admin_priority_matrix_get,
    handle_admin_priority_matrix_put,
    handle_admin_calendars_list,
    handle_admin_calendars_post,
    handle_admin_calendars_patch,
    handle_admin_ola_targets_get,
    handle_admin_ola_targets_put,
    handle_admin_audit_list,
)
from api.protocol import handle_protocol
from api.commands import handle_send_command, handle_check_functions, handle_smoke_run
from api.events import handle_get_ticket_events, handle_get_device_events, handle_ticket_messages
from api.operations import (
    handle_get_operations,
    handle_get_operation,
    handle_cancel_operation,
    handle_approve_consent,
    handle_deny_consent
)
from web_api.session_handlers import (
    handle_web_session_login,
    handle_web_session_logout,
    handle_web_session_me,
)
from web_api.access_handlers import (
    handle_web_admin_access_audit,
    handle_web_admin_access_catalog,
    handle_web_admin_access_create_group,
    handle_web_admin_access_effective,
    handle_web_admin_access_group_members,
    handle_web_admin_access_group_permissions,
    handle_web_admin_access_group_queues,
    handle_web_admin_access_summary,
    handle_web_admin_access_update_group,
)
from web_api.support_handlers import (
    handle_web_support_assign_ticket,
    handle_web_support_bootstrap,
    handle_web_support_approval_decision,
    handle_web_support_change_priority,
    handle_web_support_change_queue,
    handle_web_support_change_status,
    handle_web_support_reroute_ticket,
    handle_web_support_ticket_passport,
    handle_web_support_ticket_passport_evidence,
    handle_web_support_ticket_passport_evidence_candidates,
    handle_web_support_ticket_passport_evidence_link,
    handle_web_support_ticket_passport_evidence_update,
    handle_web_support_ticket_passport_generate,
    handle_web_support_ticket_passport_knowledge_draft,
    handle_web_support_ticket_passport_patch,
    handle_web_support_queue,
    handle_web_support_workspace_summary,
    handle_web_support_run_playbook,
    handle_web_support_run_tool,
    handle_web_support_send_message,
    handle_web_support_ticket_detail,
    handle_web_support_ticket_playbooks,
    handle_web_support_ticket_tools,
    handle_web_support_ticket_workspace,
)
from web_api.admin_handlers import (
    handle_web_admin_bootstrap,
    handle_web_admin_device_update_run,
    handle_web_admin_device_updates,
    handle_web_admin_device_token_revoke,
    handle_web_admin_device_tokens,
    handle_web_admin_devices,
    handle_web_admin_devices_cleanup_env_duplicates,
    handle_web_admin_forms_current,
    handle_web_admin_forms_route_preview,
    handle_web_admin_forms_save,
    handle_web_admin_helpdesk_model_policies,
    handle_web_admin_helpdesk_model_policy_deactivate,
    handle_web_admin_helpdesk_model_policy_diff,
    handle_web_admin_helpdesk_model_policy_rollback,
    handle_web_admin_helpdesk_model_publish_policy,
    handle_web_admin_helpdesk_model_publish_form_schema,
    handle_web_admin_helpdesk_model_publish_smart_view,
    handle_web_admin_helpdesk_model_publish_ticket_type,
    handle_web_admin_helpdesk_model_publish_from_form,
    handle_web_admin_helpdesk_model_republish_legacy_forms,
    handle_web_admin_helpdesk_model_ticket_type_deactivate,
    handle_web_admin_helpdesk_model_ticket_type_rollback,
    handle_web_admin_modules,
    handle_web_admin_patch_modules_rollout_settings,
    handle_web_admin_playbooks_catalog,
    handle_web_admin_playbooks_save,
    handle_web_admin_observer_quick,
    handle_web_admin_observer_trace_detail,
    handle_web_admin_observer_traces,
    handle_web_admin_set_module_preferred_version,
)
from web_api.registry_handlers import (
    handle_registry_options,
    handle_registry_profile_upsert,
    handle_web_admin_registry,
)
from web_api.reports_handlers import handle_web_reports_summary
from web_api.settings_handlers import handle_web_settings_payload, handle_web_settings_workflow_profiles_put
from web_api.realtime_handlers import handle_web_realtime_bootstrap
from chat.handlers import (
    handle_chat_start,
    handle_chat_raise,
    handle_chat_send,
    handle_active_chats,
    handle_chat_events
)
from modules.handlers import (
    handle_modules_ping,
    handle_install_module_package,
    handle_list_installed_modules,
    handle_activate_module,
    handle_rollback_module,
    handle_deactivate_module,
    handle_smoke_install_and_run,
    handle_upload_module,
    handle_create_module,
    handle_bulk_install_modules,
    handle_download_module,
    handle_list_modules,
    handle_list_modules_workbench,
    handle_cleanup_missing_modules,
    handle_get_module_detail,
    handle_get_module_workbench_detail,
    handle_get_module_rollout_settings,
    handle_set_module_preferred_version,
    handle_patch_module_rollout_settings,
    handle_get_module_authoring_catalog,
    handle_validate_module_authoring,
    handle_publish_module_authoring,
    handle_save_module_workbench,
    handle_validate_module_workbench,
    handle_list_module_live_test_candidates,
    handle_run_module_live_test,
    handle_delete_module,
    handle_get_device_modules,
    handle_get_device_toolset,
    handle_install_module,
    handle_activate_module_new,
    handle_deactivate_module_new,
    handle_sync_modules,
    handle_remove_module_version,
    handle_remove_module,
    handle_verify_module,
    handle_debug_modules,
    handle_get_desired_diff,
    handle_trigger_reconcile
)
from jobs.handlers import handle_get_job_events, handle_start_job
from tech.handlers import (
    handle_observer_settings_get,
    handle_observer_settings_patch,
    handle_tech_diagnostics_bundle,
    handle_tech_observer_search,
    handle_tech_observer_quick,
    handle_tech_overview,
    handle_tech_alerts,
    handle_tech_agents_audit,
    handle_tech_agent_timeline,
    handle_tech_agent_action,
    handle_tech_ticket_lifecycle,
    handle_tech_users_audit,
    handle_tech_admin_config_audit,
    handle_tech_logs,
    handle_tech_dismiss_item,
    handle_tech_operations_stuck,
    handle_tech_traces_runtime,
    handle_tech_traces_search,
    handle_tech_trace_detail,
    handle_tech_traces_rebuild,
    handle_tech_degradations_search,
    handle_tech_signatures_search,
    handle_tech_signature_detail,
)


async def handle_health(_request: web.Request) -> web.Response:
    """GET /api/health — для smoke-тестов и мониторинга (без авторизации)."""
    return web.json_response({"status": "ok", "deploy_check": "verified", "run": "2025-03-17"})


def setup_routes(app: web.Application) -> None:
    """
    Регистрирует все маршруты приложения.
    
    Args:
        app: Экземпляр aiohttp.web.Application
    """
    app.add_routes([
        # ============================================================================
        # WebSocket Endpoints
        # ============================================================================
        web.get('/ws', websocket_handler),
        web.get('/ws_ui', websocket_ui_handler),
        
        # ============================================================================
        # Static Pages
        # ============================================================================
        web.get('/', handle_index),
        web.get('/favicon.ico', handle_favicon),
        web.get('/favicon.svg', handle_webapp_public_asset),
        web.get('/assets/{asset_path:.*}', handle_webapp_asset),
        web.get('/app', handle_webapp_page),
        web.get('/app/{tail:.*}', handle_webapp_page),
        web.get('/login', handle_login_page),
        web.get('/login.css', handle_login_css),
        web.get('/login.js', handle_login_js),
        web.get('/admin', handle_admin_page),
        web.get('/admin.css', handle_admin_css),
        web.get('/admin.js', handle_admin_js),
        web.get('/admin_modules_workbench.html', handle_admin_modules_workbench_html),
        web.get('/admin_modules_workbench.js', handle_admin_modules_workbench_js),
        web.get('/admin_ticket_forms_builder.html', handle_admin_ticket_forms_builder_html),
        web.get('/admin_ticket_forms_builder.js', handle_admin_ticket_forms_builder_js),
        web.get('/web_shared.js', handle_web_shared_js),
        web.get('/support', handle_support_page),
        web.get('/support.css', handle_support_css),
        web.get('/support.js', handle_support_js),
        web.get('/queue', handle_public_queue_page),
        web.get('/queue/{queue_key}', handle_public_queue_page),
        web.get('/public_queue.css', handle_public_queue_css),
        web.get('/public_queue.js', handle_public_queue_js),
        web.get('/help', handle_help_page),
        web.get('/help.css', handle_help_css),
        web.get('/help.js', handle_help_js),
        web.get('/ticket.html', handle_ticket_page),
        web.get('/ticket/{ticket_id}', handle_ticket_page_by_id),
        web.get('/ticket.css', handle_ticket_css),
        web.get('/ticket.js', handle_ticket_js),
        web.get('/modules.html', handle_modules_page),
        
        # ============================================================================
        # Public Queue (Stage 10.2) — без авторизации
        # ============================================================================
        web.get('/public_api/queues', handle_public_queues),
        web.get('/public_api/queue/tickets', handle_public_queue_tickets),
        web.get('/public_api/queue/stats', handle_public_queue_stats),
        web.get('/public_api/ticket_forms/current', handle_ticket_form_pack_current),
        web.post('/public_api/tickets/create', handle_public_ticket_create),
        web.post('/public_api/tickets/{ticket_id}/authorize', handle_public_ticket_authorize),
        
        # ============================================================================
        # Health (для smoke-тестов и мониторинга)
        # ============================================================================
        web.get('/api/health', handle_health),

        # ============================================================================
        # Authentication API
        # ============================================================================
        web.post('/api/login', handle_login),
        web.post('/api/ui_login', handle_ui_login),  # UI user login
        web.get('/api/ui_session', handle_ui_session),
        web.post('/api/web/session/login', handle_web_session_login),
        web.post('/api/web/session/logout', handle_web_session_logout),
        web.get('/api/web/session/me', handle_web_session_me),
        web.get('/api/web/support/bootstrap', handle_web_support_bootstrap),
        web.get('/api/web/support/workspace/summary', handle_web_support_workspace_summary),
        web.get('/api/web/support/queue', handle_web_support_queue),
        web.get('/api/web/support/tickets/{ticket_id}/workspace', handle_web_support_ticket_workspace),
        web.get('/api/web/support/tickets/{ticket_id}', handle_web_support_ticket_detail),
        web.get('/api/web/support/tickets/{ticket_id}/passport', handle_web_support_ticket_passport),
        web.post('/api/web/support/tickets/{ticket_id}/passport/generate', handle_web_support_ticket_passport_generate),
        web.patch('/api/web/support/tickets/{ticket_id}/passport', handle_web_support_ticket_passport_patch),
        web.get('/api/web/support/tickets/{ticket_id}/passport/evidence-candidates', handle_web_support_ticket_passport_evidence_candidates),
        web.post('/api/web/support/tickets/{ticket_id}/passport/evidence/link', handle_web_support_ticket_passport_evidence_link),
        web.patch('/api/web/support/tickets/{ticket_id}/passport/evidence/{evidence_id}', handle_web_support_ticket_passport_evidence_update),
        web.post('/api/web/support/tickets/{ticket_id}/passport/evidence', handle_web_support_ticket_passport_evidence),
        web.post('/api/web/support/tickets/{ticket_id}/passport/knowledge-draft', handle_web_support_ticket_passport_knowledge_draft),
        web.get('/api/web/support/tickets/{ticket_id}/tools', handle_web_support_ticket_tools),
        web.get('/api/web/support/tickets/{ticket_id}/playbooks', handle_web_support_ticket_playbooks),
        web.post('/api/web/support/tickets/{ticket_id}/messages', handle_web_support_send_message),
        web.post('/api/web/support/tickets/{ticket_id}/status', handle_web_support_change_status),
        web.post('/api/web/support/tickets/{ticket_id}/assign', handle_web_support_assign_ticket),
        web.post('/api/web/support/tickets/{ticket_id}/queue', handle_web_support_change_queue),
        web.post('/api/web/support/tickets/{ticket_id}/priority', handle_web_support_change_priority),
        web.post('/api/web/support/tickets/{ticket_id}/reroute', handle_web_support_reroute_ticket),
        web.post('/api/web/support/tickets/{ticket_id}/approvals/{approval_id}/decision', handle_web_support_approval_decision),
        web.post('/api/web/support/tickets/{ticket_id}/tools/run', handle_web_support_run_tool),
        web.post('/api/web/support/tickets/{ticket_id}/playbooks/run', handle_web_support_run_playbook),
        web.get('/api/web/admin/bootstrap', handle_web_admin_bootstrap),
        web.get('/api/web/admin/access/catalog', handle_web_admin_access_catalog),
        web.get('/api/web/admin/access/summary', handle_web_admin_access_summary),
        web.get('/api/web/admin/access/effective', handle_web_admin_access_effective),
        web.get('/api/web/admin/access/audit', handle_web_admin_access_audit),
        web.post('/api/web/admin/access/groups', handle_web_admin_access_create_group),
        web.patch('/api/web/admin/access/groups/{group_id}', handle_web_admin_access_update_group),
        web.put('/api/web/admin/access/groups/{group_id}/permissions', handle_web_admin_access_group_permissions),
        web.put('/api/web/admin/access/groups/{group_id}/members', handle_web_admin_access_group_members),
        web.put('/api/web/admin/access/groups/{group_id}/queues', handle_web_admin_access_group_queues),
        web.get('/api/web/admin/observer/quick', handle_web_admin_observer_quick),
        web.get('/api/web/admin/observer/traces', handle_web_admin_observer_traces),
        web.get('/api/web/admin/observer/trace-detail/{trace_id}', handle_tech_trace_detail),
        web.get('/api/web/admin/observer/traces/{trace_id}', handle_web_admin_observer_trace_detail),
        web.get('/api/web/admin/observer/diagnostics/bundle', handle_tech_diagnostics_bundle),
        web.get('/api/web/admin/observer/runtime', handle_tech_traces_runtime),
        web.get('/api/web/admin/observer/settings', handle_observer_settings_get),
        web.patch('/api/web/admin/observer/settings', handle_observer_settings_patch),
        web.get('/api/web/admin/observer/signatures', handle_tech_signatures_search),
        web.get('/api/web/admin/observer/signatures/{error_signature}', handle_tech_signature_detail),
        web.get('/api/web/admin/observer/degradations', handle_tech_degradations_search),
        web.post('/api/web/admin/observer/traces/rebuild', handle_tech_traces_rebuild),
        web.get('/api/web/admin/tech/alerts', handle_tech_alerts),
        web.get('/api/web/admin/devices', handle_web_admin_devices),
        web.post('/api/web/admin/devices/cleanup_env_duplicates', handle_web_admin_devices_cleanup_env_duplicates),
        web.get('/api/web/admin/devices/{device_id}/tokens', handle_web_admin_device_tokens),
        web.post('/api/web/admin/devices/{device_id}/tokens/revoke', handle_web_admin_device_token_revoke),
        web.get('/api/web/admin/connection_policy', handle_admin_connection_policy_get),
        web.patch('/api/web/admin/connection_policy', handle_admin_connection_policy_patch),
        web.get('/api/web/admin/connection_requests', handle_admin_connection_requests_list),
        web.post('/api/web/admin/connection_requests/{device_id}/approve', handle_admin_connection_request_approve),
        web.post('/api/web/admin/connection_requests/{device_id}/reject', handle_admin_connection_request_reject),
        web.get('/api/web/admin/registry', handle_web_admin_registry),
        web.get('/api/web/admin/forms/current', handle_web_admin_forms_current),
        web.post('/api/web/admin/forms/route-preview', handle_web_admin_forms_route_preview),
        web.post('/api/web/admin/forms/save', handle_web_admin_forms_save),
          web.get('/api/web/admin/helpdesk-model/policies', handle_web_admin_helpdesk_model_policies),
          web.post('/api/web/admin/helpdesk-model/policies/publish', handle_web_admin_helpdesk_model_publish_policy),
          web.post('/api/web/admin/helpdesk-model/policies/diff', handle_web_admin_helpdesk_model_policy_diff),
          web.post('/api/web/admin/helpdesk-model/policies/deactivate', handle_web_admin_helpdesk_model_policy_deactivate),
          web.post('/api/web/admin/helpdesk-model/policies/rollback', handle_web_admin_helpdesk_model_policy_rollback),
          web.post('/api/web/admin/helpdesk-model/ticket-types/publish', handle_web_admin_helpdesk_model_publish_ticket_type),
          web.post('/api/web/admin/helpdesk-model/ticket-types/deactivate', handle_web_admin_helpdesk_model_ticket_type_deactivate),
          web.post('/api/web/admin/helpdesk-model/ticket-types/rollback', handle_web_admin_helpdesk_model_ticket_type_rollback),
          web.post('/api/web/admin/helpdesk-model/form-schemas/publish', handle_web_admin_helpdesk_model_publish_form_schema),
          web.post('/api/web/admin/helpdesk-model/smart-views/publish', handle_web_admin_helpdesk_model_publish_smart_view),
        web.post('/api/web/admin/helpdesk-model/request-templates/publish-from-form', handle_web_admin_helpdesk_model_publish_from_form),
        web.post('/api/web/admin/helpdesk-model/request-templates/republish-legacy-forms', handle_web_admin_helpdesk_model_republish_legacy_forms),
        web.get('/api/web/admin/playbooks/catalog', handle_web_admin_playbooks_catalog),
        web.post('/api/web/admin/playbooks/save', handle_web_admin_playbooks_save),
        web.get('/api/web/admin/modules', handle_web_admin_modules),
        web.patch('/api/web/admin/modules/rollout_settings', handle_web_admin_patch_modules_rollout_settings),
        web.patch('/api/web/admin/modules/{module_name}/preferred', handle_web_admin_set_module_preferred_version),
        web.get('/api/web/admin/modules/workbench', handle_list_modules_workbench),
        web.get('/api/web/admin/modules/workbench/{module_name}/{version}', handle_get_module_workbench_detail),
        web.post('/api/web/admin/modules/workbench/authoring/validate', handle_validate_module_authoring),
        web.post('/api/web/admin/modules/workbench/authoring/publish', handle_publish_module_authoring),
        web.post('/api/web/admin/modules/workbench/upload', handle_upload_module),
        web.get('/api/web/admin/modules/workbench/{module_name}/{version}/live_test_candidates', handle_list_module_live_test_candidates),
        web.post('/api/web/admin/modules/workbench/{module_name}/{version}/live_tests', handle_run_module_live_test),
        web.delete('/api/web/admin/modules/workbench/{module_name}/{version}', handle_delete_module),
        web.get('/api/web/admin/devices/{device_id}/updates', handle_web_admin_device_updates),
        web.post('/api/web/admin/devices/{device_id}/updates/run', handle_web_admin_device_update_run),
        web.get('/api/registry/options', handle_registry_options),
        web.post('/api/registry/profile', handle_registry_profile_upsert),
        web.get('/api/web/reports/summary', handle_web_reports_summary),
        web.get('/api/web/settings', handle_web_settings_payload),
        web.put('/api/web/settings/workflow_profiles', handle_web_settings_workflow_profiles_put),
        web.get('/api/web/notifications', handle_notifications_list),
        web.get('/api/web/notifications/unread_count', handle_notifications_unread_count),
        web.post('/api/web/notifications/read_all', handle_notifications_read_all),
        web.get('/api/web/notifications/preferences', handle_notification_preferences_get),
        web.post('/api/web/notifications/preferences', handle_notification_preferences_post),
        web.post('/api/web/notifications/{id}/read', handle_notification_mark_read),
        web.get('/api/web/settings/queues', handle_admin_queues_list),
        web.post('/api/web/settings/queues', handle_admin_queues_post),
        web.get('/api/web/settings/queues/{queue_id}', handle_admin_queues_get),
        web.patch('/api/web/settings/queues/{queue_id}', handle_admin_queues_patch),
        web.get('/api/web/settings/queues/{queue_id}/members', handle_admin_queue_members_list),
        web.put('/api/web/settings/queues/{queue_id}/members/{actor_id}', handle_admin_queue_members_put),
        web.delete('/api/web/settings/queues/{queue_id}/members/{actor_id}', handle_admin_queue_members_delete),
        web.get('/api/web/settings/queues/{queue_id}/ola_targets', handle_admin_ola_targets_get),
        web.put('/api/web/settings/queues/{queue_id}/ola_targets', handle_admin_ola_targets_put),
        web.get('/api/web/settings/routing_rules', handle_admin_routing_rules_list),
        web.post('/api/web/settings/routing_rules', handle_admin_routing_rules_post),
        web.patch('/api/web/settings/routing_rules/{rule_id}', handle_admin_routing_rules_patch),
        web.get('/api/web/settings/sla_policies', handle_admin_sla_policies_list),
        web.post('/api/web/settings/sla_policies', handle_admin_sla_policies_post),
        web.patch('/api/web/settings/sla_policies/{policy_id}', handle_admin_sla_policies_patch),
        web.post('/api/web/settings/sla_policies/{policy_id}/set_default', handle_admin_sla_policies_set_default),
        web.get('/api/web/settings/sla_policies/{policy_id}/targets', handle_admin_sla_targets_get),
        web.put('/api/web/settings/sla_policies/{policy_id}/targets', handle_admin_sla_targets_put),
        web.get('/api/web/settings/sla_policies/{policy_id}/priority_matrix', handle_admin_priority_matrix_get),
        web.put('/api/web/settings/sla_policies/{policy_id}/priority_matrix', handle_admin_priority_matrix_put),
        web.get('/api/web/settings/calendars', handle_admin_calendars_list),
        web.post('/api/web/settings/calendars', handle_admin_calendars_post),
        web.patch('/api/web/settings/calendars/{calendar_id}', handle_admin_calendars_patch),
        web.get('/api/web/settings/resolution_codes', handle_admin_resolution_codes_list),
        web.post('/api/web/settings/resolution_codes', handle_admin_resolution_codes_post),
        web.patch('/api/web/settings/resolution_codes/{code}', handle_admin_resolution_codes_patch),
        web.delete('/api/web/settings/resolution_codes/{code}', handle_admin_resolution_codes_delete),
        web.get('/api/web/settings/audit', handle_admin_audit_list),
        web.get('/api/web/realtime/bootstrap', handle_web_realtime_bootstrap),
        web.post('/api/users/me/password', handle_users_me_password_post),  # Stage 10: self-service password
        # Connection request flow (no auth: agent requests token)
        web.post('/api/connection_request', handle_connection_request),
        web.get('/api/connection_request/status', handle_connection_request_status),

        # ============================================================================
        # Agents API
        # ============================================================================
        web.get('/api/agents', handle_get_agents),
        web.get('/api/pending_connections', handle_get_pending_connections),
        web.get('/api/devices', handle_get_devices),
        web.get('/api/list_devices', handle_get_devices),  # Alias for compatibility
        web.get('/api/devices/{device_id}', handle_get_device),  # Single device (agent page)
        web.get('/api/devices/{device_id}/agent/update_diagnostics', handle_get_device_update_diagnostics),
        web.get('/api/devices/{device_id}/agent/update_recommendation', handle_get_device_update_recommendation),
        web.post('/api/devices/{device_id}/check', handle_device_check),  # Force check (list_tools)
        web.delete('/api/devices/{device_id}', handle_delete_device),  # Delete device from DB
        web.get('/api/devices/{device_id}/tokens', handle_get_device_tokens),  # Get device tokens
        web.post('/api/devices/{device_id}/tokens/revoke', handle_revoke_device_token),  # Revoke device token

        # ============================================================================
        # Agent Builds (Remote Self-Update)
        # ============================================================================
        web.post('/api/agent_builds/upload', handle_upload_agent_build),
        web.get('/api/agent_builds', handle_list_agent_builds),
        web.delete('/api/agent_builds/{target}/{channel}/{version}', handle_delete_agent_build),
        web.get('/api/agent_builds/{target}/{channel}/{version}/download', handle_download_agent_build),
        web.get('/api/agent_updates/rollout_policy', handle_get_agent_rollout_policy),
        web.patch('/api/agent_updates/rollout_policy', handle_patch_agent_rollout_policy),
        web.post('/api/devices/{device_id}/agent/update', handle_update_device_agent),
        web.post('/api/agents/update_bulk', handle_bulk_update_agents),

        # ============================================================================
        # Tickets API (static paths before {ticket_id} to avoid "resolution_codes" as ticket_id)
        # ============================================================================
        web.post('/api/tickets/create/preview', handle_tickets_create_preview),
        web.post('/api/tickets/create', handle_tickets_create),
        web.get('/api/tickets', handle_tickets_list),
        web.get('/api/ticket_forms/current', handle_ticket_form_pack_current),
        web.get('/api/ticket_forms/packs', handle_ticket_form_packs_list),
        web.get('/api/ticket_forms/packs/{pack_key}/{version}', handle_ticket_form_pack_detail),
        web.post('/api/ticket_forms/packs/save', handle_ticket_form_pack_save),
        web.patch('/api/ticket_forms/packs/{pack_key}/{version}/preferred', handle_ticket_form_pack_set_preferred),
        web.get('/api/tickets/resolution_codes', handle_ticket_resolution_codes_list),
        web.get('/api/tickets/metrics/backlog', handle_ticket_metrics_backlog),
        web.get('/api/tickets/metrics/aging', handle_ticket_metrics_aging),
        web.get('/api/tickets/metrics/sla', handle_ticket_metrics_sla),
        web.get('/api/tickets/metrics/reopen_rate', handle_ticket_metrics_reopen_rate),
        web.get('/api/tickets/metrics/top', handle_ticket_metrics_top),
        web.get('/api/tickets/metrics/status_age', handle_ticket_metrics_status_age),
        web.post('/api/tickets/queues/{queue_id}/order/reset', handle_ticket_queue_order_reset),
        web.post('/api/tickets/archive', handle_tickets_archive),
        web.post('/api/tickets/bulk_assign', handle_tickets_bulk_assign),
        web.get('/api/tickets/{ticket_id}', handle_ticket_get),
        web.get('/api/tickets/{ticket_id}/snapshot', handle_ticket_get_snapshot),  # New snapshot endpoint
        web.get('/api/tickets/{ticket_id}/observer', handle_ticket_get_observer_summary),
        web.post('/api/tickets/{ticket_id}/message', handle_ticket_send_message),
        web.post('/api/tickets/{ticket_id}/close', handle_ticket_close),
        web.post('/api/tickets/{ticket_id}/status', handle_ticket_status),
        web.post('/api/tickets/{ticket_id}/reroute', handle_ticket_reroute),
        web.post('/api/tickets/{ticket_id}/classify', handle_ticket_classify),
        web.post('/api/tickets/{ticket_id}/queue', handle_ticket_queue),
        web.post('/api/tickets/{ticket_id}/priority', handle_ticket_priority),
        web.post('/api/tickets/{ticket_id}/order', handle_ticket_order),
        web.post('/api/tickets/{ticket_id}/assign', handle_ticket_assign),
        web.post('/api/tickets/{ticket_id}/device', handle_ticket_bind_device),
        web.post('/api/tickets/{ticket_id}/read', handle_ticket_mark_read),
        web.post('/api/tickets/{ticket_id}/requester_profile', handle_ticket_requester_profile),
        web.get('/api/tickets/{ticket_id}/sla', handle_ticket_sla_get),
        web.post('/api/tickets/{ticket_id}/worklogs', handle_ticket_worklogs_post),
        web.get('/api/tickets/{ticket_id}/worklogs', handle_ticket_worklogs_list),
        web.get('/api/tickets/{ticket_id}/worklog_total', handle_ticket_worklog_total),
        web.get('/api/tickets/{ticket_id}/problems', handle_ticket_problems_get),
        web.post('/api/tickets/{ticket_id}/change_links', handle_ticket_change_links_post),
        web.get('/api/tickets/{ticket_id}/change_links', handle_ticket_change_links_list),
        web.delete('/api/tickets/{ticket_id}/change_links/{id}', handle_ticket_change_links_delete),
        # Stage 5: Relations, Watchers, KB, Metrics
        web.post('/api/tickets/{ticket_id}/links', handle_ticket_links_post),
        web.get('/api/tickets/{ticket_id}/links', handle_ticket_links_list),
        web.delete('/api/tickets/{ticket_id}/links/{link_id}', handle_ticket_links_delete),
        web.post('/api/tickets/{ticket_id}/parent', handle_ticket_parent_post),
        web.delete('/api/tickets/{ticket_id}/parent', handle_ticket_parent_delete),
        web.post('/api/tickets/{ticket_id}/watchers', handle_ticket_watchers_post),
        web.get('/api/tickets/{ticket_id}/watchers', handle_ticket_watchers_list),
        web.delete('/api/tickets/{ticket_id}/watchers/{actor_id}', handle_ticket_watchers_delete),
        web.post('/api/tickets/{ticket_id}/kb_links', handle_ticket_kb_links_post),
        web.get('/api/tickets/{ticket_id}/kb_links', handle_ticket_kb_links_list),
        web.delete('/api/tickets/{ticket_id}/kb_links/{kb_link_id}', handle_ticket_kb_links_delete),
        
        # Phase D: Event Replay Endpoints
        web.get('/api/tickets/{ticket_id}/events', handle_get_ticket_events),
        web.get('/api/tickets/{ticket_id}/messages', handle_ticket_messages),  # Shortcut for chat messages
        # Stage 6: Notifications (static paths before {id})
        web.get('/api/notifications', handle_notifications_list),
        web.get('/api/notifications/unread_count', handle_notifications_unread_count),
        web.post('/api/notifications/read_all', handle_notifications_read_all),
        web.get('/api/notifications/preferences', handle_notification_preferences_get),
        web.post('/api/notifications/preferences', handle_notification_preferences_post),
        web.post('/api/notifications/{id}/read', handle_notification_mark_read),
        # Stage 7: Problems API (support/admin)
        web.post('/api/problems', handle_problems_create),
        web.get('/api/problems', handle_problems_list),
        web.get('/api/problems/{problem_id}', handle_problem_get),
        web.post('/api/problems/{problem_id}/status', handle_problem_status_post),
        web.post('/api/problems/{problem_id}/tickets', handle_problem_tickets_post),
        web.delete('/api/problems/{problem_id}/tickets/{ticket_id}', handle_problem_tickets_delete),
        web.get('/api/devices/{device_id}/events', handle_get_device_events),
        
        # ============================================================================
        # Operations API
        # ============================================================================
        web.get('/api/operations', handle_get_operations),
        web.get('/api/operations/{operation_id}', handle_get_operation),
        web.post('/api/operations/{operation_id}/cancel', handle_cancel_operation),
        web.post('/api/operations/{operation_id}/approve', handle_approve_consent),
        web.post('/api/operations/{operation_id}/deny', handle_deny_consent),
        
        # ============================================================================
        # Tools API
        # ============================================================================
        web.get('/api/tools', handle_get_tools),
        web.post('/api/tools/run', handle_tools_run),
        
        # ============================================================================
        # Admin API
        # ============================================================================
        web.post('/api/admin/run_tool', handle_admin_run_tool),
        # Stage 10: Admin Users API (feature-flagged: AUTH_UI_DB_USERS_ENABLED)
        web.get('/api/admin/users', handle_admin_users_list),
        web.post('/api/admin/users', handle_admin_users_post),
        web.get('/api/admin/users/{user_login}', handle_admin_users_get),
        web.patch('/api/admin/users/{user_login}', handle_admin_users_patch),
        web.post('/api/admin/users/{user_login}/password', handle_admin_users_password_post),
        web.post('/api/admin/users/{user_login}/deactivate', handle_admin_users_deactivate_post),
        # Connection request policy and pending requests (admin)
        web.get('/api/admin/connection_policy', handle_admin_connection_policy_get),
        web.patch('/api/admin/connection_policy', handle_admin_connection_policy_patch),
        web.get('/api/admin/connection_requests', handle_admin_connection_requests_list),
        web.post('/api/admin/connection_requests/{device_id}/approve', handle_admin_connection_request_approve),
        web.post('/api/admin/connection_requests/{device_id}/reject', handle_admin_connection_request_reject),
        # Stage 9: Admin Config API (feature-flagged)
        web.get('/api/admin/tickets/queues', handle_admin_queues_list),
        web.post('/api/admin/tickets/queues', handle_admin_queues_post),
        web.get('/api/admin/tickets/queues/{queue_id}', handle_admin_queues_get),
        web.patch('/api/admin/tickets/queues/{queue_id}', handle_admin_queues_patch),
        web.get('/api/admin/tickets/queues/{queue_id}/members', handle_admin_queue_members_list),
        web.put('/api/admin/tickets/queues/{queue_id}/members/{actor_id}', handle_admin_queue_members_put),
        web.delete('/api/admin/tickets/queues/{queue_id}/members/{actor_id}', handle_admin_queue_members_delete),
        web.get('/api/admin/tickets/resolution_codes', handle_admin_resolution_codes_list),
        web.post('/api/admin/tickets/resolution_codes', handle_admin_resolution_codes_post),
        web.patch('/api/admin/tickets/resolution_codes/{code}', handle_admin_resolution_codes_patch),
        web.delete('/api/admin/tickets/resolution_codes/{code}', handle_admin_resolution_codes_delete),
        web.get('/api/admin/tickets/routing_rules', handle_admin_routing_rules_list),
        web.post('/api/admin/tickets/routing_rules', handle_admin_routing_rules_post),
        web.patch('/api/admin/tickets/routing_rules/{rule_id}', handle_admin_routing_rules_patch),
        web.get('/api/admin/tickets/sla_policies', handle_admin_sla_policies_list),
        web.post('/api/admin/tickets/sla_policies', handle_admin_sla_policies_post),
        web.patch('/api/admin/tickets/sla_policies/{policy_id}', handle_admin_sla_policies_patch),
        web.post('/api/admin/tickets/sla_policies/{policy_id}/set_default', handle_admin_sla_policies_set_default),
        web.get('/api/admin/tickets/sla_policies/{policy_id}/targets', handle_admin_sla_targets_get),
        web.put('/api/admin/tickets/sla_policies/{policy_id}/targets', handle_admin_sla_targets_put),
        web.get('/api/admin/tickets/sla_policies/{policy_id}/priority_matrix', handle_admin_priority_matrix_get),
        web.put('/api/admin/tickets/sla_policies/{policy_id}/priority_matrix', handle_admin_priority_matrix_put),
        web.get('/api/admin/tickets/calendars', handle_admin_calendars_list),
        web.post('/api/admin/tickets/calendars', handle_admin_calendars_post),
        web.patch('/api/admin/tickets/calendars/{calendar_id}', handle_admin_calendars_patch),
        web.get('/api/admin/tickets/queues/{queue_id}/ola_targets', handle_admin_ola_targets_get),
        web.put('/api/admin/tickets/queues/{queue_id}/ola_targets', handle_admin_ola_targets_put),
        web.get('/api/admin/tickets/audit', handle_admin_audit_list),
        # Tech observability panel (read-only)
        web.get('/api/admin/tech/overview', handle_tech_overview),
        web.get('/api/admin/tech/alerts', handle_tech_alerts),
        web.get('/api/admin/tech/logs', handle_tech_logs),
        web.post('/api/admin/tech/dismiss', handle_tech_dismiss_item),
        web.get('/api/admin/tech/agents/audit', handle_tech_agents_audit),
        web.get('/api/admin/tech/agents/{device_id}/timeline', handle_tech_agent_timeline),
        web.post('/api/admin/tech/agents/{device_id}/actions', handle_tech_agent_action),
        web.get('/api/admin/tech/tickets/{ticket_id}/lifecycle', handle_tech_ticket_lifecycle),
        web.get('/api/admin/tech/users/audit', handle_tech_users_audit),
        web.get('/api/admin/tech/admin-config/audit', handle_tech_admin_config_audit),
        web.get('/api/admin/tech/operations/stuck', handle_tech_operations_stuck),
        web.get('/api/admin/tech/observer/quick', handle_tech_observer_quick),
        web.get('/api/admin/tech/observer/search', handle_tech_observer_search),
        web.get('/api/admin/tech/diagnostics/bundle', handle_tech_diagnostics_bundle),
        web.get('/api/admin/settings/observer', handle_observer_settings_get),
        web.patch('/api/admin/settings/observer', handle_observer_settings_patch),
        web.get('/api/admin/tech/traces/runtime', handle_tech_traces_runtime),
        web.get('/api/admin/tech/traces', handle_tech_traces_search),
        web.post('/api/admin/tech/traces/rebuild', handle_tech_traces_rebuild),
        web.get('/api/admin/tech/traces/{trace_id}', handle_tech_trace_detail),
        web.get('/api/admin/tech/degradations', handle_tech_degradations_search),
        web.get('/api/admin/tech/signatures', handle_tech_signatures_search),
        web.get('/api/admin/tech/signatures/{error_signature}', handle_tech_signature_detail),
        
        # ============================================================================
        # Uploads API
        # ============================================================================
        web.post('/api/upload', handle_upload),
        web.get('/api/artifacts/{artifact_id}/download', handle_artifact_download),
        
        # ============================================================================
        # Protocol Documentation
        # ============================================================================
        web.get('/api/protocol', handle_protocol),
        
        # ============================================================================
        # Commands API
        # ============================================================================
        web.post('/api/send_command', handle_send_command),
        web.post('/api/check_functions', handle_check_functions),
        web.post('/api/smoke_run', handle_smoke_run),
        
        # ============================================================================
        # Chat API
        # ============================================================================
        web.post('/api/chat_start', handle_chat_start),
        web.post('/api/chat_raise', handle_chat_raise),
        web.post('/api/chat_send', handle_chat_send),
        web.get('/api/active_chats', handle_active_chats),
        web.get('/api/chat_events', handle_chat_events),
        
        # ============================================================================
        # Modules API
        # ============================================================================
        # New HTTP download endpoints
        web.get('/api/modules/ping', handle_modules_ping),
        web.post('/api/modules/upload', handle_upload_module),
        web.post('/api/modules/create', handle_create_module),
        web.get('/api/modules/authoring/catalog', handle_get_module_authoring_catalog),
        web.post('/api/modules/authoring/validate', handle_validate_module_authoring),
        web.post('/api/modules/authoring/publish', handle_publish_module_authoring),
        web.post('/api/modules/workbench/validate', handle_validate_module_workbench),
        web.post('/api/modules/workbench/save', handle_save_module_workbench),
        web.post('/api/modules/cleanup_missing', handle_cleanup_missing_modules),
        web.post('/api/modules/bulk_install', handle_bulk_install_modules),
        web.get('/api/modules/rollout_settings', handle_get_module_rollout_settings),
        web.patch('/api/modules/rollout_settings', handle_patch_module_rollout_settings),
        web.get('/api/modules/workbench', handle_list_modules_workbench),
        web.get('/api/modules/workbench/{module_name}/{version}', handle_get_module_workbench_detail),
        web.get('/api/modules/{module_name}/{version}/live_test_candidates', handle_list_module_live_test_candidates),
        web.post('/api/modules/{module_name}/{version}/live_tests', handle_run_module_live_test),
        web.get('/api/modules/{module_name}/{version}', handle_get_module_detail),
        web.get('/api/modules/{module_name}/{version}/download', handle_download_module),
        web.delete('/api/modules/{module_name}/{version}', handle_delete_module),
        web.get('/api/modules', handle_list_modules),
        web.patch('/api/modules/{module_name}/preferred', handle_set_module_preferred_version),
        web.get('/api/devices/{device_id}/modules', handle_get_device_modules),
        web.get('/api/devices/{device_id}/toolset', handle_get_device_toolset),
        web.post('/api/devices/{device_id}/modules/install', handle_install_module),
        web.post('/api/devices/{device_id}/modules/activate', handle_activate_module_new),
        web.post('/api/devices/{device_id}/modules/deactivate', handle_deactivate_module_new),
        web.post('/api/devices/{device_id}/modules/sync', handle_sync_modules),
        web.post('/api/devices/{device_id}/modules/remove_version', handle_remove_module_version),
        web.post('/api/devices/{device_id}/modules/remove', handle_remove_module),
        web.post('/api/devices/{device_id}/modules/verify', handle_verify_module),
        web.get('/api/devices/{device_id}/modules/debug', handle_debug_modules),
        web.get('/api/devices/{device_id}/modules/desired_diff', handle_get_desired_diff),
        web.post('/api/devices/{device_id}/modules/reconcile', handle_trigger_reconcile),
        
        # Compatibility endpoints for older clients (planned for removal after migration window)
        web.post('/api/install_module_package', handle_install_module_package),
        web.post('/api/list_installed_modules', handle_list_installed_modules),
        web.post('/api/activate_module', handle_activate_module),
        web.post('/api/rollback_module', handle_rollback_module),
        web.post('/api/deactivate_module', handle_deactivate_module),
        web.post('/api/smoke_install_and_run', handle_smoke_install_and_run),
        
        # ============================================================================
        # Playbook API (Этап 4 MVP)
        # ============================================================================
        web.post('/api/playbooks/runs', handle_start_playbook_run),
        
        # ============================================================================
        # Jobs API
        # ============================================================================
        web.get('/api/job_events', handle_get_job_events),
        web.post('/api/start_job', handle_start_job),
        
        # ============================================================================
        # Additional HTML Pages
        # ============================================================================
        web.get('/chat_debug', handle_chat_debug),
        web.get('/chat_ws', handle_chat_ws),
        web.get('/test_simple', handle_test_simple),
        web.get('/ws_ui_test', handle_ws_ui_test),
    ])
