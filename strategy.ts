export type Position = { price: number; value: number };
export type Scenario = { priceChange: number; launchLift: number; response: number; priceWeight: number };
export const neutral: Scenario = { priceChange: 0, launchLift: 0, response: 0, priceWeight: 50 };
export const clamp = (value: number) => Math.min(100, Math.max(0, value));
export function simulate(positions: Position[], target: number, scenario: Scenario) {
  const weight = clamp(scenario.priceWeight) / 100;
  const score = (p: Position) => weight * (100 - p.price) + (1 - weight) * p.value;
  return positions.map((p, index) => {
    const before = { price: clamp(p.price), value: clamp(p.value) };
    const after = { price: clamp(before.price * (1 + (index === target ? scenario.priceChange : -scenario.response) / 100)), value: clamp(before.value + (index === target ? scenario.launchLift : 0)) };
    return { before, after, baseline: score(before), score: score(after), delta: score(after) - score(before) };
  });
}
export function rank(scores: number[], index: number) { return 1 + scores.filter(score => score > scores[index] + 0.00001).length; }
