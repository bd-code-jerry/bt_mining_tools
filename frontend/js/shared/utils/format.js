export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function numberValue(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function localeNumber(value, { minimumFractionDigits = 0, maximumFractionDigits = 10 } = {}) {
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits,
    maximumFractionDigits,
  });
}

export function formatBalance(value, unit) {
  const n = numberValue(value, 0);

  // USD keeps the familiar 2 decimals for ordinary values, but does not hide
  // extra precision. Example: 1.23456 is shown as $1.23456, not $1.23.
  if (unit === "USD") {
    return `$${localeNumber(n, { minimumFractionDigits: 2, maximumFractionDigits: 10 })}`;
  }

  if (unit === "t") {
    return `${localeNumber(n, { minimumFractionDigits: 0, maximumFractionDigits: 12 })}t`;
  }

  return localeNumber(n, { minimumFractionDigits: 0, maximumFractionDigits: 10 });
}

export function inputNumber(value, maximumFractionDigits = 12) {
  const n = numberValue(value, 0);
  if (!Number.isFinite(n)) return "";

  // Inputs intentionally do NOT force USD to 2 decimals. Users may enter
  // values such as 1.23456789. Trailing zeroes are removed only when an input
  // is initially rendered or normalized after blur.
  const fixed = n.toFixed(maximumFractionDigits);
  const trimmed = fixed.replace(/(?:\.0+|(?:(\.[0-9]*?[1-9]))0+)$/, "$1");
  return trimmed === "-0" ? "0" : trimmed;
}

export function parseNumberInput(rawValue) {
  const text = String(rawValue ?? "").trim();
  if (text === "") return null;
  const value = Number(text);
  return Number.isFinite(value) ? value : null;
}

export function formatDateShort(isoDate) {
  const [year, month, day] = String(isoDate).split("-").map(Number);
  if (!year || !month || !day) return escapeHtml(isoDate);
  const d = new Date(year, month - 1, day);
  return d.toLocaleDateString(undefined, { day: "2-digit", month: "short" }).replace(" ", "-");
}

export function localIsoDate() {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}
