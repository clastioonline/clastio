# Production improvement plan — 1 October 2026

## Review findings

- Template updates synchronously rendered six slides, tying the save request to LibreOffice; cached images could retain the previous preview.
- Template pages lacked failure recovery and shared-template ownership feedback. The detail layout was crowded on small desktops and phones.
- Several core screens treated failed requests as permanent loading states.
- The landing page explained the concept but lacked a concrete example, output details, background-work explanation, FAQs and mobile navigation.
- Password login accepted a `next` value starting with `//`, which can navigate outside the application.
- Offline users had no persistent indication that their connection had dropped.

## Implementation order

1. Finish template background refresh, validation, safe preview replacement, search/filter controls and responsive layout.
2. Verify core teacher screens at phone, tablet and desktop widths; fix overflow at its source.
3. Add recoverable request errors, offline feedback and safe internal sign-in redirects.
4. Expand the landing page with an interactive, explicitly illustrative lesson example, output descriptions, workflow detail, FAQs and mobile navigation. Avoid unverified quality, compliance or integration guarantees.
5. Run backend regressions, production build, browser template/responsiveness checks and the teacher/admin and background-work journeys. Record actual results in LAUNCH_REVIEW.md.

## Implementation status

Implemented the template workflow, discovery controls, landing detail sections, connection feedback, request recovery and internal redirect validation. Browser review additionally found and fixed narrow-screen overflow in Teacher Memory and admin Plans, Payments & Media, and Health & Logs. Regression checks are included in CI. See LAUNCH_REVIEW.md for completed validation and its limits.

## Release gates requiring the deployment environment

Rotate previously exposed credentials. Configure HTTPS and the production origin. Validate live AI output/cost, email, payment sandbox webhooks and enabled integrations. Verify backup restoration, monitoring and concurrent generation capacity. Review curriculum content, policies and incomplete Arabic coverage. Passing local offline tests does not certify these gates.
