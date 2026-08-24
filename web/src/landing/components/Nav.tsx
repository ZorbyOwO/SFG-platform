import { useEffect, useRef, useState } from 'react'
import { scrollToSection } from '../lib/smooth'
import { CTA_LABEL } from '../lib/site'
import './Nav.css'

const LINKS = [
  { label: 'What it is', target: '#what' },
  { label: 'How it works', target: '#how' },
  { label: 'Safety', target: '#safe' },
  { label: 'Proof', target: '#proof' },
]

export function Nav({ platformUrl }: { platformUrl: string }) {
  const [solid, setSolid] = useState(false)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState('')
  const sheet = useRef<HTMLDivElement>(null)
  const toggle = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const onScroll = () => setSolid(window.scrollY > 24)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    const targets = LINKS.map((l) => document.querySelector(l.target)).filter(
      (el): el is Element => Boolean(el)
    )
    if (!targets.length) return
    const io = new IntersectionObserver(
      (entries) => {
        const hit = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0]
        if (hit) setActive('#' + hit.target.id)
      },
      { rootMargin: '-45% 0px -45% 0px', threshold: [0, 0.25, 0.5] }
    )
    targets.forEach((t) => io.observe(t))
    return () => io.disconnect()
  }, [])

  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false)
        toggle.current?.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    sheet.current?.querySelector<HTMLElement>('a, button')?.focus()
    return () => {
      document.body.style.overflow = prev
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const go = (e: React.MouseEvent<HTMLAnchorElement>, target: string) => {
    e.preventDefault()
    setOpen(false)
    scrollToSection(target)
  }

  return (
    <header className={'nav' + (solid ? ' nav--solid' : '') + (open ? ' nav--open' : '')}>
      <div className="nav__inner wrap">
        <a
          className="nav__brand"
          href="#top"
          onClick={(e) => {
            e.preventDefault()
            setOpen(false)
            scrollToSection('#top')
          }}
        >
          {/*
            Both spellings ship; CSS shows whichever the bar has room for, so
            the wordmark never truncates and never crowds the controls.
          */}
          <span className="nav__brand-full">Sarawak Facial Gateway</span>
          <span className="nav__brand-short" aria-hidden="true">
            SFG
          </span>
        </a>

        <nav className="nav__links" aria-label="Sections">
          {LINKS.map((l) => (
            <a
              key={l.target}
              href={l.target}
              onClick={(e) => go(e, l.target)}
              className={'link-underline' + (active === l.target ? ' is-active' : '')}
              aria-current={active === l.target ? 'true' : undefined}
            >
              {l.label}
            </a>
          ))}
        </nav>

        <a className="btn nav__cta" href={platformUrl}>
          {CTA_LABEL}{' '}
          <span className="arrow" aria-hidden="true">
            &#8594;
          </span>
        </a>

        <button
          ref={toggle}
          className="nav__burger"
          aria-expanded={open}
          aria-controls="nav-sheet"
          aria-label={open ? 'Close menu' : 'Open menu'}
          onClick={() => setOpen((v) => !v)}
        >
          <span className={'nav__burger-ico' + (open ? ' is-open' : '')} aria-hidden="true">
            <i />
            <i />
          </span>
        </button>
      </div>

      <div
        id="nav-sheet"
        ref={sheet}
        className={'nav__sheet' + (open ? ' is-open' : '')}
        hidden={!open}
      >
        <nav aria-label="Sections">
          {LINKS.map((l) => (
            <a key={l.target} href={l.target} onClick={(e) => go(e, l.target)}>
              {l.label}
            </a>
          ))}
        </nav>
        <a
          className="btn btn--block"
          href={platformUrl}
          onClick={() => setOpen(false)}
        >
          {CTA_LABEL}{' '}
          <span className="arrow" aria-hidden="true">
            &#8594;
          </span>
        </a>
      </div>
    </header>
  )
}
