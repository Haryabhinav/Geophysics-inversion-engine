/**
 * Display metadata for every method the platform supports — mirrors
 * python-agent/app/agent/methods/specs/*.py's MethodSpec params, kept as a
 * hand-curated frontend constant since this is presentational copy
 * (descriptions, citations), not runtime physics. The 12 curve-fit ids plus
 * LITHOLOGY match the backend's registry exactly — see DESIGN.md §13.1.
 */

export type MethodFamily =
  | 'Electromagnetic'
  | 'Electrical & IP'
  | 'Potential Field'
  | 'Seismic'
  | 'Radiometric'
  | 'Ground Penetrating Radar'
  | 'Classification';

// Fixed order — also the categorical color assignment order (dataviz rule:
// assign hues in fixed order, never cycled by filter/selection state).
export const METHOD_FAMILIES: MethodFamily[] = [
  'Electromagnetic',
  'Electrical & IP',
  'Potential Field',
  'Seismic',
  'Radiometric',
  'Ground Penetrating Radar',
  'Classification',
];

// Dataviz categorical slots 1-7, fixed order, never cycled — as the SAME
// CSS variables the Recharts series use (styles/globals.css), so a family tag
// and a chart line stay the same hue, and both follow the light/dark switch.
// These were previously literal light-mode hexes, which left family tags
// showing light-theme chart colours while the charts beside them had already
// switched to their dark-theme values. Callers tint them with `tint()`
// (color-mix), since hex-suffix concatenation can't alpha-blend a var().
export const FAMILY_COLOR: Record<MethodFamily, string> = {
  Electromagnetic: 'var(--viz-series1)',
  'Electrical & IP': 'var(--viz-series2)',
  'Potential Field': 'var(--viz-series3)',
  Seismic: 'var(--viz-series4)',
  Radiometric: 'var(--viz-series5)',
  'Ground Penetrating Radar': 'var(--viz-series6)',
  Classification: 'var(--viz-series7)',
};

export interface ParamMeta {
  name: string;
  unit: string;
  description: string;
}

export interface MethodMeta {
  id: string;
  displayName: string;
  shortName: string;
  family: MethodFamily;
  description: string;
  reference: string;
  xLabel: string;
  dLabel: string;
  isClassification: boolean;
  params: ParamMeta[];
}

export const METHOD_CATALOG: MethodMeta[] = [
  {
    id: 'TDEM',
    displayName: 'Time-Domain EM',
    shortName: 'TDEM',
    family: 'Electromagnetic',
    description:
      'Layered-earth resistivity from a step-off transient decay, forward-modeled with empymod.',
    reference: 'empymod (Werthmüller 2017)',
    xLabel: 'time (s)',
    dLabel: 'amplitude',
    isClassification: false,
    params: [
      { name: 'res1', unit: 'Ohm·m', description: 'overburden resistivity' },
      { name: 'res2', unit: 'Ohm·m', description: 'basement resistivity' },
      { name: 'depth1', unit: 'm', description: 'depth to basement' },
    ],
  },
  {
    id: 'MT_1D',
    displayName: 'Magnetotellurics',
    shortName: 'MT',
    family: 'Electromagnetic',
    description: '1D, 2-layer apparent-resistivity sounding from a recursive layered impedance.',
    reference: 'Wait (1954); Simpson & Bahr (2005)',
    xLabel: 'frequency (Hz)',
    dLabel: 'apparent resistivity (Ohm·m)',
    isClassification: false,
    params: [
      { name: 'rho1', unit: 'Ohm·m', description: 'upper-layer resistivity' },
      { name: 'rho2', unit: 'Ohm·m', description: 'half-space resistivity' },
      { name: 'h1', unit: 'm', description: 'depth to conductive half-space' },
    ],
  },
  {
    id: 'ERT_WENNER',
    displayName: 'Electrical Resistivity (ERT)',
    shortName: 'ERT',
    family: 'Electrical & IP',
    description: '2-layer Wenner-array apparent-resistivity sounding curve.',
    reference: 'Telford, Geldart & Sheriff (1990) ch.8',
    xLabel: 'electrode spacing a (m)',
    dLabel: 'apparent resistivity (Ohm·m)',
    isClassification: false,
    params: [
      { name: 'rho1', unit: 'Ohm·m', description: 'upper-layer resistivity' },
      { name: 'rho2', unit: 'Ohm·m', description: 'half-space resistivity' },
      { name: 'h', unit: 'm', description: 'depth to interface' },
    ],
  },
  {
    id: 'IP_COLE_COLE',
    displayName: 'Induced Polarization',
    shortName: 'IP',
    family: 'Electrical & IP',
    description: 'Chargeability decay after current shutoff (stretched-exponential approximation).',
    reference: 'approximates Pelton et al. (1978)',
    xLabel: 'time after shutoff (s)',
    dLabel: 'chargeability (mV/V)',
    isClassification: false,
    params: [
      { name: 'm0', unit: 'mV/V', description: 'initial chargeability' },
      { name: 'tau', unit: 's', description: 'decay time constant' },
      { name: 'c', unit: '—', description: 'stretching exponent' },
    ],
  },
  {
    id: 'SP_DIPOLE',
    displayName: 'Self-Potential',
    shortName: 'SP',
    family: 'Electrical & IP',
    description: 'Surface voltage profile from a buried point-dipole (electrokinetic/redox) source.',
    reference: 'Yüngül (1950)',
    xLabel: 'survey position x (m)',
    dLabel: 'SP voltage (mV)',
    isClassification: false,
    params: [
      { name: 'K', unit: 'mV·m²', description: 'lumped dipole-moment amplitude' },
      { name: 'z', unit: 'm', description: 'depth to source' },
      { name: 'x0', unit: 'm', description: 'horizontal position of source' },
      { name: 'theta', unit: 'rad', description: 'dipole polarization angle' },
    ],
  },
  {
    id: 'GRAVITY_SPHERE',
    displayName: 'Gravity',
    shortName: 'Gravity',
    family: 'Potential Field',
    description: 'Residual gravity anomaly of a single buried compact (spherical) body.',
    reference: 'Telford, Geldart & Sheriff (1990) eq. 2.20',
    xLabel: 'survey position x (m)',
    dLabel: 'residual gravity anomaly (mGal)',
    isClassification: false,
    params: [
      { name: 'K', unit: 'mGal·m²', description: 'lumped G·mass amplitude' },
      { name: 'z', unit: 'm', description: 'depth to sphere center' },
      { name: 'x0', unit: 'm', description: 'horizontal position of sphere' },
    ],
  },
  {
    id: 'MAGNETICS_DIPOLE',
    displayName: 'Magnetics',
    shortName: 'Magnetics',
    family: 'Potential Field',
    description: 'Total-field magnetic anomaly of a buried dipole (vertical-field approximation).',
    reference: 'Blakely (1995)',
    xLabel: 'survey position x (m)',
    dLabel: 'total-field anomaly (nT)',
    isClassification: false,
    params: [
      { name: 'K', unit: 'nT·m³', description: 'lumped dipole-moment amplitude' },
      { name: 'z', unit: 'm', description: 'depth to body' },
      { name: 'x0', unit: 'm', description: 'horizontal position of body' },
    ],
  },
  {
    id: 'MOGI_SOURCE',
    displayName: 'Geodetic Deformation',
    shortName: 'Mogi',
    family: 'Potential Field',
    description: 'Vertical surface displacement from a point pressure source (magma/reservoir) at depth.',
    reference: 'Mogi (1958)',
    xLabel: 'survey position x (m)',
    dLabel: 'vertical displacement (m)',
    isClassification: false,
    params: [
      { name: 'C', unit: 'm³', description: 'lumped (1−ν)·volume-change amplitude' },
      { name: 'd', unit: 'm', description: 'source depth' },
      { name: 'x0', unit: 'm', description: 'horizontal position of source' },
    ],
  },
  {
    id: 'SEISMIC_REFRACTION',
    displayName: 'Seismic Refraction',
    shortName: 'Seismic',
    family: 'Seismic',
    description: 'Layered P-wave velocity model from a direct-wave / head-wave travel-time curve.',
    reference: 'Kearey, Brooks & Hill; Telford et al. (1990) §4.4',
    xLabel: 'source-receiver offset (m)',
    dLabel: 'first-arrival travel time (s)',
    isClassification: false,
    params: [
      { name: 'v1', unit: 'm/s', description: 'upper-layer P-wave velocity' },
      { name: 'v2', unit: 'm/s', description: 'half-space P-wave velocity' },
      { name: 'h', unit: 'm', description: 'depth to interface' },
    ],
  },
  {
    id: 'EARTHQUAKE_LOCATION',
    displayName: 'Seismology (Earthquake Location)',
    shortName: 'Seismology',
    family: 'Seismic',
    description: "Hypocenter + origin time from multi-station P-wave arrivals (Geiger's method).",
    reference: 'Geiger (1912)',
    xLabel: 'station index',
    dLabel: 'P-wave arrival time (s)',
    isClassification: false,
    params: [
      { name: 'src_x', unit: 'm', description: 'epicenter x-coordinate' },
      { name: 'src_y', unit: 'm', description: 'epicenter y-coordinate' },
      { name: 'src_z', unit: 'm', description: 'hypocenter depth' },
      { name: 'origin_t', unit: 's', description: 'origin time offset' },
      { name: 'velocity', unit: 'm/s', description: 'seismic P-wave velocity' },
    ],
  },
  {
    id: 'RADIOMETRIC',
    displayName: 'Radiometrics',
    shortName: 'Radiometric',
    family: 'Radiometric',
    description: 'K/U/Th elemental concentrations from gamma-ray window counts (spectral stripping).',
    reference: 'IAEA TECDOC-1363 (2003)',
    xLabel: 'window index (0=K, 1=U, 2=Th)',
    dLabel: 'count rate (arb. units)',
    isClassification: false,
    params: [
      { name: 'K_conc', unit: '%', description: 'potassium concentration' },
      { name: 'U_conc', unit: 'ppm', description: 'uranium concentration' },
      { name: 'Th_conc', unit: 'ppm', description: 'thorium concentration' },
    ],
  },
  {
    id: 'GPR_REFLECTION',
    displayName: 'Ground Penetrating Radar',
    shortName: 'GPR',
    family: 'Ground Penetrating Radar',
    description: 'Depth to a reflector from a common-midpoint (CMP) two-way travel-time hyperbola.',
    reference: 'Annan (2003)',
    xLabel: 'antenna offset (m)',
    dLabel: 'two-way travel time (ns)',
    isClassification: false,
    params: [
      { name: 'v', unit: 'm/ns', description: 'subsurface EM wave velocity' },
      { name: 'd', unit: 'm', description: 'depth to reflector' },
    ],
  },
  {
    id: 'LITHOLOGY',
    displayName: 'Borehole Lithology',
    shortName: 'Lithology',
    family: 'Classification',
    description:
      'Predicts a lithology class per depth from a small labeled well-log training set (gamma ray, resistivity, density, sonic).',
    reference: 'supervised ML — RandomForest baseline',
    xLabel: 'depth (m)',
    dLabel: 'lithology class',
    isClassification: true,
    params: [],
  },
];

export const METHOD_BY_ID: Record<string, MethodMeta> = Object.fromEntries(
  METHOD_CATALOG.map((m) => [m.id, m]),
);

export function methodMeta(id: string): MethodMeta {
  return (
    METHOD_BY_ID[id] ?? {
      id,
      displayName: id,
      shortName: id,
      family: 'Classification',
      description: '',
      reference: '',
      xLabel: 'x',
      dLabel: 'y',
      isClassification: false,
      params: [],
    }
  );
}
