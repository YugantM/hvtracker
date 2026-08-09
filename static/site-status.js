// Header status widget, present on every page via _site_header.html.j2.
//
// Shows two things: when the registry data was last refreshed, and a live pill
// with how much the machine surfaces are being used right now. Both come from
// ONE small, edge-cached call to /api/v1/usage. This deliberately replaces the
// previous fetch of /data/latest.json, which downloaded well over a megabyte
// of leaderboard JSON to read a single timestamp string.
//
// Generated pages server-render their freshness into data-updated, so they
// never need the timestamp from the network; the hand-written pages
// (/verify/, /scan/, /live/) ship no attribute and used to render a bare
// "updated" with nothing after it.
document.addEventListener("DOMContentLoaded", () => {
  const statusNodes = Array.from(document.querySelectorAll(".site-status"));
  // The live pill lives in the page content (agent profiles), not the header,
  // so a page can have one, the other, or both.
  const pills = Array.from(document.querySelectorAll(".live-pill"));
  if (!statusNodes.length && !pills.length) return;

  // Ambient, not a dashboard: /live/ polls every 10s because you are watching
  // it, but this sits in the chrome of every page, so it refreshes slowly and
  // stops entirely while the tab is hidden.
  const POLL_MS = 30000;

  const setUpdated = (node, value) => {
    const target = node.querySelector(".site-status-value");
    if (target && value) target.textContent = value;
  };

  // Paint server-rendered freshness before any network call, so the time never
  // flickers in on pages that already had it.
  statusNodes.forEach((node) => setUpdated(node, (node.getAttribute("data-updated") || "").trim()));

  const fmt = (n) => Number(n || 0).toLocaleString();
  let shown = null;   // last count rendered, so we only animate real changes
  let timer = null;

  const paint = (payload) => {
    const fallbackUpdated = (payload.data_updated || "").trim();
    const win = payload.window || {};
    // Lead with raw machine requests. Answered tool calls are the more
    // meaningful measure of work, but this rollup only began on 2026-08-09 and
    // most /mcp traffic is protocol handshakes, so tool calls sit near zero
    // while requests already show real traffic. Labelled "machine requests"
    // precisely so it is never read as questions answered — /live/ breaks out
    // both. Revisit once tool calls accumulate.
    const count = win.requests || 0;
    const label = "machine requests";

    const changed = shown !== null && count !== shown;
    statusNodes.forEach((node) => {
      if (!(node.getAttribute("data-updated") || "").trim()) {
        setUpdated(node, fallbackUpdated);
      }
    });

    if (count) {
      pills.forEach((pill) => {
        // textContent into the existing spans — the badge's structure lives in
        // the markup, so nothing has to be re-parsed here.
        const num = pill.querySelector(".lp-num");
        const sub = pill.querySelector(".lp-sub");
        // Only reveal once the number is actually in the DOM. Without this, a
        // page whose markup has drifted from this script shows an empty badge.
        if (!num) return;
        num.textContent = fmt(count);
        if (sub) sub.textContent = label + " · 24h";
        pill.hidden = false;
        if (changed) {
          pill.classList.remove("lp-bump");
          void pill.offsetWidth;   // restart the animation
          pill.classList.add("lp-bump");
        }
      });
    }
    shown = count;
  };

  const load = () => {
    fetch("/api/v1/usage", { headers: { Accept: "application/json" } })
      .then((response) => (response.ok ? response.json() : null))
      .then((payload) => { if (payload) paint(payload); })
      .catch(() => {});   // header chrome must never break the page
  };

  const start = () => { if (!timer) timer = setInterval(load, POLL_MS); };
  const stop = () => { if (timer) { clearInterval(timer); timer = null; } };

  load();
  start();
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) { stop(); } else { load(); start(); }
  });
});
