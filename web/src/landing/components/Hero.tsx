import { useEffect, useRef } from 'react'
import { PLATFORM_URL, CTA_LABEL } from '../lib/site'
import { scrollToSection, gsap, ScrollTrigger } from '../lib/smooth'
import './hero.css'

const PROOF = [
  'Opt-in and voluntary',
  'Encrypted template, never your photo',
  'Works alongside existing counters',
]

/**
 * Intrinsic size of the hero artwork. Declared here and used for the CSS
 * aspect ratio so the stage reserves its exact box before the image decodes
 * and nothing shifts on load.
 */
const ART = { w: 964, h: 1232 }

export function Hero({ reduced }: { reduced: boolean }) {
  const root = useRef<HTMLElement>(null)
  const visual = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!root.current || reduced) return
    const ctx = gsap.context(() => {
      gsap.to(visual.current, {
        yPercent: 8,
        opacity: 0.35,
        ease: 'none',
        scrollTrigger: {
          trigger: root.current,
          start: 'bottom 85%',
          end: 'bottom 25%',
          scrub: true,
        },
      })
      ScrollTrigger.refresh()
    }, root)
    return () => ctx.revert()
  }, [reduced])

  return (
    <section className="hero" id="top" ref={root}>
      <div className="wrap hero__grid">
        <div className="hero__copy">
          <p className="eyebrow">Sarawak Facial Gateway</p>
          <h1 className="hero__h1">
Your face opens the door. <em>Your PIN says yes.</em>
          </h1>
          <p className="hero__sub">
            For Sarawakians who find app logins and passwords a barrier, and for the families who
            help them. SFG verifies identity at any enabled counter with a live face check and a
            personal PIN. No smartphone needed.
          </p>

          <div className="hero__ctas">
            <a className="btn" href={PLATFORM_URL}>
              {CTA_LABEL} <span className="arrow" aria-hidden="true">&#8594;</span>
            </a>
            <a
              className="btn btn--ghost"
              href="#how"
              onClick={(e) => {
                e.preventDefault()
                scrollToSection('#how')
              }}
            >
              See how it works
            </a>
          </div>

          <ul className="hero__proof">
            {PROOF.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>

        <div className="hero__visual" ref={visual}>
          <div
            className="hero__stage"
            style={{ ['--art' as string]: `${ART.w} / ${ART.h}` }}
          >
            <img
              className="hero__art"
              src="/landing/hero/face-640.webp"
              srcSet="/landing/hero/face-280.webp 280w, /landing/hero/face-360.webp 360w, /landing/hero/face-480.webp 480w, /landing/hero/face-640.webp 640w, /landing/hero/face-720.webp 720w, /landing/hero/face-900.webp 900w, /landing/hero/face-964.webp 964w"
              sizes="(max-height: 560px) and (orientation: landscape) min(100vw - 56px, 240px), (max-width: 360px) min(100vw - 56px, 250px), (min-width: 900px) 460px, (min-width: 560px) min(100vw - 56px, 430px), min(100vw - 56px, 380px)"
              width={ART.w}
              height={ART.h}
              alt="A face being checked by the system, with the detected facial landmarks joined into a mesh."
              /* Above the fold, so it is the LCP candidate: never lazy. */
              loading="eager"
              fetchPriority="high"
              decoding="async"
              draggable={false}
            />
            <span className="hero__sweep" aria-hidden="true" />
            <i className="vf vf--tl" aria-hidden="true" />
            <i className="vf vf--tr" aria-hidden="true" />
            <i className="vf vf--bl" aria-hidden="true" />
            <i className="vf vf--br" aria-hidden="true" />
          </div>
          <p className="hero__readout" aria-hidden="true">
            <span className="hero__rec" />
            <span>Live</span>
            <span>Liveness</span>
            <span>Template</span>
          </p>
        </div>
      </div>

      <a
        className="hero__scrollcue"
        href="#why"
        aria-label="Scroll to why SFG exists"
        onClick={(e) => {
          e.preventDefault()
          scrollToSection('#why')
        }}
      >
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </a>
    </section>
  )
}
