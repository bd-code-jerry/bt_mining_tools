export function themeToggleHtml(variant = "") {
  const variantClass = variant ? ` ${variant}` : "";
  return `
    <button class="theme-toggle${variantClass}" type="button" data-theme-toggle
      aria-label="Switch to dark mode" aria-pressed="false">
      <span class="theme-toggle-icon" data-theme-icon aria-hidden="true">☾</span>
      <span data-theme-label>Dark mode</span>
    </button>
  `;
}
