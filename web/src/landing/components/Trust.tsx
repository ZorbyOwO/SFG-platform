import './sections.css'

const DOUBTS: Array<[string, string]> = [
  [
    'Is my photo stored?',
    'No. The photo is discarded the moment your encrypted mathematical template is created. Only the template remains, and only the verification service can read it.',
  ],
  [
    'Could someone use my face without me knowing?',
    'No. A face match alone never grants access. Your personal PIN is always the second key, and nothing moves without it.',
  ],
  [
    'What about a printed photo of me?',
    'Liveness checks reject printed photos and screen replays. In our prototype trials this is measured and reported, never assumed.',
  ],
  [
    'Am I forced to use it?',
    'Never. SFG is opt-in and voluntary. Existing counters, cards and SarawakPass remain exactly as they are.',
  ],
  [
    'Who can see my data?',
    'Templates are locked away from every browser and user account by deny-by-default database rules. You can request deletion at any time.',
  ],
  [
    'Is my data protected by law?',
    "The design follows Malaysia's PDPA (Amendment) 2024, which expressly treats biometric data as sensitive personal data.",
  ],
]

const PROMISES: Array<[string, string, 'consent' | 'audit' | 'delete']> = [
  ['Consent first', 'A plain-language screen appears before any camera opens. Nothing starts without your yes.', 'consent'],
  ['Every event audited', 'Each verification writes an entry staff and auditors can review afterwards.', 'audit'],
  ['Yours to delete', 'Ask once and your template is removed. Your other ways of getting served stay open.', 'delete'],
]

function PromiseIcon({ kind }: { kind: 'consent' | 'audit' | 'delete' }) {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {kind === 'consent' && (
        <>
          <path d="M12 3l7 3v5c0 4.4-3 8.2-7 10-4-1.8-7-5.6-7-10V6z" />
          <path d="M9 12l2 2 4-4" />
        </>
      )}
      {kind === 'audit' && (
        <>
          <path d="M5 3h11l3 3v15H5z" />
          <path d="M9 9h6M9 13h6M9 17h3" />
        </>
      )}
      {kind === 'delete' && (
        <>
          <path d="M4 7h16" />
          <path d="M9 7V5h6v2" />
          <path d="M6 7l1 13h10l1-13" />
          <path d="M10 11v6M14 11v6" />
        </>
      )}
    </svg>
  )
}

export function SafeByDesign() {
  return (
    <section className="section safe" id="safe">
      <div className="wrap">
        <p className="eyebrow">Safe by design</p>
        <h2 className="sec-title">Asked and answered</h2>
        <p className="sec-lede">
          Biometrics earn trust by answering hard questions early. Here are the ones that matter,
          and the three promises behind them.
        </p>

        <ul className="promises">
          {PROMISES.map(([t, d, kind]) => (
            <li className="promise card rv" key={t}>
              <span className="promise__ico" aria-hidden="true">
                <PromiseIcon kind={kind} />
              </span>
              <h3>{t}</h3>
              <p>{d}</p>
            </li>
          ))}
        </ul>

        <div className="flips">
          {DOUBTS.map(([q, a], i) => (
            <details className="flip card rv" key={q}>
              <summary>
                <span className="flip__n" aria-hidden="true">{String(i + 1).padStart(2, '0')}</span>
                <span className="flip__q">{q}</span>
                <i aria-hidden="true" />
              </summary>
              <div className="flip__a">
                <p>{a}</p>
              </div>
            </details>
          ))}
        </div>
      </div>
    </section>
  )
}

const ALIGNS: Array<[string, string]> = [
  ['SDG 10.2', 'Social and economic inclusion regardless of age or disability.'],
  ['SDG 16.6', 'Effective, accountable, transparent institutions.'],
  ['SDG 9.1', 'Reliable, equitable infrastructure for all.'],
  ['Blueprint 2030, P3', 'Tailored, integrated public service delivery with data protection.'],
  ['Blueprint 2030, P5', 'Equal access to digital economy opportunities.'],
  ['Blueprint 2030, P4', 'Catalyse AI adoption in the public sector.'],
]

export function BuiltForSarawak() {
  return (
    <section className="section sarawak" aria-label="Built for Sarawak">
      <div className="wrap">
        <p className="eyebrow">Built for Sarawak</p>
        <h2 className="sec-title">Local problem. Local team. Measured scope.</h2>

        <div className="sarawak__grid">
          <div className="sarawak__copy">
            <p>
              SFG is designed for Sarawak&apos;s ageing population and citizens with disabilities.
              It is an optional complement to <b>SarawakPass</b> and existing counter services,
              never a replacement.
            </p>
            <p>
              It is a university prototype today. Wider government integration is future work, and
              we state it as future work.
            </p>
          </div>

          <ul className="aligns">
            {ALIGNS.map(([k, v]) => (
              <li className="align card rv" key={k}>
                <b>{k}</b>
                <span>{v}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  )
}
