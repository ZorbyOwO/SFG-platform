import { useEffect, useRef, useState } from 'react'
import './Preloader.css'

export function Preloader({ onDone }: { onDone: () => void }) {
  const [n, setN] = useState(0)
  const [hidden, setHidden] = useState(false)
  const raf = useRef(0)

  useEffect(() => {
    let v = 0
    const tick = () => {
      v += Math.floor(Math.random() * 11) + 4
      if (v >= 100) {
        setN(100)
        window.setTimeout(() => setHidden(true), 350)
        window.setTimeout(onDone, 950)
        return
      }
      setN(v)
      raf.current = window.setTimeout(tick, 42) as unknown as number
    }
    raf.current = window.setTimeout(tick, 80) as unknown as number
    return () => window.clearTimeout(raf.current)
  }, [onDone])

  return (
    <div className={'preloader' + (hidden ? ' preloader--hide' : '')} aria-hidden="true">
      <svg viewBox="0 0 100 100" className="preloader__mark">
        <path
          className="preloader__poly"
          d="M30 12 H12 V30 M70 12 H88 V30 M88 70 V88 H70 M30 88 H12 V70"
          fill="none"
          stroke="#C8102E"
          strokeWidth="4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle className="preloader__dot" cx="50" cy="50" r="5" fill="#C8102E" />
      </svg>
      <div className="preloader__count">{n}</div>
    </div>
  )
}
