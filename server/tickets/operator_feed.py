"""Event types carried by the operator's cursor-based ticket feed."""

OPERATOR_FEED_EVENT_TYPES = frozenset({
    "chat_message",
    "status_changed",
    "assignee_changed",
    "queue_changed",
    "priority_changed",
    "classification_changed",
    "requester_profile_changed",
    "device_changed",
    "diagnostic_device_selected",
})
