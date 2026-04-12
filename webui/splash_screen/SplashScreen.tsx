import { useCallback, useLayoutEffect, useRef } from 'react'
import gsap from 'gsap'
import { SplitText } from 'gsap/SplitText'
import CustomEase from 'gsap/CustomEase'
import { api } from '../src/utils/api'

interface SplashScreenProps {
  onComplete: () => void
}

gsap.registerPlugin(SplitText, CustomEase)

const wait = (ms: number) => new Promise(resolve => window.setTimeout(resolve, ms))

export default function SplashScreen({ onComplete }: SplashScreenProps) {
  const rootRef = useRef<HTMLDivElement>(null)
  const readyRef = useRef(false)
  const exitingRef = useRef(false)

  const finishSplash = useCallback(async () => {
    api.markSplashScreenShown().catch(() => {})
    await wait(150)
    onComplete()
  }, [onComplete])

  useLayoutEffect(() => {
    const root = rootRef.current
    if (!root) return

    readyRef.current = false
    exitingRef.current = false

    CustomEase.create('rua-hop', '0.9, 0, 0.1, 1')
    CustomEase.create('rua-glide', '0.8, 0, 0.2, 1')

    const splitInstances: Array<{ revert: () => void }> = []
    const fallbackTimer = window.setTimeout(() => {
      if (!exitingRef.current) {
        exitingRef.current = true
        finishSplash()
      }
    }, 90000)

    const ctx = gsap.context(() => {
      const q = gsap.utils.selector(root)
      const preloaderTexts = q('.rua-preloader p') as HTMLElement[]
      const btnOutlineTrack = q('.rua-stroke-track')[0] as unknown as SVGCircleElement | undefined
      const btnOutlineProgress = q('.rua-stroke-progress')[0] as unknown as SVGCircleElement | undefined

      if (!btnOutlineTrack || !btnOutlineProgress) return

      const svgPathLength = btnOutlineTrack.getTotalLength()

      gsap.set([btnOutlineTrack, btnOutlineProgress], {
        strokeDasharray: svgPathLength,
        strokeDashoffset: svgPathLength,
      })

      preloaderTexts.forEach((paragraph) => {
        splitInstances.push(new SplitText(paragraph, {
          type: 'lines',
          linesClass: 'line',
          mask: 'lines',
        }))
      })

      splitInstances.push(new SplitText(q('.rua-hero h1')[0], {
        type: 'words',
        wordsClass: 'word',
        mask: 'words',
      }))

      const introTl = gsap.timeline({ delay: 0.8 })

      introTl
        .to('.rua-preloader .rua-p-row p .line', {
          y: '0%',
          duration: 0.75,
          ease: 'power3.out',
          stagger: 0.1,
        })
        .to(
          btnOutlineTrack,
          {
            strokeDashoffset: 0,
            duration: 2,
            ease: 'rua-hop',
          },
          '<',
        )
        .to(
          '.rua-pbc-svg-strokes svg',
          {
            rotation: 270,
            duration: 2,
            ease: 'rua-hop',
          },
          '<',
        )

      const progressStops = [0.2, 0.25, 0.85, 1].map((base, index) => {
        if (index === 3) return 1
        return base + (Math.random() - 0.5) * 0.1
      })

      progressStops.forEach((stop, index) => {
        introTl.to(btnOutlineProgress, {
          strokeDashoffset: svgPathLength - svgPathLength * stop,
          duration: 0.75,
          ease: 'rua-glide',
          delay: index === 0 ? 0.3 : 0.3 + Math.random() * 0.2,
        })
      })

      introTl
        .to(
          '.rua-pbc-logo',
          {
            opacity: 0,
            duration: 0.35,
            ease: 'power1.out',
          },
          '-=0.25',
        )
        .to(
          '.rua-preloader-btn-container',
          {
            scale: 0.9,
            duration: 1.5,
            ease: 'rua-hop',
          },
          '-=0.5',
        )
        .to(
          '.rua-pbc-label .line',
          {
            y: '0%',
            duration: 0.75,
            ease: 'power3.out',
            onComplete: () => {
              readyRef.current = true
              root.classList.add('is-ready')
            },
          },
          '-=0.75',
        )
    }, root)

    return () => {
      window.clearTimeout(fallbackTimer)
      root.classList.remove('is-ready')
      ctx.revert()
      splitInstances.forEach(instance => instance.revert())
    }
  }, [finishSplash])

  const handleEnter = useCallback(() => {
    const root = rootRef.current
    if (!root || !readyRef.current || exitingRef.current) return

    exitingRef.current = true
    readyRef.current = false

    const q = gsap.utils.selector(root)
    const btnOutlineTrack = q('.rua-stroke-track')[0] as unknown as SVGCircleElement | undefined
    const btnOutlineProgress = q('.rua-stroke-progress')[0] as unknown as SVGCircleElement | undefined

    if (!btnOutlineTrack || !btnOutlineProgress) {
      finishSplash()
      return
    }

    const svgPathLength = btnOutlineTrack.getTotalLength()

    gsap.timeline()
      .to('.rua-preloader', {
        scale: 0.75,
        duration: 1.25,
        ease: 'rua-hop',
      })
      .to(
        [btnOutlineTrack, btnOutlineProgress],
        {
          strokeDashoffset: -svgPathLength,
          duration: 1.25,
          ease: 'rua-hop',
        },
        '<',
      )
      .to(
        '.rua-pbc-label .line',
        {
          y: '-100%',
          duration: 0.75,
          ease: 'power3.out',
        },
        '-=1.25',
      )
      .to(
        '.rua-pbc-outro-label .line',
        {
          y: '0%',
          duration: 0.75,
          ease: 'power3.out',
        },
        '-=0.75',
      )
      .to('.rua-preloader', {
        clipPath: 'polygon(0% 0%, 0% 0%, 0% 100%, 0% 100%)',
        duration: 1.5,
        ease: 'rua-hop',
      })
      .to(
        '.rua-preloader-revealer',
        {
          clipPath: 'polygon(0% 0%, 0% 0%, 0% 100%, 0% 100%)',
          duration: 1.5,
          ease: 'rua-hop',
          onComplete: () => {
            gsap.set('.rua-preloader', { display: 'none' })
          },
        },
        '-=1.45',
      )
      .to('.rua-hero', {
        scale: 1,
        duration: 1.25,
        ease: 'rua-hop',
      })
      .to(
        '.rua-hero h1 .word',
        {
          y: '0%',
          duration: 1,
          ease: 'rua-glide',
          stagger: 0.05,
        },
        '-=1.75',
      )
      .call(() => {
        finishSplash()
      }, undefined, '+=1.4')
  }, [finishSplash])

  return (
    <div ref={rootRef} className="rua-splash" aria-label="RuaBot startup splash">
      <div className="rua-preloader-backdrop">
        <div className="rua-pb-row">
          <div className="rua-pb-col">
            <p>RUA//NEXT Control Mesh</p>
            <p>RUA//NEXT Control Mesh</p>
            <p>RUA//NEXT Control Mesh</p>
            <p>RUA//NEXT Control Mesh</p>
            <p>RUA//NEXT Control Mesh</p>
          </div>
          <div className="rua-pb-col">
            <p>OneBot / Event Runtime</p>
          </div>
          <div className="rua-pb-col">
            <p>0.392 02SD 008923</p>
          </div>
          <div className="rua-pb-col">
            <p>Material / Plugin Fiber</p>
          </div>
          <div className="rua-pb-col">
            <p>Status / Soft Resonance</p>
          </div>
          <div className="rua-pb-col">
            <img className="rua-pb-logo" src="/splash/logo-dark.png" alt="RuaBot logo" />
            <p>::.:::.:.:::.:::</p>
          </div>
        </div>

        <div className="rua-pb-row">
          <div className="rua-pb-col">
            <p>Runtime Memory</p>
          </div>
          <div className="rua-pb-col">
            <p>/// Event / Bot / AI / Plugin ///</p>
          </div>
          <div className="rua-pb-col">
            <p>Boot Offset &gt; 17%</p>
          </div>
          <div className="rua-pb-col">
            <p>Kernel Waking</p>
            <p>Adapters Aligning</p>
          </div>
          <div className="rua-pb-col">
            <p>Dashboard Pending</p>
            <p>Return -- Layer Zero</p>
          </div>
          <div className="rua-pb-col">
            <p>V-Next</p>
          </div>
        </div>
      </div>

      <div className="rua-preloader">
        <div className="rua-p-row">
          <p>Launching</p>
        </div>
        <div className="rua-p-row">
          <div className="rua-p-col">
            <div className="rua-p-sub-col">
              <p>Phase 01</p>
              <p>WebUI Sequence</p>
            </div>
            <div className="rua-p-sub-col">
              <p>Signal Scan</p>
              <p>07 Layers</p>
            </div>
          </div>
          <div className="rua-p-col">
            <p>RUA-NEXT</p>
          </div>
        </div>

        <button
          className="rua-preloader-btn-container"
          type="button"
          onClick={handleEnter}
          aria-label="Enter RuaBot WebUI"
        >
          <span className="rua-pbc-logo" aria-hidden="true">R</span>
          <p className="rua-pbc-label">Enter Console</p>
          <p className="rua-pbc-outro-label">Access Granted</p>

          <div className="rua-pbc-svg-strokes" aria-hidden="true">
            <svg fill="none" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 320">
              <circle
                className="rua-stroke-track"
                cx="160"
                cy="160"
                r="155"
                stroke="#2b2b2b"
                strokeWidth="2"
              />
              <circle
                className="rua-stroke-progress"
                cx="160"
                cy="160"
                r="155"
                stroke="#fff"
                strokeWidth="2"
              />
            </svg>
          </div>
        </button>
      </div>

      <section className="rua-hero">
        <div className="rua-preloader-revealer" />
        <div className="rua-hero-copy">
          <p>Welcome back to Xiaoyi WebUI</p>
          <h1>RuaBot Console Online</h1>
        </div>
      </section>

      <style>{`
        @import url("https://fonts.googleapis.com/css2?family=Barlow+Condensed:ital,wght@0,100;0,200;0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,100;1,200;1,300;1,400;1,500;1,600;1,700;1,800;1,900&family=Geist+Mono:wght@100..900&display=swap");

        .rua-splash {
          --base-100: #fff;
          --base-200: #7a7a7a;
          --base-300: #000;
          position: fixed;
          inset: 0;
          z-index: 9999;
          overflow: hidden;
          background: var(--base-300);
        }

        .rua-splash,
        .rua-splash * {
          box-sizing: border-box;
        }

        .rua-splash h1,
        .rua-splash p,
        .rua-splash button {
          margin: 0;
          padding: 0;
        }

        .rua-splash h1 {
          text-transform: uppercase;
          font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
          font-size: clamp(5rem, 15vw, 15rem);
          font-weight: 800;
          letter-spacing: -0.02em;
          line-height: 0.8;
        }

        .rua-splash p {
          text-transform: uppercase;
          font-family: "Geist Mono", "Courier New", monospace;
          font-size: 0.75rem;
          font-weight: 500;
          line-height: 1;
        }

        .rua-splash h1 .word,
        .rua-splash p .line {
          position: relative;
          transform: translateY(100%);
          will-change: transform;
        }

        .rua-preloader-backdrop {
          position: fixed;
          inset: 0;
          width: 100%;
          height: 100svh;
          background-color: var(--base-100);
          color: var(--base-200);
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          z-index: 0;
        }

        .rua-pb-row,
        .rua-p-row {
          width: 100%;
          padding: 1.5rem;
          display: flex;
          justify-content: space-between;
        }

        .rua-pb-row:nth-child(2) {
          align-items: flex-end;
        }

        .rua-pb-logo {
          width: 2.5rem;
          height: 2.5rem;
          padding: 0.25rem;
          border: 1px dashed var(--base-200);
        }

        .rua-preloader {
          position: fixed;
          inset: 0;
          width: 100%;
          height: 100svh;
          background-color: var(--base-300);
          color: var(--base-100);
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          clip-path: polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%);
          transform-origin: center;
          will-change: transform, clip-path;
          z-index: 2;
        }

        .rua-p-row .rua-p-col {
          display: flex;
          gap: 6rem;
          align-items: flex-end;
        }

        .rua-preloader-btn-container {
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          width: min(20rem, 72vw);
          height: min(20rem, 72vw);
          border: 0;
          border-radius: 999px;
          background: transparent;
          color: var(--base-100);
          cursor: wait;
          opacity: 0.86;
          transition: opacity 240ms ease, filter 240ms ease;
        }

        .rua-splash.is-ready .rua-preloader-btn-container {
          cursor: pointer;
          opacity: 1;
          filter: drop-shadow(0 0 1.75rem rgba(255, 255, 255, 0.16));
        }

        .rua-pbc-svg-strokes,
        .rua-pbc-logo,
        .rua-pbc-label,
        .rua-pbc-outro-label {
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
        }

        .rua-pbc-logo {
          display: grid;
          width: 4rem;
          height: 4rem;
          place-items: center;
          font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
          font-size: 4.5rem;
          font-weight: 800;
          line-height: 0.8;
          letter-spacing: -0.08em;
          text-indent: -0.08em;
          color: var(--base-100);
          pointer-events: none;
        }

        .rua-pbc-label,
        .rua-pbc-outro-label {
          font-size: 0.9rem;
          white-space: nowrap;
          pointer-events: none;
        }

        .rua-pbc-svg-strokes,
        .rua-pbc-svg-strokes svg {
          width: 100%;
          height: 100%;
          will-change: transform;
        }

        .rua-pbc-svg-strokes {
          pointer-events: none;
        }

        .rua-hero {
          position: relative;
          width: 100%;
          height: 100svh;
          padding: 1.5rem;
          background-color: var(--base-300);
          color: var(--base-100);
          display: flex;
          justify-content: center;
          align-items: center;
          text-align: center;
          transform: scale(0.75);
          will-change: transform;
          z-index: 1;
        }

        .rua-hero-copy {
          position: relative;
          z-index: 1;
          display: grid;
          gap: 1rem;
          justify-items: center;
          width: 92%;
        }

        .rua-hero-copy p {
          color: rgba(255, 255, 255, 0.58);
          letter-spacing: 0.16em;
        }

        .rua-hero h1 {
          width: min(90%, 80rem);
        }

        .rua-preloader-revealer {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background-color: var(--base-100);
          clip-path: polygon(0% 0%, 100% 0%, 100% 100%, 0% 100%);
          will-change: clip-path;
        }

        @media (max-width: 1000px) {
          .rua-pb-row .rua-pb-col:nth-child(1),
          .rua-pb-row .rua-pb-col:nth-child(2),
          .rua-pb-row .rua-pb-col:nth-child(5) {
            display: none;
          }

          .rua-p-row .rua-p-col {
            gap: 2.5rem;
          }
        }

        @media (max-width: 640px) {
          .rua-pb-row,
          .rua-p-row,
          .rua-hero {
            padding: 1rem;
          }

          .rua-p-row .rua-p-col {
            gap: 1.5rem;
          }

          .rua-p-row:nth-child(2) {
            align-items: flex-end;
          }

          .rua-p-sub-col:nth-child(2),
          .rua-p-row:nth-child(2) > .rua-p-col:nth-child(2) {
            display: none;
          }
        }
      `}</style>
    </div>
  )
}
