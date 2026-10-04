import { escapeHtml, formatBalance } from "../../../shared/utils/format.js";
import { providerSymbols } from "../../balances/providerUi.js";

const PERIOD_LABELS = {
  all: "All Time",
  day: "1 Day",
  week: "1 Week",
  month: "1 Month",
  custom: "Custom Range",
};

function formatDateLong(isoDate) {
  if (!isoDate) return "—";
  const [year, month, day] = String(isoDate).split("-").map(Number);
  if (!year || !month || !day) return escapeHtml(isoDate);
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function periodButton(period, activePeriod, label) {
  const active = period === activePeriod ? "active" : "";
  return `<button class="usage-period-btn ${active}" type="button" data-usage-period="${period}">${label}</button>`;
}

function providerUsageCards(summary) {
  return (summary?.by_provider || []).map((provider) => `
    <div class="usage-provider-card">
      <div class="provider-badge">${providerSymbols[provider.provider_key] || escapeHtml(provider.display_name).slice(0, 1)}</div>
      <div class="usage-provider-copy">
        <div class="usage-provider-name">${escapeHtml(provider.display_name)}</div>
        <div class="usage-provider-value">${formatBalance(provider.total_used, provider.unit)}</div>
        <div class="usage-provider-unit">Total used • ${escapeHtml(provider.unit)}</div>
      </div>
    </div>
  `).join("");
}

function totalsByUnitHtml(summary) {
  const byUnit = summary?.by_unit || {};
  const orderedUnits = ["USD", "credits", "t"];
  const units = [
    ...orderedUnits.filter((unit) => Object.prototype.hasOwnProperty.call(byUnit, unit)),
    ...Object.keys(byUnit).filter((unit) => !orderedUnits.includes(unit)),
  ];

  if (!units.length) return `<span>No usage in this range</span>`;

  return units.map((unit) => `
    <span><strong>${escapeHtml(unit)}:</strong> ${formatBalance(byUnit[unit], unit)}</span>
  `).join("");
}

export function usageRangeSummaryHtml({
  summary,
  activePeriod = "all",
  showCustomRange = false,
  customStart = "",
  customEnd = "",
  loading = false,
  error = "",
}) {
  const startLabel = formatDateLong(summary?.start_date);
  const endLabel = formatDateLong(summary?.end_date);
  const rangeLabel = summary?.start_date && summary?.end_date
    ? summary.start_date === summary.end_date
      ? startLabel
      : `${startLabel} → ${endLabel}`
    : "No saved dates yet";

  const presetActivePeriod = showCustomRange ? "" : activePeriod;

  return `
    <section class="card section-card usage-range-section" id="usage-range-section">
      <div class="section-head usage-range-head">
        <div>
          <h2>Total Used Balance by API Key</h2>
          <div class="help">See how much each API key used during a selected date range. Start and end dates are included.</div>
        </div>
        <div class="usage-period-tabs" aria-label="Usage range">
          ${periodButton("all", presetActivePeriod, PERIOD_LABELS.all)}
          ${periodButton("day", presetActivePeriod, PERIOD_LABELS.day)}
          ${periodButton("week", presetActivePeriod, PERIOD_LABELS.week)}
          ${periodButton("month", presetActivePeriod, PERIOD_LABELS.month)}
          <button class="usage-period-btn ${activePeriod === "custom" || showCustomRange ? "active" : ""}" type="button" data-open-custom-range>📅 Custom Range</button>
        </div>
      </div>

      ${showCustomRange ? `
        <div class="custom-range-bar">
          <label class="field custom-range-field">
            <span>From</span>
            <input class="input" type="date" value="${escapeHtml(customStart)}" data-usage-start />
          </label>
          <span class="custom-range-separator">to</span>
          <label class="field custom-range-field">
            <span>To</span>
            <input class="input" type="date" value="${escapeHtml(customEnd)}" data-usage-end />
          </label>
          <button class="btn btn-primary" type="button" data-apply-custom-range>Apply Range</button>
          <button class="btn" type="button" data-close-custom-range>Cancel</button>
        </div>
      ` : ""}

      <div class="usage-range-meta">
        <div>
          <span class="usage-range-label">${escapeHtml(PERIOD_LABELS[activePeriod] || "Selected Range")}</span>
          <strong>${rangeLabel}</strong>
          <span>${Number(summary?.entry_count || 0)} saved ${Number(summary?.entry_count || 0) === 1 ? "entry" : "entries"}</span>
        </div>
        <div class="usage-unit-totals">${totalsByUnitHtml(summary)}</div>
      </div>

      ${error ? `<div class="usage-range-error">${escapeHtml(error)}</div>` : ""}
      ${loading
        ? `<div class="loading-row usage-range-loading">Calculating usage…</div>`
        : `<div class="usage-provider-grid">${providerUsageCards(summary)}</div>`}
    </section>
  `;
}
