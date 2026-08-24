import Lenis from 'lenis'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useEffect } from 'react'

gsap.registerPlugin(ScrollTrigger)

let lenisInstance: Lenis | null = null

/** Shared smooth-scroll + RAF loop. One ticker drives Lenis and ScrollTrigger. */
export function useSmoothScroll(enabled: boolean) {
  useEffect(() => {
    if (!enabled) return
    const lenis = new Lenis({
      duration: 1.15,
      easing: (t: number) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: true,
      touchMultiplier: 1.6,
    })
    lenisInstance = lenis
    lenis.on('scroll', ScrollTrigger.update)
    const raf = (time: number) => lenis.raf(time * 1000)
    gsap.ticker.add(raf)
    gsap.ticker.lagSmoothing(0)
    return () => {
      gsap.ticker.remove(raf)
      lenis.destroy()
      lenisInstance = null
    }
  }, [enabled])
}

export function scrollToSection(selector: string) {
  const el = document.querySelector(selector)
  if (!el) return
  if (lenisInstance) lenisInstance.scrollTo(el as HTMLElement, { offset: -70 })
  else el.scrollIntoView({ behavior: 'smooth' })
}

export { gsap, ScrollTrigger }
