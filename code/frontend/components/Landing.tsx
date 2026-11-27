'use client';

import { ChevronDown, Phone } from 'lucide-react';
import { useEffect, useRef, type CSSProperties } from 'react';

/*
 * The five rings are the published catalogue: one ring per scheme category,
 * inner to outer, each carrying its schemes. Every scheme has a fixed angle
 * (0deg = top, clockwise) for landscape (l) and portrait (p) screens. The angles
 * were solved against measured name sizes so every name stays inside the
 * viewport, at least 12px from every other name, the wordmark and the hero action, on
 * phones from 360x740 to 430x932 and screens from 1024x768 to 1440x900.
 */
const RINGS = [
  {
    category: 'Pensions',
    schemes: [{ name: 'Atal Pension', l: 300, p: 190 }, { name: 'NSAP', l: 60, p: 20 }, { name: 'PM-SYM', l: 180, p: 135 }],
  },
  {
    category: 'Insurance',
    schemes: [
      { name: 'Ayushman Bharat', l: 20, p: 310 }, { name: 'Fasal Bima', l: 105, p: 60 },
      { name: 'Jeevan Jyoti', l: 235, p: 5 }, { name: 'Suraksha Bima', l: 300, p: 240 },
    ],
  },
  {
    category: 'Loans',
    schemes: [
      { name: 'Kisan Credit Card', l: 40, p: 140 }, { name: 'MUDRA', l: 125, p: 330 },
      { name: 'PMEGP', l: 235, p: 45 }, { name: 'PM Vishwakarma', l: 320, p: 215 },
    ],
  },
  {
    category: 'Grants',
    schemes: [
      { name: 'PM-KISAN', l: 55, p: 350 }, { name: 'Awaas Gramin', l: 115, p: 155 },
      { name: 'Anna Yojana', l: 245, p: 30 }, { name: 'Ujjwala', l: 305, p: 200 },
    ],
  },
  {
    category: 'Banking and rural employment',
    schemes: [{ name: 'Jan Dhan', l: 55, p: 175 }, { name: 'Aajeevika', l: 125, p: 330 }, { name: 'VB-G RAM G', l: 135, p: 15 }],
  },
] as const;

/* Scroll windows for the three statements: fade in from a to b, out from c to d. */
const BEATS: ReadonlyArray<readonly [number, number, number, number]> = [
  [0.22, 0.3, 0.46, 0.53],
  [0.53, 0.61, 0.72, 0.79],
  [0.79, 0.87, 2, 2],
];

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
const ramp = (p: number, a: number, b: number) => clamp01((p - a) / (b - a));
const easeOut = (t: number) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t));

export default function Landing() {
  const storyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const story = storyRef.current;
    if (!story) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
    const root = getComputedStyle(document.documentElement);
    const num = (name: string) => parseFloat(root.getPropertyValue(name));
    const r0 = num('--r0');
    const band = num('--band');
    const gap = num('--gap');
    const cyRatio = num('--cy') / 100;
    let frame = 0;

    // Hide any scheme name that would be cut by the viewport edge or sit on the wordmark or action.
    const placeChips = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      const vmin = Math.min(w, h) / 100;
      const cx = w / 2;
      const cy = h * cyRatio;
      const foot = story.querySelector<HTMLElement>('.hero-foot');
      const pad = 12;
      const fx0 = cx - (foot?.offsetWidth ?? 0) / 2 - pad;
      const fx1 = cx + (foot?.offsetWidth ?? 0) / 2 + pad;
      const fy0 = (foot?.offsetTop ?? h) - pad;
      const fy1 = (foot?.offsetTop ?? h) + (foot?.offsetHeight ?? 0) + pad;
      const mark = story.querySelector<HTMLElement>('.hero-mark');
      const mw = (mark?.offsetWidth ?? 0) / 2 + pad;
      const mh = (mark?.offsetHeight ?? 0) / 2 + pad;
      story.querySelectorAll<HTMLElement>('.ring-chip').forEach((chip) => {
        const k = Number(chip.dataset.ring);
        const r = (r0 + gap + k * (band + gap) + band / 2) * vmin;
        const a = (parseFloat(getComputedStyle(chip).getPropertyValue('--a')) * Math.PI) / 180;
        const x = cx + Math.sin(a) * r;
        const y = cy - Math.cos(a) * r;
        const hw = chip.offsetWidth / 2;
        const hh = chip.offsetHeight / 2;
        const outside = x - hw < 8 || x + hw > w - 8 || y - hh < 8 || y + hh > h - 8;
        const underAction = x + hw > fx0 && x - hw < fx1 && y + hh > fy0 && y - hh < fy1;
        const onMark = x + hw > cx - mw && x - hw < cx + mw && y + hh > cy - mh && y - hh < cy + mh;
        chip.toggleAttribute('data-clipped', outside || underAction || onMark);
      });
    };

    const update = () => {
      frame = 0;
      const w = window.innerWidth;
      const h = window.innerHeight;
      const travel = story.offsetHeight - h;
      const p = travel > 0 ? clamp01(-story.getBoundingClientRect().top / travel) : 0;
      const set = (name: string, value: number) => story.style.setProperty(name, value.toFixed(4));

      // The flight into the rings: exponential scale reads as constant speed.
      // Outer rings are nearer the viewer, so they open faster, as in a tunnel.
      const fly = ramp(p, 0.02, 0.32);
      for (let i = 2; i <= RINGS.length; i += 1) set(`--ring-s-${i}`, Math.exp(fly * (1.85 + 0.28 * i)));
      set('--rings-o', 1 - ramp(p, 0.24, 0.34));
      set('--disc-s', Math.exp(fly * 1.75));
      set('--disc-o', 1 - ramp(p, 0.08, 0.2));

      // The innermost ring stops just short of the far corners and stays,
      // so the statements rise inside it.
      const vmin = Math.min(w, h) / 100;
      const cy = h * cyRatio;
      const corner = Math.hypot(w / 2, Math.max(cy, h - cy));
      const linger = (0.9 * corner) / ((r0 + gap) * vmin);
      set('--ring-s-1', Math.min(Math.exp(fly * 2.13), linger));
      set('--ring1-o', 1 - 0.3 * ramp(p, 0.2, 0.3));
      // Its names leave before the rim settles, so no pill is cut by the frame edge.
      set('--names1-o', 1 - ramp(p, 0.1, 0.18));

      const hero = ramp(p, 0.02, 0.12);
      set('--hero-o', 1 - hero);
      set('--hero-s', 1 + hero * 0.35);
      story.toggleAttribute('data-hero-gone', hero > 0.98);

      BEATS.forEach(([a, b, c, d], i) => {
        const enter = easeOut(ramp(p, a, b));
        const leave = ramp(p, c, d);
        set(`--b${i + 1}-o`, enter * (1 - leave));
        set(`--b${i + 1}-y`, (1 - enter) * 2.5 - leave * 2);
        set(`--b${i + 1}-blur`, (1 - enter) * 10 + leave * 6);
      });
    };

    const schedule = () => { if (!frame) frame = requestAnimationFrame(update); };
    const onResize = () => { placeChips(); schedule(); };

    const apply = () => {
      if (reduce.matches) {
        story.classList.remove('is-live');
        window.removeEventListener('scroll', schedule);
        return;
      }
      story.classList.add('is-live');
      window.addEventListener('scroll', schedule, { passive: true });
      update();
    };

    apply();
    placeChips();
    document.fonts?.ready.then(placeChips);
    window.addEventListener('resize', onResize);
    reduce.addEventListener('change', apply);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', onResize);
      reduce.removeEventListener('change', apply);
    };
  }, []);

  return (
    <div className="story" ref={storyRef}>
      <div className="story-stage">
        <div className="rings" aria-hidden="true">
          {/* Bands first, then every ring's names in a layer above all bands,
              so a name that spills past its own band is never covered. */}
          {RINGS.map((ring, i) => (
            <div className={`ring-zoom ring-zoom-${i + 1}`} key={ring.category}>
              <div className={`ring ring-${i + 1}`} />
            </div>
          ))}
          <div className="ring-disc" />
          {RINGS.map((ring, i) => (
            <div className={`ring-zoom ring-names ring-zoom-${i + 1}`} key={`${ring.category}-names`}>
              {ring.schemes.map((scheme) => (
                <span
                  className="ring-chip"
                  data-ring={i}
                  key={scheme.name}
                  style={{ '--a-l': `${scheme.l}deg`, '--a-p': `${scheme.p}deg` } as CSSProperties}
                >
                  {scheme.name}
                </span>
              ))}
            </div>
          ))}
        </div>

        <header className="hero">
          <div className="hero-mark">
            <h1 className="wordmark">Janmitra</h1>
            <p className="tagline">Government help, in your own words.</p>
          </div>
          <div className="hero-foot">
            <a className="hero-action" href="#call">
              <Phone aria-hidden="true" />
              Talk to Janmitra
            </a>
            <span className="hero-cue" aria-hidden="true">
              Scroll
              <ChevronDown />
            </span>
          </div>
        </header>

        <div className="beats">
          <p className="beat beat-1">
            A crop fails. The work dries up. Someone falls ill.{' '}
            <em className="beat-mark beat-mark-1">The help already exists</em>, written into a government scheme.
          </p>
          <p className="beat beat-2">
            But it is buried in long documents and formal language, on websites made for people who{' '}
            <em className="beat-mark beat-mark-2">already know what to search for</em>.
          </p>
          <div className="beat beat-3">
            <p>
              Janmitra listens. Describe your situation{' '}
              <em className="beat-mark beat-mark-3">in your own words</em>, and hear which schemes may help
              and what to do next.
            </p>
            <p className="beat-langs">
              Tested in <span lang="en">English</span>, <span lang="hi">हिन्दी</span> and{' '}
              <span lang="pa">ਪੰਜਾਬੀ</span>.
            </p>
          </div>
        </div>
      </div>

      <div className="visually-hidden">
        <h2>Schemes Janmitra can explain</h2>
        <ul>
          {RINGS.map((ring) => (
            <li key={ring.category}>
              {ring.category}: {ring.schemes.map((scheme) => scheme.name).join(', ')}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
