(function () {
  // Skip analytics for developers and bots.
  // Set once in your browser console: localStorage.setItem('hvt_notrack', '1')
  try {
    if (localStorage.getItem("hvt_notrack") === "1") return;
  } catch (_) {}
  var ua = navigator.userAgent || "";
  if (/HeadlessChrome|Puppeteer|Playwright|Claude\/[\d.]+.*Electron\/|bot|crawl|spider|curl|wget|python-requests/i.test(ua)) return;

  var ATTRIBUTION_KEY = "hvtracker_attribution_v1";
  var LAST_COMPARE_KEY = "hvtracker_last_compare_v1";
  var ALERT_POPUP_KEY = "hvtracker_alert_popup_state_v1";

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

  function nowIso() {
    return new Date().toISOString();
  }

  function readPopupState() {
    return readJson(safeStorage("local"), ALERT_POPUP_KEY) || {};
  }

  function writePopupState(next) {
    writeJson(safeStorage("local"), ALERT_POPUP_KEY, next);
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

  function shouldShowAlertPopup() {
    var path = window.location.pathname || "/";
    if (path.indexOf("/agents/") === 0) return false;
    if (path.indexOf("/alerts") === 0) return false;
    if (path.indexOf("/submit") === 0 || path.indexOf("/correct") === 0) return false;

    var state = readPopupState();
    if (state.submitted_at) return false;

    if (state.dismissed_at) {
      var dismissedAt = Date.parse(state.dismissed_at);
      if (!isNaN(dismissedAt) && (Date.now() - dismissedAt) < 7 * 24 * 60 * 60 * 1000) {
        return false;
      }
    }

    return true;
  }

  function buildAlertPopup() {
    if (document.getElementById("hvt-alert-popup")) return null;

    var overlay = document.createElement("div");
    overlay.id = "hvt-alert-popup";
    overlay.setAttribute("hidden", "hidden");
    overlay.innerHTML =
      '<div class="hvt-alert-popup__backdrop" data-alert-close="backdrop"></div>' +
      '<div class="hvt-alert-popup__panel" role="dialog" aria-modal="true" aria-labelledby="hvt-alert-popup-title">' +
        '<button type="button" class="hvt-alert-popup__close" aria-label="Close alert signup" data-alert-close="button">×</button>' +
        '<div class="hvt-alert-popup__eyebrow">Trust alerts</div>' +
        '<h2 id="hvt-alert-popup-title">Get emailed when agent trust signals move.</h2>' +
        '<p class="hvt-alert-popup__copy">Join the waitlist for rank changes, provenance regressions, and meaningful trust score drops.</p>' +
        '<form class="hvt-alert-popup__form" id="hvt-alert-popup-form">' +
          '<label for="hvt-alert-popup-email">Work email</label>' +
          '<input id="hvt-alert-popup-email" name="email" type="email" placeholder="you@company.com" required />' +
          '<div class="hvt-alert-popup__actions">' +
            '<button type="submit">Join waitlist</button>' +
            '<button type="button" class="secondary" data-alert-close="later">Maybe later</button>' +
          '</div>' +
          '<p class="hvt-alert-popup__status" id="hvt-alert-popup-status" aria-live="polite"></p>' +
        '</form>' +
      '</div>';

    var style = document.createElement("style");
    style.id = "hvt-alert-popup-style";
    style.textContent =
      '#hvt-alert-popup[hidden]{display:none}' +
      '#hvt-alert-popup{position:fixed;inset:0;z-index:1200}' +
      '.hvt-alert-popup__backdrop{position:absolute;inset:0;background:rgba(20,16,12,.42);backdrop-filter:blur(4px)}' +
      '.hvt-alert-popup__panel{position:relative;max-width:430px;margin:min(14vh,120px) auto 0;background:#f4f1eb;color:#1f1b17;border:1px solid #d5cbbc;box-shadow:0 26px 90px rgba(34,28,22,.18);padding:24px 22px 22px}' +
      '.hvt-alert-popup__close{position:absolute;top:10px;right:10px;border:none;background:none;color:#6f665d;font:400 24px/1 "IBM Plex Mono",ui-monospace,Menlo,monospace;cursor:pointer}' +
      '.hvt-alert-popup__close:hover{color:#c67c6d}' +
      '.hvt-alert-popup__eyebrow{margin-bottom:10px;color:#c67c6d;font:11px "IBM Plex Mono",ui-monospace,Menlo,monospace;text-transform:uppercase;letter-spacing:.08em}' +
      '.hvt-alert-popup__panel h2{margin:0 0 10px;font:700 28px/1.08 "Hanken Grotesk",system-ui,-apple-system,sans-serif;letter-spacing:-.03em}' +
      '.hvt-alert-popup__copy{margin:0 0 16px;color:#6f665d;font:14px/1.6 "Hanken Grotesk",system-ui,-apple-system,sans-serif}' +
      '.hvt-alert-popup__form{display:grid;gap:10px}' +
      '.hvt-alert-popup__form label{font:600 13px/1.4 "Hanken Grotesk",system-ui,-apple-system,sans-serif}' +
      '.hvt-alert-popup__form input{width:100%;padding:12px 13px;border:1px solid #d5cbbc;background:#fff;color:#1f1b17;font:14px "Hanken Grotesk",system-ui,-apple-system,sans-serif;outline:none}' +
      '.hvt-alert-popup__form input:focus{border-color:#b05a3a}' +
      '.hvt-alert-popup__actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:4px}' +
      '.hvt-alert-popup__actions button{border:1px solid #d5cbbc;background:#fff;color:#1f1b17;padding:11px 14px;cursor:pointer;font:700 12px "IBM Plex Mono",ui-monospace,Menlo,monospace}' +
      '.hvt-alert-popup__actions button:hover{border-color:#c67c6d;color:#c67c6d}' +
      '.hvt-alert-popup__actions .secondary{background:#ece4d6;color:#6f665d}' +
      '.hvt-alert-popup__status{min-height:18px;color:#6f665d;font:12px/1.5 "IBM Plex Mono",ui-monospace,Menlo,monospace}' +
      '.hvt-alert-popup__status.is-error{color:#9b3c3c}' +
      '.hvt-alert-popup__status.is-success{color:#2f6846}' +
      '@media (max-width:640px){.hvt-alert-popup__panel{margin:24px 16px 0;padding:22px 18px 18px}.hvt-alert-popup__panel h2{font-size:24px}}';

    document.head.appendChild(style);
    document.body.appendChild(overlay);
    return overlay;
  }

  function markAlertPopupDismissed(reason) {
    writePopupState({
      dismissed_at: nowIso(),
      submitted_at: readPopupState().submitted_at || null,
      reason: reason || "dismissed"
    });
  }

  function setupAlertPopup() {
    if (!shouldShowAlertPopup()) return;

    var popup = buildAlertPopup();
    if (!popup) return;

    var dismissed = false;
    var form = document.getElementById("hvt-alert-popup-form");
    var status = document.getElementById("hvt-alert-popup-status");
    var emailInput = document.getElementById("hvt-alert-popup-email");

    function closePopup(reason) {
      if (dismissed) return;
      popup.setAttribute("hidden", "hidden");
      popup.classList.remove("is-open");
      document.body.classList.remove("hvt-alert-popup-open");
      markAlertPopupDismissed(reason);
      dismissed = true;
    }

    function showPopup() {
      if (dismissed) return;
      popup.removeAttribute("hidden");
      popup.classList.add("is-open");
      document.body.classList.add("hvt-alert-popup-open");
      if (typeof emailInput.focus === "function") emailInput.focus();
      if (typeof window.hvtTrack === "function") {
        window.hvtTrack("alert_popup_view", {});
      }
    }

    popup.addEventListener("click", function (event) {
      var action = event.target && event.target.getAttribute("data-alert-close");
      if (!action) return;
      if (typeof window.hvtTrack === "function") {
        window.hvtTrack("alert_popup_dismiss", { dismiss_source: action });
      }
      closePopup(action);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !popup.hasAttribute("hidden")) {
        if (typeof window.hvtTrack === "function") {
          window.hvtTrack("alert_popup_dismiss", { dismiss_source: "escape" });
        }
        closePopup("escape");
      }
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      status.textContent = "Saving...";
      status.className = "hvt-alert-popup__status";

      var payload = new URLSearchParams();
      payload.set("email", emailInput.value.trim());

      fetch("/alerts", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded"
        },
        body: payload.toString()
      }).then(function (response) {
        if (!response.ok) throw new Error("request_failed");
        writePopupState({
          dismissed_at: readPopupState().dismissed_at || null,
          submitted_at: nowIso(),
          reason: "submitted"
        });
        dismissed = true;
        status.textContent = "You're on the list.";
        status.className = "hvt-alert-popup__status is-success";
        form.innerHTML =
          '<p class="hvt-alert-popup__status is-success">You\'re on the list.</p>' +
          '<p class="hvt-alert-popup__copy">I\'ll reach out when trust alerts are ready.</p>';
        if (typeof window.hvtTrack === "function") {
          window.hvtTrack("alert_popup_submit", {});
        }
        window.setTimeout(function () {
          popup.setAttribute("hidden", "hidden");
          document.body.classList.remove("hvt-alert-popup-open");
        }, 1400);
      }).catch(function () {
        status.textContent = "Could not save right now. Please try again from the Alerts page.";
        status.className = "hvt-alert-popup__status is-error";
      });
    });

    window.setTimeout(showPopup, 18000);
  }

  captureAttribution();
  if (typeof window.gtag === "function") {
    window.hvtTrack("hvt_pageview", {
      page_location: window.location.href,
      page_title: document.title
    });
  }
  setupAlertPopup();

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
