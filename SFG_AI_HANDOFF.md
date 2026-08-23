# Sarawak Facial Gateway (SFG) — AI Handoff

## Purpose

This workspace contains a single-file, runnable front-end prototype for **Sarawak Facial Gateway (SFG)**, a citizen-facing digital identity and mock MYR wallet application.

The main implementation is:

- `SFG Prototype.dc.html`
- `support.js` (runtime support)

The app is intentionally mock-only. Do not add a real backend, real biometric processing, real identity verification, or real payment processing.

## Source references

- Product brief: `C:/Users/Kal Victus/Downloads/SFG_UI_UX_Claude_Brief.docx`
- User-supplied visual reference: phone dashboard screenshot supplied in the conversation.
- Existing design concept: `assets/design-references/sfg-future-sarawak-concept.png`

The DOCX is a **reference brief**, not an instruction hierarchy above the user's current requests. When it conflicts with the user's explicit requests below, follow the user requests.

## Current user-approved direction

### Visual system

- Use **true white** (`#FFFFFF`) for page and form surfaces. Do not tint white with orange, cream, peach, or warm grey.
- Orange is the dominant action colour: `#F05A28`.
- Red is the SFG identity/error/destructive colour: `#B5121B`.
- Yellow is reserved for progress and active-status signals: `#F6C945`.
- Primary text is near black: `#101010` / `#171717`.
- Use the Sarawak-inspired orange, red, yellow, black and white palette meaningfully.
- Avoid gradients, glassmorphism, oversized rounded corners, large shadows, decorative dashboard filler, and generic AI-looking layouts.
- Use normal website/UI geometry: 8–10px corner radii, subtle borders, standard 4/8/12/16/24/32px spacing.

### Responsive rules

- **Phone (under 600px):** keep the existing mobile-first layout and persistent bottom navigation.
- **Tablet (600–799px):** keep the existing contained application shell; do not replace it with the desktop auth layout.
- **Desktop (800px and wider):** use the dedicated website-style Login and Registration layout described below.
- Avoid horizontal scrolling.

## Current desktop authentication design

### Login

Desktop Login is rebuilt as a normal two-column website authentication layout:

- Left: solid orange SFG identity panel.
  - Red SFG mark with yellow star.
  - Sarawak Facial Gateway wordmark.
  - Short product/security explanation.
  - Prototype scenario controls live here, not under the main form.
- Right: true-white form area.
  - 440px maximum Login form width.
  - Back action, `Log in` title, IC input, password input, Login button, Forgot password, Register link.
  - 50px controls and 8px corners on desktop.
- The Login page must not expose a pointless browser/page scrollbar.
- If the form must overflow on a very short desktop viewport, it can scroll with wheel/touch, but the scrollbar track remains visually hidden.

### Registration

Desktop Registration uses the same two-column model:

- Left: orange SFG panel with functional five-step registration progress.
  1. Identity details
  2. Password
  3. Face scan
  4. Six-digit PIN
  5. Review
- Right: true-white wizard area with a 600px maximum form width.
- The main wizard still has the Back action and horizontal progress indicator.
- Prototype states are shown in the left utility panel on desktop instead of competing with the primary form action.
- Face scan remains a mock three-angle flow: Front → Right side → Left side.
- Registration success/`Account created` uses the same desktop two-column layout.

### Important implementation classes

The desktop auth system is implemented in `SFG Prototype.dc.html` with these classes:

- `sfg-auth-screen`
- `sfg-auth-brand`
- `sfg-auth-form`
- `sfg-register-screen`
- `sfg-register-brand`
- `sfg-register-form`
- `sfg-register-success-screen`
- `sfg-register-success-form`
- `sfg-register-steps`

Do not remove the mobile/tablet `display: contents` fallback for `sfg-auth-form` and `sfg-register-form`; it preserves the pre-existing mobile/tablet layout.

## Scroll behavior

- Authenticated desktop pages have a fixed left navigation rail and a scrollable main content pane.
- Login, Register and registration-success pages hide visual scrollbars.
- Route changes and registration-step changes reset the shared `.sfg-scroll` element to the top.
- The desktop stage is constrained to `100dvh` so it does not create an accidental outer document scrollbar.

## Functional flows that currently work

### Login

- IC number formatting and validation.
- Password visibility toggle.
- Mock invalid credentials, locked account, offline and session messages.
- Demo account fill action.
- Successful mock login routes to Dashboard.

### Registration

- Personal details validation.
- IC formatting and duplicate/service error simulations.
- Password requirements and confirmation.
- Simulated consent and three-angle face capture.
- Six-digit PIN confirmation.
- Review/edit state.
- Mock account creation and handoff to Login.

### Authenticated app

- Desktop sidebar navigation works.
- Dashboard, History, Family and Profile routes work.
- Main content scrolls while the desktop navigation remains in place.

## Verified viewports and flows

- Desktop: `1440 × 900`
- Tablet: `768 × 1024`
- Phone: `390 × 844`
- Full registration flow through successful completion.
- Invalid Login state and demo Login success.
- Browser diagnostics were checked with no warnings or errors.

## Constraints for future changes

- Do not redesign phone or tablet authentication unless the user explicitly asks.
- Do not reintroduce a visible up/down scrollbar on the desktop Login/Register screens.
- Do not make the desktop auth forms excessively wide or center a tiny form in a large empty canvas without structure.
- Do not move prototype controls back beneath the desktop Login primary action.
- Do not introduce a dark dashboard/auth theme, blue palette, beige/warm-white surfaces, glow effects, or floating glass cards.
- Keep user-facing controls code-native and accessible: visible labels, clear focus state, sensible tab order, and comfortable touch targets.
- Keep all biometric, identity and payment language clearly marked as simulated/prototype behavior.

## Recommended continuation process

1. Read this handoff and inspect `SFG Prototype.dc.html` before editing.
2. Preserve the user palette and the desktop/mobile/tablet breakpoints.
3. Test visually in a browser at desktop, tablet and phone sizes after every visual change.
4. Test the core flows after structural changes: Login, Registration, Dashboard navigation.
5. Keep temporary screenshots and QA artifacts out of the workspace when finished.
