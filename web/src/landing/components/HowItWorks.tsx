import { useEffect, useRef } from 'react'
import { gsap } from '../lib/smooth'
import { KioskFlow, STEPS } from './KioskFlow'
import './sections.css'

const ENROL: Array<[string, string]> = [
  ['Give consent', 'A plain-language screen before any camera opens. Your call, recorded and auditable.'],
  ['Quick identity check', 'Counter staff confirm who you are. The standard check, nothing extra.'],
  ['Look at the camera', 'Three seconds. The system detects your face and checks liveness.'],
  ['Template encrypted and linked', 'Your photo is discarded. Only a mathematical template is kept, encrypted.'],
  ['Choose your PIN', 'Six digits you pick. From then on your face identifies, your PIN authorises.'],
]

/** Enrolment once, then the kiosk flow, shown as a self-playing sequence. */
export function HowItWorks({ reduced }: { reduced: boolean }) {
  const root = useRef<HTMLElement>(null)

  useEffect(() => {
    if (!root.current) return
    const ctx = gsap.context(() => {
      gsap.utils.toArray<HTMLElement>('.lane').forEach((lane) => {
        const rail = lane.querySelector('.lane__rail i')
        if (!rail) return
        gsap.fromTo(
          rail,
          { scaleX: 0 },
          {
            scaleX: 1,
            ease: 'none',
            scrollTrigger: { trigger: lane, start: 'top 78%', end: 'bottom 58%', scrub: true },
          }
        )
      })
    }, root)
    return () => ctx.revert()
  }, [])

  return (
    <section className="section how panel-dark" id="how" ref={root}>
      <div className="wrap">
        <p className="eyebrow">How it works</p>
        <h2 className="sec-title">Enrol once. Then just show up.</h2>

        <div className="lane">
          <h3 className="lane__title">
            <span aria-hidden="true">1</span> Once: enrol at an authorised counter
          </h3>
          <div className="lane__rail" aria-hidden="true">
            <i />
          </div>
          <ol className="steps">
            {ENROL.map(([t, d], i) => (
              <li className="step card rv" key={t}>
                <b>{String(i + 1).padStart(2, '0')}</b>
                <div>
                  <strong>{t}</strong>
                  <span>{d}</span>
                </div>
              </li>
            ))}
          </ol>
        </div>

        <div className="lane">
          <h3 className="lane__title">
            <span aria-hidden="true">2</span> Every visit: verify at the kiosk
          </h3>
          <div className="lane__rail" aria-hidden="true">
            <i />
          </div>

          <div className="how__duo">
            <ol className="steps steps--kiosk">
              {STEPS.map((s, i) => (
                <li className="step step--k card rv" key={s.k}>
                  <b>{s.k}</b>
                  <div>
                    <span>{s.d}</span>
                  </div>
                </li>
              ))}
            </ol>

            <div className="flowwrap">
              <KioskFlow reduced={reduced} />
            </div>
          </div>
        </div>

        <p className="engine-note">
          Under the hood: <b>YuNet</b> detection, <b>Silent-Face</b> liveness, <b>SFace</b>{' '}
          encrypted templates, server-side matching.
        </p>
      </div>
    </section>
  )
}
