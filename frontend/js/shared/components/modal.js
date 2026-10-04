export function openModal({ title, bodyHtml, footerHtml = "", onReady }) {
  const root = document.getElementById("modal-root");
  root.innerHTML = `
    <div class="modal-backdrop" data-modal-backdrop>
      <section class="modal" role="dialog" aria-modal="true" aria-label="${title}">
        <div class="modal-header">
          <h2>${title}</h2>
          <button class="btn btn-small" type="button" data-modal-close>Close</button>
        </div>
        <div class="modal-body">${bodyHtml}</div>
        ${footerHtml ? `<div class="modal-footer">${footerHtml}</div>` : ""}
      </section>
    </div>
  `;

  const close = () => { root.innerHTML = ""; };
  root.querySelectorAll("[data-modal-close]").forEach((btn) => btn.addEventListener("click", close));
  root.querySelector("[data-modal-backdrop]").addEventListener("click", (event) => {
    if (event.target.matches("[data-modal-backdrop]")) close();
  });
  document.addEventListener("keydown", function escHandler(event) {
    if (event.key === "Escape" && root.innerHTML) {
      close();
      document.removeEventListener("keydown", escHandler);
    }
  });

  if (onReady) onReady({ root, close });
  return { close };
}
