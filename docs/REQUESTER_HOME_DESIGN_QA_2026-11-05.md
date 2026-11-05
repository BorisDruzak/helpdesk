# Requester home design QA — 2026-11-05

Selected reference: first **displayed** image, `exec-24f0abcb-c0da-48c0-9eb6-0ff722a13726.png`.
Compare the white-sidebar concept, not the second horizontal-navigation concept.

## Findings and fixes

- Initial comparison found P2 density/typography drift: sidebar 232px and undersized
  action/list type made the implementation denser than the reference. Increased
  sidebar to 280px, desktop heading/action/body sizes and spacing; recaptured.
- Final combined evidence: `tmp/requester-home-20261105/comparison-final.png` puts
  the reference beside the implementation at the reference's nominal 1488x1058
  viewport. Reference raster is 1487px wide. Full-page implementation is 1072px
  tall because the user additionally required device readiness. This is natural
  vertical page scrolling, not clipping or a second internal scroll area.
- White navigation, paired create/list actions, flat recent-ticket rows and
  compact profile completion match the selected hierarchy. Device readiness is an
  intentional addition. Real staff sessions retain workspace switching, notifications
  and logout; real ticket codes/dates use canonical existing projections.
- Remaining P3: existing product font/icons and absolute date formatter differ
  from the generated raster; these preserve the established product components.
  No P0/P1/P2 visual issue remains in the compared view.

## Browser coverage

Screenshots cover 1366x768, 1440x900, 1488x1058, 1920x1080 and 390x844.
Create is visible without scrolling; body has no horizontal overflow. Ready,
incomplete profile, missing device, empty tickets, read failure/retry, Linux tab,
keyboard tab switching and Windows image decode are checked. Unit cases also cover
offline/ambiguous/pending device states and explicit consent decisions.

The Linux guide is intentionally support-assisted: current agent has no Linux
tray code UI. The link uses the canonical `device_owner_change` intent; the browser
follows it to the explicit no-device owner-check form. This is not acceptance of a
native Linux agent self-service code flow.

The pre-existing unrelated root `design-qa.md` is preserved; this task's QA report
lives here to avoid overwriting other work.

final result: passed
