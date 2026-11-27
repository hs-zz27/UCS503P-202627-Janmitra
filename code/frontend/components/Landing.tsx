'use client';

import { ChevronDown, Phone } from 'lucide-react';
import { useEffect, useRef, type CSSProperties } from 'react';

import { boxAround, chipCentre, chipHidden, RINGS, storyFrame, type Box, type Geometry } from '@/lib/landing-story';

export default function Landing() {
  const storyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const story = storyRef.current;
    if (!story) return;
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
    const root = getComputedStyle(document.documentElement);
    const num = (name: string) => parseFloat(root.getPropertyValue(name));
    // Read from landing.css so the stylesheet stays the single source of the geometry.
    const geometry: Geometry = { r0: num('--r0'), band: num('--band'), gap: num('--gap'), cy: num('--cy') / 100 };
    let frame = 0;

    // Hide any scheme name that would be cut by the viewport edge or sit on the wordmark or action.
    const placeChips = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      const pad = 12;
      const obstacles: Box[] = [];
      const foot = story.querySelector<HTMLElement>('.hero-foot');
      if (foot) {
        obstacles.push(boxAround(w / 2, foot.offsetTop + foot.offsetHeight / 2, foot.offsetWidth / 2, foot.offsetHeight / 2, pad));
      }
      const mark = story.querySelector<HTMLElement>('.hero-mark');
      if (mark) obstacles.push(boxAround(w / 2, h * geometry.cy, mark.offsetWidth / 2, mark.offsetHeight / 2, pad));
      story.querySelectorAll<HTMLElement>('.ring-chip').forEach((chip) => {
        const angle = parseFloat(getComputedStyle(chip).getPropertyValue('--a'));
        const { x, y } = chipCentre(angle, Number(chip.dataset.ring), w, h, geometry);
        const box = boxAround(x, y, chip.offsetWidth / 2, chip.offsetHeight / 2);
        chip.toggleAttribute('data-clipped', chipHidden(box, w, h, obstacles));
      });
    };

    const update = () => {
      frame = 0;
      const h = window.innerHeight;
      const travel = story.offsetHeight - h;
      const p = travel > 0 ? Math.min(1, Math.max(0, -story.getBoundingClientRect().top / travel)) : 0;
      const f = storyFrame(p, window.innerWidth, h, geometry);
      const set = (name: string, value: number) => story.style.setProperty(name, value.toFixed(4));

      f.ringScales.forEach((scale, i) => set(`--ring-s-${i + 1}`, scale));
      set('--rings-o', f.ringsOpacity);
      set('--ring1-o', f.ring1Opacity);
      set('--names1-o', f.ring1NamesOpacity);
      set('--disc-s', f.discScale);
      set('--disc-o', f.discOpacity);
      set('--hero-o', f.heroOpacity);
      set('--hero-s', f.heroScale);
      story.toggleAttribute('data-hero-gone', f.heroGone);
      f.beats.forEach((beat, i) => {
        set(`--b${i + 1}-o`, beat.opacity);
        set(`--b${i + 1}-y`, beat.offset);
        set(`--b${i + 1}-blur`, beat.blur);
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
