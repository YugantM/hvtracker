document.addEventListener("DOMContentLoaded", () => {
  const statusNodes = Array.from(document.querySelectorAll(".site-status[data-updated]"));
  if (!statusNodes.length) return;

  const emptyNodes = statusNodes.filter((node) => !(node.getAttribute("data-updated") || "").trim());
  if (!emptyNodes.length) {
    statusNodes.forEach((node) => {
      const value = (node.getAttribute("data-updated") || "").trim();
      const target = node.querySelector(".site-status-value");
      if (target && value) target.textContent = value;
    });
    return;
  }

  fetch("/data/latest.json", { headers: { Accept: "application/json" } })
    .then((response) => (response.ok ? response.json() : null))
    .then((payload) => {
      const updated = (payload && typeof payload.updated === "string" ? payload.updated : "").trim();
      if (!updated) return;
      statusNodes.forEach((node) => {
        const value = (node.getAttribute("data-updated") || updated).trim();
        const target = node.querySelector(".site-status-value");
        if (target && value) target.textContent = value;
      });
    })
    .catch(() => {});
});
