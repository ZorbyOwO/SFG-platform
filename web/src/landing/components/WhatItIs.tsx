import { useEffect, useRef } from 'react'
import { gsap } from '../lib/smooth'
import './sections.css'

const BENEFITS = [
  {
    t: 'No smartphone needed',
    d: 'Verification happens at the counter terminal. Your phone stays in your pocket, or at home.',
  },
  {
    t: 'Enrol once',
    d: 'One short assisted visit to register your face and choose your PIN. Recognised ever after.',
  },
  {
    t: 'Seconds, not forms',
    d: 'A passive camera check and six digits. No typing marathons, no reset-link scavenger hunts.',
  },
  {
    t: 'Always your choice',
    d: 'Opt-in only. Counters, cards and SarawakPass remain exactly as they are today.',
  },
]

/** The two-factor idea, stated once as an equation and then unpacked. */
export function WhatItIs() {
  const root = useRef<HTMLElement>(null)

  useEffect(() => {
    if (!root.current) return
    const ctx = gsap.context(() => {
      gsap.fromTo(
        '.eq__token',
        { x: (i: number) => (i === 0 ? -40 : i === 2 ? 40 : 0), opacity: 0 },
        {
          x: 0,
          opacity: 1,
          stagger: 0.12,
          duration: 0.65,
          ease: 'power3.out',
          scrollTrigger: { trigger: '.eq', start: 'top 84%' },
        }
      )
    }, root)
    return () => ctx.revert()
  }, [])

  return (
    <section className="section what" id="what" ref={root}>
      <div className="wrap">
        <p className="eyebrow">What it is</p>
        <h2 className="sec-title">Identity that fits in a glance</h2>

        <p className="eq" aria-label="Live face match plus personal PIN equals verified">
          <span className="eq__token eq__face">Live face match</span>
          <span className="eq__op" aria-hidden="true">
            +
          </span>
          <span className="eq__token eq__pin">Personal PIN</span>
          <span className="eq__op" aria-hidden="true">
            =
          </span>
          <span className="eq__token eq__ok">You are verified</span>
        </p>

        <ul className="benefits">
          {BENEFITS.map((b) => (
            <li className="benefit card rv" key={b.t}>
              <h3>{b.t}</h3>
              <p>{b.d}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
