import { readdirSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
  BEATS, FLIGHT, GEOMETRY, RINGS, boxAround, chipCentre, chipHidden, ring1Cap, storyFrame,
} from '../lib/landing-story';

const CATALOGUE = new URL('../../backend/data/', import.meta.url);
const CSS = readFileSync(new URL('../app/landing.css', import.meta.url), 'utf8');

// Phones in portrait through ultra-wide monitors, including square and 4:3 shapes.
const VIEWPORTS: ReadonlyArray<readonly [number, number]> = [
  [360, 740], [390, 844], [430, 932], [768, 1024], [1000, 1000],
  [1024, 768], [1280, 720], [1440, 900], [1920, 1080], [2560, 1080],
];
const PROGRESS = Array.from({ length: 1001 }, (_, i) => i / 1000);
const schemes = RINGS.flatMap((ring) => [...ring.schemes]);

const vminOf = (w: number, h: number) => Math.min(w, h) / 100;
const cornerOf = (w: number, h: number) => {
  const cy = h * GEOMETRY.cy;
  return Math.hypot(w / 2, Math.max(cy, h - cy));
};
/** Inner radius in px of ring index k (0 = innermost) at the given scale. */
const innerRadius = (k: number, scale: number, w: number, h: number) =>
  (GEOMETRY.r0 + GEOMETRY.gap + k * (GEOMETRY.band + GEOMETRY.gap)) * vminOf(w, h) * scale;

describe('landing rings carry the published catalogue', () => {
  const records = readdirSync(CATALOGUE)
    .filter((file) => file.endsWith('.json'))
    .map((file) => JSON.parse(readFileSync(new URL(file, CATALOGUE), 'utf8')) as { slug: string; category: string });

  it('shows every published scheme exactly once', () => {
    const onRings = schemes.map((scheme) => scheme.slug).sort();
    expect(onRings).toEqual(records.map((record) => record.slug).sort());
    expect(new Set(onRings).size).toBe(onRings.length);
  });

  it('puts each scheme on the ring for its catalogue category', () => {
    const categoryOf = new Map(records.map((record) => [record.slug, record.category]));
    for (const ring of RINGS) {
      for (const scheme of ring.schemes) {
        expect(ring.catalogue as readonly string[]).toContain(categoryOf.get(scheme.slug));
      }
    }
  });

  it('gives every scheme a landscape and a portrait angle', () => {
    for (const scheme of schemes) {
      for (const angle of [scheme.l, scheme.p]) {
        expect(angle).toBeGreaterThanOrEqual(0);
        expect(angle).toBeLessThan(360);
      }
    }
  });

  it('uses the same ring geometry as landing.css', () => {
    const read = (name: string) => Number(CSS.match(new RegExp(`${name}:\\s*([\\d.]+)`))?.[1]);
    expect(read('--r0')).toBe(GEOMETRY.r0);
    expect(read('--band')).toBe(GEOMETRY.band);
    expect(read('--gap')).toBe(GEOMETRY.gap);
    expect(read('--cy') / 100).toBe(GEOMETRY.cy);
  });
});

describe('landing scroll timeline', () => {
  it('opens on the hero with the rings at rest and no statement showing', () => {
    const frame = storyFrame(0, 1440, 900);
    expect(frame.heroOpacity).toBe(1);
    expect(frame.heroGone).toBe(false);
    expect(frame.discOpacity).toBe(1);
    expect(frame.ringScales).toEqual([1, 1, 1, 1, 1]);
    expect(frame.ring1NamesOpacity).toBe(1);
    for (const beat of frame.beats) expect(beat.opacity).toBe(0);
  });

  it('shows the statements one at a time, each in full, and keeps the last', () => {
    const peak = BEATS.map(() => 0);
    for (const p of PROGRESS) {
      const beats = storyFrame(p, 1440, 900).beats;
      expect(beats.reduce((sum, beat) => sum + beat.opacity, 0)).toBeLessThanOrEqual(1 + 1e-9);
      beats.forEach((beat, i) => { peak[i] = Math.max(peak[i], beat.opacity); });
    }
    for (const value of peak) expect(value).toBeGreaterThan(0.99);
    expect(storyFrame(1, 1440, 900).beats.at(-1)?.opacity).toBe(1);
  });

  it('clears the hero and the centre disc before the first statement appears', () => {
    for (const p of PROGRESS) {
      const frame = storyFrame(p, 1440, 900);
      if (frame.beats[0].opacity > 0) {
        expect(frame.heroOpacity).toBe(0);
        expect(frame.heroGone).toBe(true);
        expect(frame.discOpacity).toBe(0);
      }
    }
  });

  it('flies the outer rings faster than the inner ones, as in a tunnel', () => {
    for (const p of PROGRESS.filter((value) => value > FLIGHT[0] && value <= FLIGHT[1])) {
      const scales = storyFrame(p, 1440, 900).ringScales;
      for (let k = 0; k < scales.length - 1; k += 1) expect(scales[k + 1]).toBeGreaterThan(scales[k]);
    }
  });

  it('has the outer rings past every corner whenever a statement is legible', () => {
    for (const [w, h] of VIEWPORTS) {
      for (const p of PROGRESS) {
        const frame = storyFrame(p, w, h);
        if (!frame.beats.some((beat) => beat.opacity > 0.5)) continue;
        for (let k = 1; k < frame.ringScales.length; k += 1) {
          expect(innerRadius(k, frame.ringScales[k], w, h)).toBeGreaterThan(cornerOf(w, h));
        }
      }
    }
  });

  it('holds the violet ring at the frame corners through the statements', () => {
    for (const [w, h] of VIEWPORTS) {
      for (const p of PROGRESS.filter((value) => value >= FLIGHT[1])) {
        const frame = storyFrame(p, w, h);
        expect(frame.ringScales[0]).toBeCloseTo(ring1Cap(w, h), 9);
        const edge = innerRadius(0, frame.ringScales[0], w, h);
        expect(edge).toBeLessThan(cornerOf(w, h));
        expect(edge).toBeGreaterThan(0.85 * cornerOf(w, h));
        expect(frame.ring1Opacity).toBeGreaterThanOrEqual(0.7);
      }
    }
  });

  // Regression: ring 1's names once stayed on screen at its capped scale and
  // were cut by the frame edge during every statement.
  it("clears ring 1's names before its band settles at the frame edge, on every shape", () => {
    for (const [w, h] of VIEWPORTS) {
      const cap = ring1Cap(w, h);
      for (const p of PROGRESS) {
        const frame = storyFrame(p, w, h);
        if (frame.ringScales[0] >= cap * 0.999) expect(frame.ring1NamesOpacity).toBe(0);
      }
    }
  });
});

describe('landing scheme-name placement', () => {
  it('places a name on the middle of its band, measured from the ring centre', () => {
    const [w, h] = [1440, 900];
    const vmin = vminOf(w, h);
    const r = (GEOMETRY.r0 + GEOMETRY.gap + GEOMETRY.band / 2) * vmin;
    const top = chipCentre(0, 0, w, h);
    expect(top.x).toBeCloseTo(w / 2, 9);
    expect(top.y).toBeCloseTo(h * GEOMETRY.cy - r, 9);
    const right = chipCentre(90, 0, w, h);
    expect(right.x).toBeCloseTo(w / 2 + r, 9);
    expect(right.y).toBeCloseTo(h * GEOMETRY.cy, 9);
  });

  it('hides a name that would be cut by the viewport edge', () => {
    expect(chipHidden(boxAround(200, 200, 40, 10), 1440, 900, [])).toBe(false);
    expect(chipHidden(boxAround(1430, 200, 40, 10), 1440, 900, [])).toBe(true);
    expect(chipHidden(boxAround(45, 200, 40, 10), 1440, 900, [])).toBe(true);
    expect(chipHidden(boxAround(200, 895, 40, 10), 1440, 900, [])).toBe(true);
  });

  it('hides a name that would sit on the wordmark or the action, and only then', () => {
    const action = boxAround(720, 790, 100, 25, 12);
    expect(chipHidden(boxAround(720, 760, 40, 10), 1440, 900, [action])).toBe(true);
    expect(chipHidden(boxAround(720, 600, 40, 10), 1440, 900, [action])).toBe(false);
    // Edges touching is clear; any overlap is not.
    expect(chipHidden(boxAround(720, action.y0 - 10, 40, 10), 1440, 900, [action])).toBe(false);
    expect(chipHidden(boxAround(720, action.y0 - 9, 40, 10), 1440, 900, [action])).toBe(true);
  });
});
