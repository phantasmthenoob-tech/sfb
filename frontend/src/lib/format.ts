export function money(value: number, digits = 2): string {
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function signedMoney(value: number): string {
  const formatted = money(Math.abs(value));
  return `${value >= 0 ? "+" : "-"}${formatted}`;
}

export function signedPct(value: number, digits = 2): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}%`;
}

export function signedShares(quantity: number): string {
  return `${quantity > 0 ? "+" : ""}${quantity}`;
}

export function toneClass(value: number): "pos" | "neg" | "flat" {
  if (value > 0) return "pos";
  if (value < 0) return "neg";
  return "flat";
}


export function simDate(ts: string | undefined): string {
  if (!ts) return "—";
  return new Date(`${ts.slice(0, 10)}T00:00:00`).toLocaleDateString("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  });
}

