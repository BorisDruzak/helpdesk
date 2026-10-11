# Ticket and requester workspaces

`/app/tickets` and `/app/tickets/:ticketId` use the shared application sidebar
and header, with a light workspace by default. An explicitly saved dark theme
remains supported. Column layout measures the space inside the shell rather
than the entire browser width; the inspector becomes a drawer when necessary.

`/app/requester/tickets` contains the searchable/filterable list only.
`/app/requester/tickets/:ticketId` opens a separate chat with a fixed reply
composer. Description and history are a secondary view; consent, confirmation,
feedback and reopening retain server-supplied permissions. Changing the ticket
resets the reply draft. Polling retains the existing visible-tab policy.

The support SLA/OLA projection distinguishes a completed timer from a missing
deadline: `status=completed`, `completed_at` and
`completed_within_target`. Completed timers have no active remaining countdown.
Late completion remains visibly different from completion within the target.
A paused countdown uses the pause time, so waiting does not consume remaining
time. Resolution stops for resolved/closed tickets with the canonical
`resolution_at` timestamp (or legacy `resolved_at`). Recorded breaches persist
after completion, even if later pauses extend the current deadline.

Support contacts come from an actor-scoped `RegistryPort.requester_profile`
read after requester identity validation. The bounded profile projection adds
optional `email` and `phone` fields; department/location labels retain their
existing fields. Contacts are displayed only when requester references match.
The minimal immutable `RequesterSnapshot` and ticket-history persistence do not
gain profile data. Unavailable Registry reads do not fall back to a device owner
or expose contacts from stale history.

`/app/admin/quality` uses Russian interface text, translated review/action
states, priorities and types, Russian date formatting and “Нет данных” for
missing metrics. Service/offering codes remain identifiers; API enum values
and permissions are unchanged.
