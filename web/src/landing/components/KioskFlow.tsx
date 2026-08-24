import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * The five kiosk steps, each with a drawn frame rather than an abstract dot
 * pattern. The carousel plays on its own and can also be swiped or scrolled
 * sideways; scrolling the page is no longer a prerequisite for seeing it.
 */

export const STEPS = [
  {
    k: 'Look',
    title: 'Face the camera',
    d: 'The camera finds exactly one face and lines it up in the guide.',
  },
  {
    k: 'Verify',
    title: 'Prove you are live',
    d: 'A passive check accepts a real person and refuses a printed photo or a screen replay.',
  },
  {
    k: 'Match',
    title: 'Compare the template',
    d: 'Your face becomes an encrypted template, and only that is compared against your record.',
  },
  {
    k: 'Confirm',
    title: 'Key your PIN',
    d: 'The screen shows masked details. Six digits you chose approve the request.',
  },
  {
    k: 'Access',
    title: 'You are through',
    d: 'Access is granted and logged. About twenty seconds, start to finish.',
  },
] as const

const HOLD = 4200

/* ------------------------------------------------------------------ *
 * Frames
 * ------------------------------------------------------------------ */

const S = { screen: '#141210', line: 'rgba(243,239,232,0.22)', ink: '#F3EFE8' }

function Screen({ children }: { children: React.ReactNode }) {
  return (
    <svg viewBox="0 0 320 200" className="flow__svg" role="presentation" focusable="false">
      <rect x="8" y="8" width="304" height="184" rx="14" fill={S.screen} stroke={S.line} />
      {children}
    </svg>
  )
}

/** Simplified head and shoulders, reused across frames. */
function Person({ x = 0, y = 0, s = 1, dim = false }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`} opacity={dim ? 0.45 : 1}>
      <path d="M-34 46 C-34 22 -18 12 0 12 C18 12 34 22 34 46 Z" fill="#C79A7B" />
      <circle cx="0" cy="-10" r="22" fill="#EBCDB4" />
      <path d="M-22 -16 C-20 -34 20 -34 22 -16 C22 -28 14 -36 0 -36 C-14 -36 -22 -28 -22 -16 Z" fill="#2A2320" />
    </g>
  )
}

function FrameLook() {
  return (
    <Screen>
      <ellipse cx="160" cy="96" rx="46" ry="60" fill="none" stroke="#F2C94C" strokeWidth="2.5" strokeDasharray="7 7" />
      <Person x={160} y={104} s={1.05} />
      {/* The attribute transform is the resting place; the CSS animation
          overrides it. Without it the line parks outside the screen whenever
          motion is switched off. */}
      <g className="flow__scanline" transform="translate(0 96)">
        <rect x="100" y="-1.25" width="120" height="2.5" fill="#C8102E" />
      </g>
      {[
        [110, 46, 1, 1], [210, 46, -1, 1], [110, 146, 1, -1], [210, 146, -1, -1],
      ].map(([x, y, sx, sy], i) => (
        <path key={i} d={`M${x} ${(y as number) + 12 * (sy as number)} L${x} ${y} L${(x as number) + 12 * (sx as number)} ${y}`}
          stroke="#C8102E" strokeWidth="2.5" fill="none" />
      ))}
      <text x="160" y="182" className="flow__cap" textAnchor="middle">ONE FACE DETECTED</text>
    </Screen>
  )
}

function FrameVerify() {
  return (
    <Screen>
      <g>
        <rect x="26" y="30" width="118" height="114" rx="10" fill="rgba(99,214,155,0.09)" stroke="#63D69B" strokeWidth="2" />
        <Person x={85} y={96} s={0.8} />
        <circle cx="128" cy="48" r="13" fill="#63D69B" />
        <path d="M122 48 l4 4 l8 -9" stroke="#10231A" strokeWidth="2.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        <text x="85" y="168" className="flow__cap" textAnchor="middle" fill="#63D69B">LIVE PERSON</text>
      </g>
      <g>
        <rect x="176" y="30" width="118" height="114" rx="10" fill="rgba(200,16,46,0.09)" stroke="#C8102E" strokeWidth="2" />
        {/* a held-up photo of a face */}
        <rect x="205" y="52" width="60" height="70" rx="4" fill="#241F1B" stroke="rgba(243,239,232,0.35)" />
        <Person x={235} y={104} s={0.48} dim />
        <circle cx="278" cy="48" r="13" fill="#C8102E" />
        <path d="M273 43 l10 10 M283 43 l-10 10" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" />
        <text x="235" y="168" className="flow__cap" textAnchor="middle" fill="#E8677F">PHOTO REFUSED</text>
      </g>
    </Screen>
  )
}

function FrameMatch() {
  return (
    <Screen>
      <Person x={54} y={112} s={0.72} />
      <text x="54" y="170" className="flow__cap" textAnchor="middle">YOUR FACE</text>

      <path d="M92 96 h22" stroke="#F2C94C" strokeWidth="2" />
      <path d="M110 91 l6 5 l-6 5" fill="#F2C94C" />

      <g>
        <rect x="124" y="58" width="72" height="76" rx="8" fill="rgba(242,201,76,0.08)" stroke="#F2C94C" strokeWidth="2" />
        {Array.from({ length: 12 }).map((_, i) => (
          <rect key={i} x={136 + (i % 4) * 14} y={74 + Math.floor(i / 4) * 14}
            width="9" height="9" rx="2" fill="#F2C94C" opacity={0.35 + ((i * 7) % 10) / 14} />
        ))}
        <path d="M160 122 m-9 0 a9 9 0 0 1 18 0" stroke="#F2C94C" strokeWidth="2" fill="none" />
        <rect x="151" y="121" width="18" height="12" rx="2.5" fill="#F2C94C" />
      </g>
      <text x="160" y="163" className="flow__cap" textAnchor="middle" fill="#F2C94C">ENCRYPTED</text>
      <text x="160" y="176" className="flow__cap" textAnchor="middle" fill="#F2C94C">TEMPLATE</text>

      <path d="M206 96 h22" stroke="#F2C94C" strokeWidth="2" />
      <path d="M224 91 l6 5 l-6 5" fill="#F2C94C" />

      <g>
        <rect x="238" y="58" width="58" height="76" rx="8" fill="rgba(243,239,232,0.06)" stroke={S.line} strokeWidth="2" />
        {[76, 90, 104].map((y) => (
          <rect key={y} x="250" y={y} width="34" height="5" rx="2.5" fill="rgba(243,239,232,0.4)" />
        ))}
        <circle cx="267" cy="122" r="10" fill="#63D69B" />
        <path d="M262 122 l3.5 3.5 l7 -7.5" stroke="#10231A" strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </g>
      <text x="267" y="170" className="flow__cap" textAnchor="middle">YOUR RECORD</text>
    </Screen>
  )
}

function FrameConfirm() {
  return (
    <Screen>
      <rect x="34" y="28" width="252" height="36" rx="8" fill="rgba(243,239,232,0.06)" stroke={S.line} />
      <text x="48" y="51" className="flow__label">NAME</text>
      <text x="272" y="51" className="flow__value" textAnchor="end">AHMAD B. ***</text>

      <text x="160" y="88" className="flow__cap" textAnchor="middle" fill="#F2C94C">ENTER YOUR PIN</text>

      <g>
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <circle key={i} cx={110 + i * 20} cy="106" r="6.5"
            fill={i < 4 ? '#F2C94C' : 'none'} stroke="#F2C94C" strokeWidth="2" />
        ))}
      </g>

      <g>
        {Array.from({ length: 9 }).map((_, i) => (
          <rect key={i} x={112 + (i % 3) * 34} y={126 + Math.floor(i / 3) * 22}
            width="26" height="16" rx="4" fill="rgba(243,239,232,0.09)" stroke={S.line} />
        ))}
      </g>
    </Screen>
  )
}

function FrameAccess() {
  return (
    <Screen>
      <circle cx="160" cy="82" r="34" fill="rgba(99,214,155,0.14)" stroke="#63D69B" strokeWidth="2.5" />
      <path d="M146 82 l10 10 l19 -21" stroke="#63D69B" strokeWidth="4.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <text x="160" y="140" className="flow__value" textAnchor="middle" fill="#63D69B">ACCESS GRANTED</text>
      <rect x="52" y="152" width="216" height="24" rx="6" fill="rgba(243,239,232,0.06)" stroke={S.line} />
      <text x="160" y="168" className="flow__cap" textAnchor="middle">LOGGED &#183; 19 SECONDS &#183; COUNTER 3</text>
    </Screen>
  )
}

const FRAMES = [FrameLook, FrameVerify, FrameMatch, FrameConfirm, FrameAccess]

/* ------------------------------------------------------------------ *
 * Carousel
 * ------------------------------------------------------------------ */

export function KioskFlow({ reduced }: { reduced: boolean }) {
  const [index, setIndex] = useState(0)
  const [paused, setPaused] = useState(false)
  const track = useRef<HTMLDivElement>(null)
  const syncing = useRef(false)

  const goTo = useCallback((i: number, smooth = true) => {
    const el = track.current
    if (!el) return
    const n = ((i % STEPS.length) + STEPS.length) % STEPS.length
    syncing.current = true
    el.scrollTo({ left: n * el.clientWidth, behavior: smooth && !reduced ? 'smooth' : 'auto' })
    setIndex(n)
    // Long enough to cover the smooth scroll, so the scroll listener does not
    // fight the animation and snap the index to an intermediate slide.
    window.setTimeout(() => (syncing.current = false), 700)
  }, [reduced])

  // Auto-advance. Never runs under reduced motion, and yields to the visitor.
  useEffect(() => {
    if (reduced || paused) return
    const t = window.setTimeout(() => goTo(index + 1), HOLD)
    return () => window.clearTimeout(t)
  }, [index, paused, reduced, goTo])

  // Keep the index in step with a manual swipe or sideways scroll.
  useEffect(() => {
    const el = track.current
    if (!el) return
    let raf = 0
    const onScroll = () => {
      if (syncing.current) return
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        const i = Math.round(el.scrollLeft / Math.max(1, el.clientWidth))
        setIndex((prev) => (i !== prev ? i : prev))
      })
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      el.removeEventListener('scroll', onScroll)
      cancelAnimationFrame(raf)
    }
  }, [])

  // Keep the visible slide correct if the track is resized.
  useEffect(() => {
    const el = track.current
    if (!el) return
    const ro = new ResizeObserver(() => goTo(index, false))
    ro.observe(el)
    return () => ro.disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index])

  const step = STEPS[index]

  return (
    <div
      className="flow"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={() => setPaused(false)}
      onTouchStart={() => setPaused(true)}
      /* Without this the first tap on a phone pauses the flow permanently. */
      onTouchEnd={() => window.setTimeout(() => setPaused(false), 2500)}
      onTouchCancel={() => setPaused(false)}
      role="group"
      aria-roledescription="carousel"
      aria-label="How a kiosk visit runs, step by step"
    >
      <div
        className="flow__track"
        ref={track}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'ArrowRight') { e.preventDefault(); goTo(index + 1) }
          if (e.key === 'ArrowLeft') { e.preventDefault(); goTo(index - 1) }
        }}
      >
        {FRAMES.map((Frame, i) => (
          <div
            className={'flow__slide' + (i === index ? ' is-current' : '')}
            key={STEPS[i].k}
            role="group"
            aria-roledescription="slide"
            aria-label={`Step ${i + 1} of ${STEPS.length}: ${STEPS[i].k}`}
          >
            <Frame />
          </div>
        ))}
      </div>

      <div className="flow__meta" aria-live="polite">
        <p className="flow__step">
          <b>{index + 1}</b>
          <span>{step.title}</span>
        </p>
        <p className="flow__desc">{step.d}</p>
      </div>

      <div className="flow__dots">
        {STEPS.map((s, i) => (
          <button
            key={s.k}
            className={'flow__dot' + (i === index ? ' is-on' : '')}
            aria-label={`Show step ${i + 1}, ${s.k}`}
            aria-current={i === index ? 'true' : undefined}
            onClick={() => goTo(i)}
          >
            <i />
          </button>
        ))}
      </div>
    </div>
  )
}
