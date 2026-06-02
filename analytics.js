(function () {
  var ATTRIBUTION_KEY = "hvtracker_attribution_v1";
  var LAST_COMPARE_KEY = "hvtracker_last_compare_v1";

  function safeStorage(kind) {
    try {
      return kind === "local" ? window.localStorage : window.sessionStorage;
    } catch (_) {
      return null;
    }
  }

  function readJson(storage, key) {
    if (!storage) return null;
    try {
      var raw = storage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  }

  function writeJson(storage, key, value) {
    if (!storage) return;
    try {
      storage.setItem(key, JSON.stringify(value));
    } catch (_) {}
  }

  function inferPageType(pathname) {
    if (pathname === "/" || pathname === "") return "leaderboard";
    if (pathname.indexOf("/agents/") === 0) return "agent_profile";
    if (pathname.indexOf("/categories/") === 0) return "category_page";
    if (pathname.indexOf("/blog/") === 0) {
      return pathname === "/blog/" || pathname === "/blog" ? "blog_index" : "blog_article";
    }
    if (pathname.indexOf("/compare/") === 0 || pathname === "/compare") return "compare_page";
    if (pathname.indexOf("/methodology") === 0) return "methodology";
    if (pathname.indexOf("/spec/") === 0 || pathname === "/spec") return "spec_page";
    if (pathname.indexOf("/badges/") === 0 || pathname === "/badges") return "badges";
    if (pathname.indexOf("/roadmap/") === 0 || pathname === "/roadmap") return "roadmap";
    return "unknown";
  }

  function trimValue(value, maxLen) {
    return value ? String(value).slice(0, maxLen) : "";
  }

  function captureAttribution() {
    var sessionStore = safeStorage("session");
    var localStore = safeStorage("local");
    var params = new URLSearchParams(window.location.search);
    var hasUtm = ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"].some(function (key) {
      return params.get(key);
    });
    var referrer = document.referrer || "";
    var referrerUrl = null;
    var externalReferrer = "";
    try {
      referrerUrl = referrer ? new URL(referrer) : null;
      if (referrerUrl && referrerUrl.hostname !== window.location.hostname) {
        externalReferrer = referrerUrl.hostname;
      }
    } catch (_) {}

    var existing = readJson(sessionStore, ATTRIBUTION_KEY) || readJson(localStore, ATTRIBUTION_KEY) || {};
    var next = existing;

    if (hasUtm || externalReferrer || !existing.source) {
      next = {
        source: trimValue(params.get("utm_source"), 100) || externalReferrer || existing.source || "(direct)",
        medium: trimValue(params.get("utm_medium"), 100) || (externalReferrer ? "referral" : existing.medium || "(none)"),
        campaign: trimValue(params.get("utm_campaign"), 120) || existing.campaign || "",
        term: trimValue(params.get("utm_term"), 120) || existing.term || "",
        content: trimValue(params.get("utm_content"), 120) || existing.content || "",
        referrer_host: trimValue(externalReferrer, 120) || existing.referrer_host || "",
        landing_path: existing.landing_path || window.location.pathname,
        landing_page: existing.landing_page || window.location.pathname + window.location.search
      };
      writeJson(sessionStore, ATTRIBUTION_KEY, next);
      writeJson(localStore, ATTRIBUTION_KEY, next);
    }

    return next;
  }

  function baseParams() {
    var body = document.body || {};
    var data = body.dataset || {};
    var attribution = captureAttribution();
    var params = {
      page_type: data.pageType || inferPageType(window.location.pathname),
      page_path: window.location.pathname
    };
    if (data.agentSlug) params.agent_slug = data.agentSlug;
    if (data.agentName) params.agent_name = data.agentName;
    if (data.category) params.category = data.category;
    if (data.globalRank) params.global_rank = Number(data.globalRank);
    if (data.trustScore) params.trust_score = Number(data.trustScore);
    if (attribution.source) params.session_source = attribution.source;
    if (attribution.medium) params.session_medium = attribution.medium;
    if (attribution.campaign) params.session_campaign = attribution.campaign;
    if (attribution.referrer_host) params.referrer_host = attribution.referrer_host;
    return params;
  }

  window.hvtTrack = function (eventName, params) {
    if (typeof window.gtag !== "function") return;
    window.gtag("event", eventName, Object.assign(baseParams(), params || {}));
  };

  captureAttribution();
  if (typeof window.gtag === "function") {
    window.hvtTrack("hvt_pageview", {
      page_location: window.location.href,
      page_title: document.title
    });
  }

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
    var isComparePath = url.pathname.startsWith("/compare/");
    var isRoadmapPath = url.pathname === "/roadmap/" || url.pathname === "/roadmap";
    // Correction URLs are GitHub issue templates with our [Correction] title prefix.
    var isCorrectionLink = url.hostname === "github.com" && href.indexOf("%5BCorrection%5D") !== -1;

    // Leaving the /badges/ page via an in-site, same-tab link (badge adoption funnel).
    // Fired alongside the destination event below so we capture both the exit and where it went.
    if (document.body.dataset.pageType === "badges" && !link.target &&
        !isBadgesPath && url.hostname === window.location.hostname) {
      window.hvtTrack("badges_exit", Object.assign({}, params, { exit_to: url.pathname }));
    }

    if (link.closest(".pr-offer")) {
      window.hvtTrack("badge_pr_click", params);
    } else if (isCorrectionLink) {
      // Distinct from generic github_issue_click — correction is a conversion event.
      window.hvtTrack("correction_click", Object.assign({}, params, {
        from_area: link.closest(".maintainer-cta") ? "maintainer_cta" :
                   link.closest(".review-actions") ? "review_card" :
                   link.closest(".hero-actions") ? "hero" : "other"
      }));
    } else if (isComparePath) {
      window.hvtTrack("compare_click", Object.assign({}, params, {
        from_area: link.closest(".compare-strip") ? "compare_strip" :
                   link.closest(".review-actions") ? "review_card" :
                   link.closest(".hero-actions") ? "hero" :
                   link.closest(".siblings") ? "head_to_head" : "other"
      }));
    } else if (isRoadmapPath) {
      window.hvtTrack("roadmap_click", params);
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

  if (window.location.pathname.indexOf("/compare") === 0) {
    var compareState = window.location.search;
    var sessionStore = safeStorage("session");
    var previousState = sessionStore ? sessionStore.getItem(LAST_COMPARE_KEY) : null;
    if (compareState && compareState !== previousState) {
      var selections = new URLSearchParams(window.location.search).get("a") || "";
      var slugs = selections ? selections.split(",").filter(Boolean) : [];
      if (slugs.length >= 2) {
        window.hvtTrack("compare_view", {
          compared_agents: slugs.join(","),
          compared_count: slugs.length
        });
      }
    }
    if (sessionStore) {
      try {
        sessionStore.setItem(LAST_COMPARE_KEY, compareState);
      } catch (_) {}
    }
  }
})();
