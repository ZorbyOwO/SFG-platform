import { PLATFORM_URL, CTA_LABEL, CONTACT } from '../lib/site'
import './sections.css'

const METRICS: Array<[string, string]> = [
  ['Completion time', 'Median seconds to complete a verification at the kiosk.'],
  ['Independent completion', 'Share of priority users finishing without assistance.'],
  ['Genuine and impostor match', 'Correctly accepted against correctly rejected identities.'],
  ['Spoof rejection', 'Printed-photo and replay attempts refused by liveness.'],
]

const TOOLS = ['YuNet', 'Silent-Face', 'SFace', 'PaddleOCR', 'FastAPI', 'Supabase']

export function Proof() {
  return (
    <section className="section proof" id="proof">
      <div className="wrap">
        <p className="eyebrow">Measured, not assumed</p>
        <h2 className="sec-title">A prototype that reports its own numbers</h2>
        <p className="sec-lede">
          Built by students at University of Technology Sarawak for Track 1: Public Services and
          Government Delivery. The prototype measures four things in real trials, and reports what
          it finds, never more.
        </p>

        <ul className="metrics">
          {METRICS.map(([t, d]) => (
            <li className="metric card rv" key={t}>
              <span className="metric__slot">In trials</span>
              <h3>{t}</h3>
              <p>{d}</p>
            </li>
          ))}
        </ul>

        <h3 className="tools__title">AI tools used</h3>
        <ul className="tools">
          {TOOLS.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
      </div>
    </section>
  )
}

export function Close() {
  return (
    <section className="section close" aria-label="Get started">
      <div className="wrap close__inner">
        <h2>Ready to see it work?</h2>
        <p>Opt-in. Encrypted. Yours to delete.</p>
        <a className="btn close__cta" href={PLATFORM_URL}>
          {CTA_LABEL}{' '}
          <span className="arrow" aria-hidden="true">
            &#8594;
          </span>
        </a>
      </div>
    </section>
  )
}

export function Footer() {
  return (
    <footer className="footer panel-dark">
      <div className="wrap footer__grid">
        <div>
          <b>Sarawak Facial Gateway</b>
          <p>An opt-in AI computer vision identity layer for inclusive public service delivery.</p>
        </div>

        <nav aria-label="Footer">
          <a href="#what">What it is</a>
          <a href="#how">How it works</a>
          <a href="#safe">Safety</a>
          <a href={PLATFORM_URL}>
            {CTA_LABEL}
          </a>
        </nav>

        <div className="footer__contact">
          <b>Contact us</b>
          <a href={CONTACT.phoneHref}>{CONTACT.phone}</a>
          <a href={`mailto:${CONTACT.email}`}>{CONTACT.email}</a>
        </div>

        <div className="footer__refs">
          <b>Sources</b>
          <span>DOSM, Current Population Estimates 2025</span>
          <span>EPU Sarawak, Digital Economy Blueprint 2030</span>
          <span>PDPA (Amendment) Act 2024 (Act A1727)</span>
          <span>Md Fadzil et al., Digital Health 2023</span>
          <span>SarawakPass, Sarawak Government</span>
        </div>
      </div>

      <div className="wrap footer__base">
        <span>&copy; 2026 TheRookiesUTS, University of Technology Sarawak</span>
      </div>
    </footer>
  )
}
