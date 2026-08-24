import { useEffect, useRef } from 'react'
import { gsap } from '../lib/smooth'
import './sections.css'

const FRICTIONS = [
  ['Passwords and 2FA', 'Multi-step logins assume app confidence many were never taught.'],
  ['Small screens', 'Tiny fields and shifting layouts punish ageing eyes and hands.'],
  ['Asking for help', 'Today the workaround is a family member or the counter queue.'],
]

/** The one line the whole page hangs from, revealed word by word on scrub. */
export function Manifesto() {
  const root = useRef<HTMLElement>(null)
  const line = 'Digital services should not leave people behind.'

  useEffect(() => {
    if (!root.current) return
    const ctx = gsap.context(() => {
      gsap.fromTo(
        '.mani__w',
        { opacity: 0.16, y: 6 },
        {
          opacity: 1,
          y: 0,
          stagger: 0.06,
          ease: 'none',
          scrollTrigger: { trigger: root.current, start: 'top 82%', end: 'top 34%', scrub: true },
        }
      )
    }, root)
    return () => ctx.revert()
  }, [])

  return (
    <section className="section mani" ref={root} aria-label="Manifesto">
      <div className="wrap">
        <p className="mani__line">
          {line.split(' ').map((w, i) => (
            <span className="mani__w" key={i}>
              {w}&nbsp;
            </span>
          ))}
        </p>
      </div>
    </section>
  )
}

export function Problem() {
  const root = useRef<HTMLElement>(null)
  const num = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (!root.current || !num.current) return
    const el = num.current
    const ctx = gsap.context(() => {
      const counter = { v: 0 }
      gsap.to(counter, {
        v: 230000,
        ease: 'power1.out',
        scrollTrigger: { trigger: root.current, start: 'top 72%', end: 'top 28%', scrub: 0.5 },
        onUpdate: () => {
          el.textContent = Math.round(counter.v).toLocaleString('en-MY')
        },
      })
    }, root)
    return () => {
      ctx.revert()
      // Leave the true figure in the DOM, not whatever frame the scrub stopped on.
      el.textContent = (230000).toLocaleString('en-MY')
    }
  }, [])

  return (
    <section className="section problem" id="why" ref={root}>
      <div className="wrap">
        <p className="eyebrow">Why it exists</p>
        <h2 className="sec-title">The hardest part of a public service is the login screen.</h2>

        <div className="problem__grid">
          <figure className="problem__stat">
            {/*
              The figure is rendered correct and only then animated, so the value
              is right before scripts run and right for assistive tech.
            */}
            <p className="problem__num">
              <span ref={num}>230,000</span>
            </p>
            <figcaption className="problem__statlabel">
              Sarawakians aged 65 and over today
              <span>9.1 percent of 2.53 million. DOSM, 2025.</span>
            </figcaption>
          </figure>

          <ul className="problem__frictions">
            {FRICTIONS.map(([t, d]) => (
              <li className="chip card rv" key={t}>
                <b>{t}</b>
                <span>{d}</span>
              </li>
            ))}
          </ul>
        </div>

        <p className="problem__pivot">
          SFG removes the screen-skills requirement, <strong>not the security.</strong>
        </p>
      </div>
    </section>
  )
}
