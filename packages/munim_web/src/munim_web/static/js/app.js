// Small enhancements; every page works without them except zoom and copy.

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

function toast(text) {
  const box = $(".toast");
  if (!box) return;
  box.textContent = text;
  window.setTimeout(() => { box.textContent = ""; }, 4000);
}

function setup(root = document) {
  // Zoom the paper: buttons and keyboard (+, -, 0) on the viewer.
  const canvas = $("[data-canvas]", root);
  if (canvas) {
    let zoom = 1;
    const apply = () => { canvas.style.width = `${Math.round(zoom * 100)}%`; };
    const change = (kind) => {
      if (kind === "in") zoom = Math.min(4, zoom * 1.25);
      else if (kind === "out") zoom = Math.max(1, zoom / 1.25);
      else zoom = 1;
      apply();
    };
    $$("[data-zoom]", root).forEach((button) => {
      button.addEventListener("click", () => change(button.dataset.zoom));
    });
    const frame = $("[data-viewer]", root);
    frame?.addEventListener("keydown", (event) => {
      if (event.key === "+" || event.key === "=") change("in");
      else if (event.key === "-") change("out");
      else if (event.key === "0") change("fit");
    });
  }

  // Selecting a box selects its row and the other way round.
  const select = (id) => {
    $$(".is-selected[data-claim]", root).forEach((el) => el.classList.remove("is-selected"));
    $$(`[data-claim="${CSS.escape(id)}"]`, root).forEach((el) => el.classList.add("is-selected"));
  };
  $$("a.box[data-claim]", root).forEach((box) => {
    box.addEventListener("click", () => select(box.dataset.claim));
  });
  $$("tr.row[data-claim]", root).forEach((row) => {
    row.addEventListener("click", () => select(row.dataset.claim));
  });

  // Arrow keys move between rows of the claims table; Escape closes an open edit.
  const rows = $$("tr.row[data-claim]", root);
  rows.forEach((row, index) => {
    row.addEventListener("keydown", (event) => {
      if (event.target !== row) return;
      if (event.key === "ArrowDown" && rows[index + 1]) { rows[index + 1].focus(); event.preventDefault(); }
      if (event.key === "ArrowUp" && rows[index - 1]) { rows[index - 1].focus(); event.preventDefault(); }
      if (event.key === "Enter") { const edit = $("details.edit", row); if (edit) { edit.open = true; $("input[name=value]", edit)?.focus(); } }
    });
  });
  $$("details.edit, details.accept", root).forEach((details) => {
    details.addEventListener("keydown", (event) => {
      if (event.key === "Escape") { details.open = false; details.closest("tr")?.focus(); }
    });
  });

  // Copy the notice text; print the evidence file.
  $$("[data-copy]", root).forEach((button) => {
    button.addEventListener("click", async () => {
      const source = document.getElementById(button.dataset.copy);
      if (!source) return;
      await navigator.clipboard.writeText(source.textContent);
      toast($(".toast")?.dataset.copied || "");
    });
  });
  $$("[data-print]", root).forEach((button) => button.addEventListener("click", () => window.print()));
}

document.addEventListener("DOMContentLoaded", () => setup());
// hx-boost swaps the whole body; small fragments (the status line) need no new listeners.
document.addEventListener("htmx:afterSettle", (event) => {
  if (event.detail?.target === document.body) setup();
});
