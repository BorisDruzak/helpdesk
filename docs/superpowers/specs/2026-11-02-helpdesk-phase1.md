# Helpdesk first-stage fixes

Authority: the user's numbered response to the 2026-11-02 UX audit and request
to implement and rerun Other/Studio scenarios. Prior audit recommendations are
superseded where the user corrected them.

- Keep registration and existing profiles/roles; inspect and fix registration
  defects without opening self-registration or automatically binding identities.
- Keep password-only AD login for every Helpdesk role. Existing linked profiles
  must survive login unchanged. Unlinked/failed SSO needs a usable Russian error.
- Complete necessary Studio coverage; preserve questions, answer conditions and
  SLA calculation. Test meaningful branches, not merely schema validation.
- Remove the manual processing-preview action. At submission show processing
  automatically, submit once, and open the resulting requester ticket directly.
- Make the existing compact support queue the normal staff entry. Keep advanced
  operations reachable. Show the problem and actual resolution without digging.
- Remove manual resolution-code entry. Ordinary first-stage policies require a
  public result, not a code or mandatory requester confirmation.
  Old ticket snapshots requiring a code must not become impossible to complete:
  a missing code is retired as a closure prerequisite; retain optional existing
  code metadata and every other approval/evidence/visibility/authority guard.
- Support must resolve and close ordinary work directly. Preserve atomicity,
  ticket visibility, ownership, role, audit and explicit special-policy guards.
  Fix requester action projection/command mismatch; never authorize by UI alone.
- Preserve question/SLA semantics and scenario version/session consistency.
- Registration testing must include the existing enabled/disabled policy,
  duplicate/invalid inputs, correct normal-user authority and profile preservation.
- Verify source, focused PostgreSQL/API tests, UI unit/build, browser scenarios
  (Other and Studio including conditions), and exact deployed staging behavior.
- Use only approved staging for live changes; leave it running (explicit user
  request). Preserve production, AD records, existing roles and credentials.
  Subsequent explicit user replies authorize a separate staging `admin-2`
  profile with Helpdesk administrator role and an exact confirmed AD binding;
  no previous account/profile existed. Keep other accounts unchanged. Owned
  synthetic requester fixtures may be created for acceptance without enabling
  self-registration or changing an existing account's password.

Actors and composition: requester wizard (questions -> submission -> ticket chat),
support list/detail (queue -> take -> reply -> resolution), admin existing Studio
workbench for publication. No redesign or parallel workflow engine.

Baseline: 9a79f6cfba8cfe37649a62e0077a82ff8637ac9f, existing codex/ui-support-001
checkout. Preserve unrelated dirty PLANS/history and local evidence.
