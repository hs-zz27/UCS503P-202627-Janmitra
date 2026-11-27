/*
 * Pure logic behind the landing page's ring stage: the scheme catalogue the
 * rings carry, the scroll timeline that flies the viewer into them, and the
 * rule that hides a scheme name that would be cut or sit on something.
 * components/Landing.tsx applies these results to the DOM.
 */

/** Ring geometry. r0, band and gap are in vmin; cy is the ring centre as a fraction of viewport height. */
export type Geometry = { r0: number; band: number; gap: number; cy: number };

/** Must match the --r0, --band, --gap and --cy custom properties in app/landing.css. */
export const GEOMETRY: Geometry = { r0: 21, band: 6.4, gap: 4.2, cy: 0.45 };

/*
 * One ring per scheme category, inner to outer. `catalogue` lists the backend
 * catalogue categories the ring stands for; each scheme carries its catalogue
 * slug. Angles (0deg = top, clockwise) were solved against measured name sizes
 * so every name stays inside the viewport, at least 12px from every other
 * name, the wordmark and the hero action, on phones from 360x740 to 430x932
 * (portrait, p) and screens from 1024x768 to 1440x900 (landscape, l).
 */
export const RINGS = [
  {
    category: 'Pensions',
    catalogue: ['pension'],
    schemes: [
      { slug: 'apy', name: 'Atal Pension', l: 300, p: 190 },
      { slug: 'nsap', name: 'NSAP', l: 60, p: 20 },
      { slug: 'pm-sym', name: 'PM-SYM', l: 180, p: 135 },
    ],
  },
  {
    category: 'Insurance',
    catalogue: ['insurance'],
    schemes: [
      { slug: 'pm-jay', name: 'Ayushman Bharat', l: 20, p: 310 },
      { slug: 'pmfby', name: 'Fasal Bima', l: 105, p: 60 },
      { slug: 'pmjjby', name: 'Jeevan Jyoti', l: 235, p: 5 },
      { slug: 'pmsby', name: 'Suraksha Bima', l: 300, p: 240 },
    ],
  },
  {
    category: 'Loans',
    catalogue: ['loan'],
    schemes: [
      { slug: 'kcc', name: 'Kisan Credit Card', l: 40, p: 140 },
      { slug: 'pmmy', name: 'MUDRA', l: 125, p: 330 },
      { slug: 'pmegp', name: 'PMEGP', l: 235, p: 45 },
      { slug: 'pm-vishwakarma', name: 'PM Vishwakarma', l: 320, p: 215 },
    ],
  },
  {
    category: 'Grants',
    catalogue: ['grant'],
    schemes: [
      { slug: 'pm-kisan', name: 'PM-KISAN', l: 55, p: 350 },
      { slug: 'pmay-g', name: 'Awaas Gramin', l: 115, p: 155 },
      { slug: 'pmgkay', name: 'Anna Yojana', l: 245, p: 30 },
      { slug: 'pmuy', name: 'Ujjwala', l: 305, p: 200 },
    ],
  },
  {
    category: 'Banking and rural employment',
    catalogue: ['banking', 'other'],
    schemes: [
      { slug: 'pmjdy', name: 'Jan Dhan', l: 55, p: 175 },
      { slug: 'day-nrlm', name: 'Aajeevika', l: 125, p: 330 },
      { slug: 'mgnrega', name: 'VB-G RAM G', l: 135, p: 15 },
    ],
  },
] as const;

/** Scroll windows for the three statements: fade in from a to b, out from c to d. The last never leaves. */
export const BEATS: ReadonlyArray<readonly [number, number, number, number]> = [
  [0.22, 0.3, 0.46, 0.53],
  [0.53, 0.61, 0.72, 0.79],
  [0.79, 0.87, Infinity, Infinity],
];

/** Scroll progress over which the viewer flies into the rings. */
export const FLIGHT: readonly [number, number] = [0.02, 0.32];

export const clamp01 = (v: number) => Math.min(1, Math.max(0, v));

/** 0 before a, 1 after b, linear between. A window with no width is a step at a. */
export const ramp = (p: number, a: number, b: number) => (b > a ? clamp01((p - a) / (b - a)) : p >= a ? 1 : 0);

export const easeOut = (t: number) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t));

/** Exponential growth rate of each ring's scale during the flight; outer rings are nearer, so faster. */
export const ringRate = (ring: number) => (ring === 1 ? 2.13 : 1.85 + 0.28 * ring);

/**
 * The innermost ring stops when its inner edge reaches 0.9 of the distance to
 * the farthest viewport corner, so its band frames the corners and stays.
 */
export function ring1Cap(width: number, height: number, g: Geometry = GEOMETRY) {
  const vmin = Math.min(width, height) / 100;
  const cy = height * g.cy;
  const corner = Math.hypot(width / 2, Math.max(cy, height - cy));
  return (0.9 * corner) / ((g.r0 + g.gap) * vmin);
}

export type StoryFrame = {
  heroOpacity: number;
  heroScale: number;
  heroGone: boolean;
  discScale: number;
  discOpacity: number;
  /** Index 0 is ring 1, the innermost. */
  ringScales: number[];
  /** Opacity of rings 2 to 5 and their names. */
  ringsOpacity: number;
  ring1Opacity: number;
  ring1NamesOpacity: number;
  beats: { opacity: number; offset: number; blur: number }[];
};

/** Everything the ring stage shows at scroll progress p (0 to 1) on a width x height viewport. */
export function storyFrame(p: number, width: number, height: number, g: Geometry = GEOMETRY): StoryFrame {
  const fly = ramp(p, FLIGHT[0], FLIGHT[1]);
  const cap = ring1Cap(width, height, g);
  const ringScales = RINGS.map((_, i) => Math.exp(fly * ringRate(i + 1)));
  ringScales[0] = Math.min(ringScales[0], cap);

  // Ring 1's names leave on the ring's own progress toward its cap, not on a
  // fixed scroll position, so on any aspect ratio they are gone before the
  // band settles at the frame edge, where a pill would be cut.
  const toCap = Math.log(ringScales[0]) / Math.log(cap);
  const hero = ramp(p, 0.02, 0.12);

  return {
    heroOpacity: 1 - hero,
    heroScale: 1 + hero * 0.35,
    heroGone: hero > 0.98,
    discScale: Math.exp(fly * 1.75),
    discOpacity: 1 - ramp(p, 0.08, 0.2),
    ringScales,
    ringsOpacity: 1 - ramp(p, 0.24, 0.34),
    ring1Opacity: 1 - 0.3 * ramp(p, 0.2, 0.3),
    ring1NamesOpacity: 1 - ramp(toCap, 0.6, 0.9),
    beats: BEATS.map(([a, b, c, d]) => {
      const enter = easeOut(ramp(p, a, b));
      const leave = ramp(p, c, d);
      return { opacity: enter * (1 - leave), offset: (1 - enter) * 2.5 - leave * 2, blur: (1 - enter) * 10 + leave * 6 };
    }),
  };
}

/** Centre of a scheme name on its ring at rest. ring is 0 for the innermost. */
export function chipCentre(angleDeg: number, ring: number, width: number, height: number, g: Geometry = GEOMETRY) {
  const vmin = Math.min(width, height) / 100;
  const r = (g.r0 + g.gap + ring * (g.band + g.gap) + g.band / 2) * vmin;
  const a = (angleDeg * Math.PI) / 180;
  return { x: width / 2 + Math.sin(a) * r, y: height * g.cy - Math.cos(a) * r };
}

export type Box = { x0: number; y0: number; x1: number; y1: number };

/** A box of the given half-size centred on (x, y), grown by pad on every side. */
export const boxAround = (x: number, y: number, halfW: number, halfH: number, pad = 0): Box => ({
  x0: x - halfW - pad, y0: y - halfH - pad, x1: x + halfW + pad, y1: y + halfH + pad,
});

const overlaps = (a: Box, b: Box) => a.x1 > b.x0 && a.x0 < b.x1 && a.y1 > b.y0 && a.y0 < b.y1;

/** True when a name would be cut by the viewport (inset by edge) or would sit on an obstacle. */
export function chipHidden(chip: Box, width: number, height: number, obstacles: Box[], edge = 8) {
  const outside = chip.x0 < edge || chip.x1 > width - edge || chip.y0 < edge || chip.y1 > height - edge;
  return outside || obstacles.some((o) => overlaps(chip, o));
}
