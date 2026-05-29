(function () {
  function baseParams() {
    var body = document.body || {};
    var data = body.dataset || {};
    var params = {
      page_type: data.pageType || "unknown"
    };
    if (data.agentSlug) params.agent_slug = data.agentSlug;
    if (data.agentName) params.agent_name = data.agentName;
    if (data.category) params.category = data.category;
    if (data.globalRank) params.global_rank = Number(data.globalRank);
    if (data.trustScore) params.trust_score = Number(data.trustScore);
    return params;
  }

  window.hvtTrack = function (eventName, params) {
    if (typeof window.gtag !== "function") return;
    window.gtag("event", eventName, Object.assign(baseParams(), params || {}));
  };

  document.addEventListener("click", function (event) {
    var link = event.target.closest("a");
    if (!link) return;

    var href = link.getAttribute("href") || "";
    var url = new URL(link.href, window.location.href);
    var params = {
      link_url: url.href,
      link_text: link.textContent.trim().slice(0, 80)
    };
    var isBadgesPath = url.pathname === "/badges/" || url.pathname === "/badges";

    // Leaving the /badges/ page via an in-site, same-tab link (badge adoption funnel).
    // Fired alongside the destination event below so we capture both the exit and where it went.
    if (document.body.dataset.pageType === "badges" && !link.target &&
        !isBadgesPath && url.hostname === window.location.hostname) {
      window.hvtTrack("badges_exit", Object.assign({}, params, { exit_to: url.pathname }));
    }

    if (link.closest(".pr-offer")) {
      window.hvtTrack("badge_pr_click", params);
    } else if (isBadgesPath) {
      // Landing on /badges/: distinguish the per-agent "Badge guide for maintainers" link.
      window.hvtTrack(link.closest("#embed-badge") ? "badge_guide_click" : "badges_click", params);
    } else if (url.pathname.startsWith("/agents/")) {
      var parts = url.pathname.split("/").filter(Boolean);
      window.hvtTrack("agent_click", Object.assign(params, {
        clicked_agent_slug: parts[1] || "",
        link_area: link.closest(".movers") ? "movers" :
          link.closest(".siblings") ? "siblings" :
          document.body.dataset.pageType || "unknown"
      }));
    } else if (url.pathname.startsWith("/data/")) {
      window.hvtTrack("data_api_click", Object.assign(params, { endpoint: url.pathname }));
    } else if (url.pathname.startsWith("/methodology")) {
      window.hvtTrack("methodology_click", params);
    } else if (url.pathname.startsWith("/spec")) {
      window.hvtTrack("specs_click", params);
    } else if (url.pathname === "/") {
      window.hvtTrack("leaderboard_click", params);
    } else if (url.hostname === "github.com") {
      window.hvtTrack(href.includes("/issues/new") || href.includes("/issues")
        ? "github_issue_click"
        : "github_click", params);
    } else if (url.hostname !== window.location.hostname) {
      window.hvtTrack("outbound_click", Object.assign(params, { outbound_domain: url.hostname }));
    }
  });
})();
