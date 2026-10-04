import { preferencesApi } from "../../features/preferences/api.js";

export function timezoneSelectorHtml(timezone = "UTC") {
  const utcSelected = timezone === "UTC" ? " selected" : "";
  const easternSelected = timezone === "America/New_York" ? " selected" : "";
  return `
    <label class="timezone-control">
      <span>Time zone</span>
      <select class="input timezone-select" data-timezone-select aria-label="Time zone">
        <option value="UTC"${utcSelected}>UTC</option>
        <option value="America/New_York"${easternSelected}>Eastern Time (ET)</option>
      </select>
      <span class="error-text" data-timezone-error role="status"></span>
    </label>
  `;
}

export function renderTimezoneSelector(
  container,
  { timezone = "UTC", onUpdated = () => {}, savePreference = preferencesApi.updateTimezone } = {},
) {
  if (!container) return;
  let savedTimezone = timezone;
  container.innerHTML = timezoneSelectorHtml(timezone);
  const select = container.querySelector("[data-timezone-select]");
  const error = container.querySelector("[data-timezone-error]");
  if (!select) return;
  select.addEventListener("change", async () => {
    error.textContent = "";
    select.disabled = true;
    try {
      const result = await savePreference(select.value);
      savedTimezone = result.timezone;
      select.value = savedTimezone;
      await onUpdated(savedTimezone);
    } catch (problem) {
      select.value = savedTimezone;
      error.textContent = problem.message;
    } finally {
      select.disabled = false;
    }
  });
}
