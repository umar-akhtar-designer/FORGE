export function divide(a: number, b: number): number | null {
  if (b === 0) {
    return null;
  }
  return a / b;
}