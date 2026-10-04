export function showToast(message, type = "default", timeout = 3200) {
  const root = document.getElementById("toast-root");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  root.appendChild(el);
  window.setTimeout(() => el.remove(), timeout);
}
