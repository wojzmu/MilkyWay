export interface CloudUi {
  distMax: number; // pc
  fMax: number; // relative uncertainty
  percent: number; // 5..100
  pointSize: number; // px
  brightness: number; // per-point opacity, 0.02..1
  hidden: string[]; // hidden class names
  labels: boolean; // names of well-known stars
}

export const F_MIN = 0.001;
export const F_MAX = 0.5;

export function defaultCloudUi(maxDist: number): CloudUi {
  return { distMax: maxDist, fMax: 0.2, percent: 100, pointSize: 2, brightness: 0.15, hidden: [], labels: true };
}

