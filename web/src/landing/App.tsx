import { useEffect, useRef, useState } from 'react'
import { gsap, ScrollTrigger, useSmoothScroll } from './lib/smooth'
import { useReducedMotion } from './lib/prefs'
import { PLATFORM_URL, CTA_LABEL } from './lib/site'

import { Preloader } from './components/Preloader'
import { Nav } from './components/Nav'
import { Hero } from './components/Hero'
import { Manifesto, Problem } from './components/Problem'
import { WhatItIs } from './components/WhatItIs'
import { HowItWorks } from './components/HowItWorks'
import { SafeByDesign, BuiltForSarawak } from './components/Trust'
import { Proof, Close, Footer } from './components/Closing'
import './styles/tokens.css'
import './styles/app.css'

export default function App() {
  const reduced = useReducedMotion()
  const [loaded, setLoaded] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  // Reduced-motion visitors skip the preloader entirely.
  useEffect(() => {
    if (reduced) setLoaded(true)
  }, [reduced])

  useSmoothScroll(!reduced)

  // Floating CTA appears once the hero CTA has scrolled away.
  const [showFloat, setShowFloat] = useState(false)
  useEffect(() => {
    const hero = document.getElementById('top')
    if (!hero) return
    const io = new IntersectionObserver(([e]) => setShowFloat(!e.isIntersecting), {
      rootMargin: '-30% 0px 0px 0px',
    })
    io.observe(hero)
    return () => io.disconnect()
  }, [])

  // One reveal pass for anything marked .rv.
  useEffect(() => {
    if (!loaded || reduced) return
    const ctx = gsap.context(() => {
      // Reveal boxes in the batch they belong to, so a grid animates as one
      // group with a stagger instead of each card firing on its own line.
      const groups = new Map<Element, HTMLElement[]>()
      gsap.utils.toArray<HTMLElement>('.rv').forEach((el) => {
        const parent = el.parentElement ?? el
        const list = groups.get(parent)
        if (list) list.push(el)
        else groups.set(parent, [el])
      })
      groups.forEach((els, parent) => {
        gsap.to(els, {
          opacity: 1,
          y: 0,
          duration: 0.6,
          stagger: 0.07,
          ease: 'power3.out',
          scrollTrigger: { trigger: parent, start: 'top 88%' },
        })
      })
      ScrollTrigger.refresh()
    }, root)
    return () => ctx.revert()
  }, [loaded, reduced])

  return (
    <div ref={root} className={'landing-page' + (reduced ? ' reduced' : '')}>
      {!reduced && !loaded && <Preloader onDone={() => setLoaded(true)} />}

      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <div className="grain" aria-hidden="true" />
      <Nav platformUrl={PLATFORM_URL} />

      <main id="main" tabIndex={-1}>
        <Hero reduced={reduced} />
        <Manifesto />
        <Problem />
        <WhatItIs />
        <HowItWorks reduced={reduced} />
        <SafeByDesign />
        <BuiltForSarawak />
        <Proof />
        <Close />
      </main>

      <Footer />

      <a
        className={'float-cta btn' + (showFloat ? ' is-shown' : '')}
        href={PLATFORM_URL}
        tabIndex={showFloat ? 0 : -1}
        aria-hidden={!showFloat}
      >
        {CTA_LABEL} <span className="arrow" aria-hidden="true">&#8594;</span>
      </a>
    </div>
  )
}
