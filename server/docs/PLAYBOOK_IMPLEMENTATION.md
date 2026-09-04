# Playbook implementation boundary

Helpdesk playbooks coordinate ticket workflow and safe evidence. Endpoint
Platform owns endpoint-side collection, execution, module lifecycle and result
delivery. Helpdesk does not enqueue device commands or maintain agent runtime
state.

Any ticket-facing operation must use the Endpoint operation contract and remain
safe to retry without creating duplicate evidence.
