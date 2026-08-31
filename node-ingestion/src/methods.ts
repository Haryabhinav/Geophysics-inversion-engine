/**
 * The Method registry (Node-side mirror).
 *
 * Single source of truth for which geophysical methods this deployment
 * supports — mirrors the Python side's `METHOD_REGISTRY`
 * (python-agent/app/agent/methods/registry.py). Grown one method at a time,
 * in lockstep with its Python registration, so a dataType is never valid on
 * one side and rejected on the other.
 *
 * `SIMULATORS` provides one synthetic "ground truth" generator per method
 * for the dashboard's `/simulate` endpoint. Only TDEM needs `agentMode`
 * awareness (empymod vs. bi-exponential, so the offline optimizer can
 * actually fit it); every other closed-form method (added in later batches)
 * uses one generator usable by both Gemini and the offline optimizer.
 */
import type { SensorPayload } from './types.js';

export const METHOD_IDS = [
  'TDEM',
  'GRAVITY_SPHERE',
  'MAGNETICS_DIPOLE',
  'GPR_REFLECTION',
  'SP_DIPOLE',
  'MOGI_SOURCE',
  'RADIOMETRIC',
  'SEISMIC_REFRACTION',
  'EARTHQUAKE_LOCATION',
  'ERT_WENNER',
  'MT_1D',
  'IP_COLE_COLE',
] as const;
export type MethodId = (typeof METHOD_IDS)[number];

export function isMethodId(value: string): value is MethodId {
  return (METHOD_IDS as readonly string[]).includes(value);
}

// A real empymod TDEM step-off transient over a 2-layer earth (air / 50 Ω·m
// overburden to 40 m / 200 Ω·m basement) — the kind of curve the Gemini agent
// inverts. Generated once with empymod (empymod.dipole, signal=-1).
const SIM_TIME = [
  1e-5, 1.333521e-5, 1.778279e-5, 2.371374e-5, 3.162278e-5, 4.216965e-5,
  5.623413e-5, 7.498942e-5, 1e-4, 1.333521e-4, 1.778279e-4, 2.371374e-4,
  3.162278e-4, 4.216965e-4, 5.623413e-4, 7.498942e-4, 1e-3, 1.333521e-3,
  1.778279e-3, 2.371374e-3, 3.162278e-3, 4.216965e-3, 5.623413e-3, 7.498942e-3, 1e-2,
];
const SIM_AMP = [
  1.130264e-5, 1.094813e-5, 1.012592e-5, 8.77939e-6, 7.095997e-6, 5.392272e-6,
  3.911728e-6, 2.725708e-6, 1.848747e-6, 1.227547e-6, 8.021937e-7, 5.188348e-7,
  3.334073e-7, 2.132082e-7, 1.361586e-7, 8.662659e-8, 5.520318e-8, 3.545849e-8,
  2.250741e-8, 1.454127e-8, 9.26825e-9, 5.94527e-9, 3.825482e-9, 2.458338e-9, 1.581909e-9,
];

/** The canonical empymod TDEM curve with a few corrupt samples (for the sanitizer). */
export function buildEmpymodTdem(): SensorPayload {
  const timeSteps: Array<number | null> = [...SIM_TIME];
  const amplitudes: Array<number | null> = [...SIM_AMP];
  const bad = 4;
  for (let k = 0; k < bad; k++) {
    const idx = (k * 6 + 3) % SIM_TIME.length;
    if (k % 2 === 0) amplitudes[idx] = null;
    else timeSteps[idx] = null;
  }
  return { sensorId: 'dashboard-sim', dataType: 'TDEM', timeSteps, amplitudes };
}

/**
 * A bi-exponential decay the OFFLINE Nelder-Mead modeler can fit (it emits
 * numpy-only code). Used when the agent runs offline so the dashboard converges
 * with no API key. Gemini can't invert this (it writes empymod), hence the
 * mode-aware selection below.
 */
export function buildBiexpTdem(): SensorPayload {
  const TRUTH = { a1: 10, tau1: 2e-3, a2: 2, tau2: 2e-2 };
  const n = 45;
  const bad = 5;
  const lo = Math.log10(1e-4);
  const hi = Math.log10(1e-1);
  const timeSteps: Array<number | null> = [];
  const amplitudes: Array<number | null> = [];
  for (let i = 0; i < n; i++) {
    const t = 10 ** (lo + (i * (hi - lo)) / (n - 1));
    timeSteps.push(t);
    amplitudes.push(TRUTH.a1 * Math.exp(-t / TRUTH.tau1) + TRUTH.a2 * Math.exp(-t / TRUTH.tau2));
  }
  for (let k = 0; k < bad; k++) {
    const idx = (k * 7 + 3) % n;
    if (k % 2 === 0) amplitudes[idx] = null;
    else timeSteps[idx] = null;
  }
  return { sensorId: 'dashboard-sim', dataType: 'TDEM', timeSteps, amplitudes };
}

/** Corrupts `bad` samples (alternating amplitude/x-value) at a spread of
 * indices — same pattern buildEmpymodTdem/buildBiexpTdem use, extracted so
 * every new method's truth-generator doesn't repeat the loop. */
function corrupt(
  xValues: Array<number | null>,
  dValues: Array<number | null>,
  bad: number,
  stride = 6,
): void {
  const n = xValues.length;
  for (let k = 0; k < bad; k++) {
    const idx = (k * stride + 3) % n;
    if (k % 2 === 0) dValues[idx] = null;
    else xValues[idx] = null;
  }
}

function buildGravitySphereTruth(): SensorPayload {
  const TRUTH = { K: 8000, z: 25, x0: 0 };
  const n = 41;
  const xValues: Array<number | null> = [];
  const dValues: Array<number | null> = [];
  for (let i = 0; i < n; i++) {
    const x = -100 + (i * 200) / (n - 1);
    xValues.push(x);
    dValues.push((TRUTH.K * TRUTH.z) / ((x - TRUTH.x0) ** 2 + TRUTH.z ** 2) ** 1.5);
  }
  corrupt(xValues, dValues, 4);
  return { sensorId: 'dashboard-sim', dataType: 'GRAVITY_SPHERE', timeSteps: xValues, amplitudes: dValues };
}

function buildMagneticsDipoleTruth(): SensorPayload {
  const TRUTH = { K: 50000, z: 20, x0: 0 };
  const n = 41;
  const xValues: Array<number | null> = [];
  const dValues: Array<number | null> = [];
  for (let i = 0; i < n; i++) {
    const x = -100 + (i * 200) / (n - 1);
    const dx = x - TRUTH.x0;
    xValues.push(x);
    dValues.push((TRUTH.K * (2 * TRUTH.z ** 2 - dx ** 2)) / (dx ** 2 + TRUTH.z ** 2) ** 2.5);
  }
  corrupt(xValues, dValues, 4);
  return { sensorId: 'dashboard-sim', dataType: 'MAGNETICS_DIPOLE', timeSteps: xValues, amplitudes: dValues };
}

function buildGprReflectionTruth(): SensorPayload {
  const TRUTH = { v: 0.1, d: 3.0 };
  const n = 25;
  const t0 = (2 * TRUTH.d) / TRUTH.v;
  const xValues: Array<number | null> = [];
  const dValues: Array<number | null> = [];
  for (let i = 0; i < n; i++) {
    const x = (i * 20) / (n - 1);
    xValues.push(x);
    dValues.push(Math.sqrt(t0 ** 2 + (x / TRUTH.v) ** 2));
  }
  corrupt(xValues, dValues, 3, 7);
  return { sensorId: 'dashboard-sim', dataType: 'GPR_REFLECTION', timeSteps: xValues, amplitudes: dValues };
}

function buildSpDipoleTruth(): SensorPayload {
  const TRUTH = { K: 500, z: 10, x0: 0, theta: 0.3 };
  const n = 31;
  const xValues: Array<number | null> = [];
  const dValues: Array<number | null> = [];
  for (let i = 0; i < n; i++) {
    const x = -60 + (i * 120) / (n - 1);
    const dx = x - TRUTH.x0;
    const num = TRUTH.z * Math.cos(TRUTH.theta) + dx * Math.sin(TRUTH.theta);
    xValues.push(x);
    dValues.push((TRUTH.K * num) / (dx ** 2 + TRUTH.z ** 2) ** 1.5);
  }
  corrupt(xValues, dValues, 4);
  return { sensorId: 'dashboard-sim', dataType: 'SP_DIPOLE', timeSteps: xValues, amplitudes: dValues };
}

function buildMogiSourceTruth(): SensorPayload {
  const TRUTH = { C: 1e5, d: 3000, x0: 0 };
  const n = 41;
  const xValues: Array<number | null> = [];
  const dValues: Array<number | null> = [];
  for (let i = 0; i < n; i++) {
    const x = -5000 + (i * 10000) / (n - 1);
    xValues.push(x);
    dValues.push((TRUTH.C * TRUTH.d) / ((x - TRUTH.x0) ** 2 + TRUTH.d ** 2) ** 1.5);
  }
  corrupt(xValues, dValues, 4);
  return { sensorId: 'dashboard-sim', dataType: 'MOGI_SOURCE', timeSteps: xValues, amplitudes: dValues };
}

// Fixed instrument calibration matching python-agent's radiometric.py exactly
// — window response to [K, U, Th], off-diagonal terms are Compton cross-talk.
const RADIOMETRIC_M = [
  [1.0, 0.15, 0.1],
  [0.05, 1.0, 0.3],
  [0.02, 0.1, 1.0],
];

function buildRadiometricTruth(): SensorPayload {
  const TRUTH = { K: 2.0, U: 3.0, Th: 10.0 }; // % , ppm, ppm
  const conc = [TRUTH.K, TRUTH.U, TRUTH.Th];
  const counts = RADIOMETRIC_M.map((row) => row.reduce((sum, coeff, j) => sum + coeff * conc[j]!, 0));
  // Only 3 real measurements exist (one per window) — none are corruptible.
  return {
    sensorId: 'dashboard-sim',
    dataType: 'RADIOMETRIC',
    timeSteps: [0, 1, 2],
    amplitudes: counts,
  };
}

function buildSeismicRefractionTruth(): SensorPayload {
  const TRUTH = { v1: 800, v2: 3000, h: 15 };
  const thetaC = Math.asin(TRUTH.v1 / TRUTH.v2);
  const n = 25;
  const xValues: Array<number | null> = [];
  const dValues: Array<number | null> = [];
  for (let i = 0; i < n; i++) {
    const x = 2 + (i * 98) / (n - 1);
    const tDirect = x / TRUTH.v1;
    const tHead = x / TRUTH.v2 + (2 * TRUTH.h * Math.cos(thetaC)) / TRUTH.v1;
    xValues.push(x);
    dValues.push(Math.min(tDirect, tHead));
  }
  corrupt(xValues, dValues, 3, 7);
  return { sensorId: 'dashboard-sim', dataType: 'SEISMIC_REFRACTION', timeSteps: xValues, amplitudes: dValues };
}

// 6 stations, matching python-agent's earthquake_location.py exactly.
const EQ_STATION_X = [500, 8000, 14000, 2000, 12000, 6000];
const EQ_STATION_Y = [1000, 500, 4000, 13000, 12000, 7000];
const EQ_STATION_Z = [0, 0, 0, 0, 0, 0];

function buildEarthquakeLocationTruth(): SensorPayload {
  const TRUTH = { srcX: 5000, srcY: 3000, srcZ: 8000, originT: 0.0, velocity: 6000 };
  const n = EQ_STATION_X.length;
  const stationIndex: number[] = [];
  const arrivalTimes: number[] = [];
  for (let i = 0; i < n; i++) {
    const dx = EQ_STATION_X[i]! - TRUTH.srcX;
    const dy = EQ_STATION_Y[i]! - TRUTH.srcY;
    const dz = EQ_STATION_Z[i]! - TRUTH.srcZ;
    const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
    stationIndex.push(i);
    arrivalTimes.push(TRUTH.originT + dist / TRUTH.velocity);
  }
  // 6 real station readings — none are corruptible (would break the aux
  // station-coordinate alignment).
  return {
    sensorId: 'dashboard-sim',
    dataType: 'EARTHQUAKE_LOCATION',
    timeSteps: stationIndex,
    amplitudes: arrivalTimes,
    auxData: { station_x: EQ_STATION_X, station_y: EQ_STATION_Y, station_z: EQ_STATION_Z },
  };
}

function wennerRhoA(a: number, rho1: number, rho2: number, h: number, nTerms = 60): number {
  const k = (rho2 - rho1) / (rho2 + rho1);
  let sum = 0;
  for (let n = 1; n <= nTerms; n++) {
    const ratio = (2 * n * h) / a;
    sum += k ** n * (1 / Math.sqrt(1 + ratio ** 2) - 1 / Math.sqrt(4 + ratio ** 2));
  }
  return rho1 * (1 + 4 * sum);
}

function buildErtWennerTruth(): SensorPayload {
  const TRUTH = { rho1: 50, rho2: 300, h: 20 };
  const n = 30;
  const lo = 1;
  const hi = Math.log10(250);
  const xValues: Array<number | null> = [];
  const dValues: Array<number | null> = [];
  for (let i = 0; i < n; i++) {
    const a = 10 ** (lo + (i * (hi - lo)) / (n - 1));
    xValues.push(a);
    dValues.push(wennerRhoA(a, TRUTH.rho1, TRUTH.rho2, TRUTH.h));
  }
  corrupt(xValues, dValues, 4);
  return { sensorId: 'dashboard-sim', dataType: 'ERT_WENNER', timeSteps: xValues, amplitudes: dValues };
}

// Minimal complex-number arithmetic (JS has no native complex type) for the
// MT recursive impedance — represented as [re, im] pairs, mirroring exactly
// the same formula as python-agent's mt_1d.py so the offline optimizer (run
// against whichever side generated the data) fits the same physics.
type Complex = [number, number];
const cMul = (a: Complex, b: Complex): Complex => [a[0] * b[0] - a[1] * b[1], a[0] * b[1] + a[1] * b[0]];
const cAdd = (a: Complex, b: Complex): Complex => [a[0] + b[0], a[1] + b[1]];
const cDiv = (a: Complex, b: Complex): Complex => {
  const denom = b[0] * b[0] + b[1] * b[1];
  return [(a[0] * b[0] + a[1] * b[1]) / denom, (a[1] * b[0] - a[0] * b[1]) / denom];
};
const cSqrt = (a: Complex): Complex => {
  const r = Math.hypot(a[0], a[1]);
  const re = Math.sqrt((r + a[0]) / 2);
  const im = (a[1] < 0 ? -1 : 1) * Math.sqrt(Math.max(r - a[0], 0) / 2);
  return [re, im];
};
const cTanh = (a: Complex): Complex => {
  const [x, y] = a;
  const denom = Math.cosh(2 * x) + Math.cos(2 * y);
  return [Math.sinh(2 * x) / denom, Math.sin(2 * y) / denom];
};
const cAbs2 = (a: Complex): number => a[0] * a[0] + a[1] * a[1];

function mt1dRhoA(f: number, rho1: number, rho2: number, h1: number): number {
  const mu0 = 4 * Math.PI * 1e-7;
  const omega = 2 * Math.PI * f;
  const k1 = cSqrt([0, (omega * mu0) / rho1]);
  const z1 = cSqrt([0, omega * mu0 * rho1]);
  const zHalf = cSqrt([0, omega * mu0 * rho2]);
  const ik1h1: Complex = cMul([0, 1], [k1[0] * h1, k1[1] * h1]); // 1j * k1 * h1
  const th = cTanh(ik1h1);
  const numerator = cAdd(zHalf, cMul(z1, th));
  const denominator = cAdd(z1, cMul(zHalf, th));
  const zTop = cMul(z1, cDiv(numerator, denominator));
  return cAbs2(zTop) / (omega * mu0);
}

function buildMt1dTruth(): SensorPayload {
  const TRUTH = { rho1: 100, rho2: 10, h1: 300 };
  const n = 25;
  const lo = -3;
  const hi = 3;
  const xValues: Array<number | null> = [];
  const dValues: Array<number | null> = [];
  for (let i = 0; i < n; i++) {
    const f = 10 ** (lo + (i * (hi - lo)) / (n - 1));
    xValues.push(f);
    dValues.push(mt1dRhoA(f, TRUTH.rho1, TRUTH.rho2, TRUTH.h1));
  }
  corrupt(xValues, dValues, 4);
  return { sensorId: 'dashboard-sim', dataType: 'MT_1D', timeSteps: xValues, amplitudes: dValues };
}

function buildIpColeColeTruth(): SensorPayload {
  const TRUTH = { m0: 25, tau: 0.5, c: 0.6 };
  const n = 25;
  const xValues: Array<number | null> = [];
  const dValues: Array<number | null> = [];
  for (let i = 0; i < n; i++) {
    const t = 0.01 + (i * (3.0 - 0.01)) / (n - 1);
    xValues.push(t);
    dValues.push(TRUTH.m0 * Math.exp(-((t / TRUTH.tau) ** TRUTH.c)));
  }
  corrupt(xValues, dValues, 4);
  return { sensorId: 'dashboard-sim', dataType: 'IP_COLE_COLE', timeSteps: xValues, amplitudes: dValues };
}

export const SIMULATORS: Record<MethodId, (agentMode: string) => SensorPayload> = {
  TDEM: (agentMode) => (agentMode === 'offline' ? buildBiexpTdem() : buildEmpymodTdem()),
  GRAVITY_SPHERE: () => buildGravitySphereTruth(),
  MAGNETICS_DIPOLE: () => buildMagneticsDipoleTruth(),
  GPR_REFLECTION: () => buildGprReflectionTruth(),
  SP_DIPOLE: () => buildSpDipoleTruth(),
  MOGI_SOURCE: () => buildMogiSourceTruth(),
  RADIOMETRIC: () => buildRadiometricTruth(),
  SEISMIC_REFRACTION: () => buildSeismicRefractionTruth(),
  EARTHQUAKE_LOCATION: () => buildEarthquakeLocationTruth(),
  ERT_WENNER: () => buildErtWennerTruth(),
  MT_1D: () => buildMt1dTruth(),
  IP_COLE_COLE: () => buildIpColeColeTruth(),
};
