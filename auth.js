/* HVTracker accounts widget: sign-in / account menu, notifications bell, and
   tracked-projects sync. Progressive enhancement — if the API is unavailable
   (e.g. no DB locally) it silently no-ops and the public site is unaffected. */
(function () {
  "use strict";
  var WATCHLIST_KEY = "hvtracker_watchlist_v1";

  function api(path, opts) {
    return fetch(path, Object.assign({ credentials: "same-origin" }, opts || {}))
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r); });
  }
  function postJSON(path, body) {
    return api(path, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}) });
  }

  // Exposed so the inline tracked-projects toggles (homepage + agent pages) can
  // sync add/remove to the signed-in account. Harmless when logged out (401).
  window.hvtSyncWatch = function (action, slug) {
    if (!action || !slug) return;
    postJSON("/api/watchlist", { action: action, slug: slug }).catch(function () {});
  };

  // Compare list — a SEPARATE local list (max 3) from the tracked-projects list.
  // Used by the "Add to compare" buttons and read by the compare tool.
  window.hvtCompare = {
    KEY: "hvtracker_compare_v1",
    MAX: 3,
    get: function () { try { return JSON.parse(localStorage.getItem(this.KEY) || "[]") || []; } catch (e) { return []; } },
    set: function (list) { localStorage.setItem(this.KEY, JSON.stringify(list.slice(0, this.MAX))); },
    slugs: function () { return this.get().map(function (i) { return i.slug || i; }); },
    has: function (slug) { return this.slugs().indexOf(slug) >= 0; },
    full: function () { return this.get().length >= this.MAX; },
    toggle: function (item) {
      var list = this.get(), s = item.slug;
      if (this.has(s)) list = list.filter(function (i) { return (i.slug || i) !== s; });
      else if (list.length < this.MAX) list = list.concat([{ slug: s, name: item.name, repo: item.repo }]);
      this.set(list);
      renderCompareTray();
      return this.get();
    },
    url: function () { var s = this.slugs(); return s.length ? "/compare/?a=" + s.join(",") : "/compare/"; }
  };

  // Floating "Compare (N)" tray — appears on any page (except the compare tool
  // itself) whenever the compare list is non-empty.
  function renderCompareTray() {
    if (/^\/compare\//.test(location.pathname)) return;
    var n = window.hvtCompare.slugs().length;
    var tray = document.getElementById("hvt-compare-tray");
    if (!tray) {
      tray = document.createElement("a");
      tray.id = "hvt-compare-tray";
      document.body.appendChild(tray);
    }
    tray.href = window.hvtCompare.url();
    tray.innerHTML = "⇄ Compare <strong>" + n + "</strong> →";
    tray.hidden = n === 0;
  }
  function loginUrl(provider) {
    return "/auth/" + provider + "/login?next=" + encodeURIComponent(location.pathname + location.search);
  }
  function toggle(id) {
    var e = document.getElementById(id);
    if (e) e.hidden = !e.hidden;
  }
  function esc(s) { return (s == null ? "" : String(s)).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  injectStyles();
  var slot = document.getElementById("hvt-auth-slot");

  api("/api/me").then(function (me) {
    if (me.logged_in) renderLoggedIn(me.user); else renderLoggedOut(me);
  }).catch(function () { /* auth disabled — leave the public UI untouched */ });

  initAccountPage();
  renderCompareTray();

  // ---- /account page: remove-from-watchlist buttons ----
  function initAccountPage() {
    var btns = document.querySelectorAll(".account-remove");
    if (!btns.length) return;
    [].forEach.call(btns, function (btn) {
      btn.addEventListener("click", function () {
        var slug = btn.getAttribute("data-remove-slug");
        btn.disabled = true; btn.textContent = "Removing…";
        postJSON("/api/watchlist", { action: "remove", slug: slug }).then(function () {
          var li = btn.closest("li"); if (li && li.parentNode) li.parentNode.removeChild(li);
          var cnt = document.querySelector("#watchlist .account-count");
          if (cnt) cnt.textContent = Math.max(0, (parseInt(cnt.textContent, 10) || 1) - 1);
        }).catch(function () { btn.disabled = false; btn.textContent = "Remove"; });
      });
    });
  }

  // ---- header: signed out ----
  function renderLoggedOut(me) {
    if (!slot) return;
    var providers = (me && me.providers) || [];
    var canSignIn = providers.length || (me && me.dev_login);
    if (!canSignIn) { slot.innerHTML = ""; return; }  // no sign-in method -> show nothing publicly
    // Link to the real /login page rather than a cramped dropdown.
    slot.innerHTML = '<a class="hvt-auth-btn hvt-auth-signin" href="/login?next=' +
      encodeURIComponent(location.pathname + location.search) + '">Sign in</a>';
  }

  // ---- header: signed in ----
  function renderLoggedIn(user) {
    if (!slot) return;
    var avatar = user.avatar_url ? '<img class="hvt-auth-avatar" src="' + esc(user.avatar_url) + '" alt="">' : "";
    slot.innerHTML = '<div class="hvt-auth">' +
      '<button class="hvt-bell" id="hvtBell" title="Notifications" aria-label="Notifications">◉' +
        '<span class="hvt-bell-count" id="hvtBellCount" hidden>0</span></button>' +
      '<button class="hvt-auth-btn" id="hvtAcct">' + avatar + "<span>" + esc(user.login || user.name || "Account") + "</span></button>" +
      '<div class="hvt-auth-pop" id="hvtAcctPop" hidden>' +
        '<a class="hvt-auth-item" href="/account/">Your account</a>' +
        '<a class="hvt-auth-item" href="/account/#watchlist">Tracked projects</a>' +
        '<button class="hvt-auth-item" id="hvtLogout">Sign out</button></div>' +
      '<div class="hvt-auth-pop hvt-notif" id="hvtNotifPop" hidden>' +
        '<div class="hvt-notif-head">Trust activity on your tracked projects</div>' +
        '<div id="hvtNotifList" class="hvt-notif-list"><div class="hvt-notif-empty">Loading…</div></div></div>' +
      "</div>";
    document.getElementById("hvtAcct").addEventListener("click", function () { toggle("hvtAcctPop"); });
    document.getElementById("hvtLogout").addEventListener("click", logout);
    document.getElementById("hvtBell").addEventListener("click", function () { toggle("hvtNotifPop"); markRead(); });
    syncWatchlist();
    loadNotifications();
  }

  function logout() {
    // Real form POST -> server clears the cookie and 303-redirects home.
    var f = document.createElement("form");
    f.method = "post"; f.action = "/auth/logout";
    var n = document.createElement("input");
    n.type = "hidden"; n.name = "next"; n.value = "/";
    f.appendChild(n); document.body.appendChild(f); f.submit();
  }

  // ---- watchlist: merge the anonymous localStorage list into the account once ----
  function syncWatchlist() {
    if (sessionStorage.getItem("hvt_wl_synced")) return;
    var slugs = [];
    try {
      var raw = JSON.parse(localStorage.getItem(WATCHLIST_KEY) || "[]");
      slugs = (raw || []).map(function (i) { return i && i.slug ? i.slug : i; }).filter(Boolean);
    } catch (e) { slugs = []; }
    sessionStorage.setItem("hvt_wl_synced", "1");
    if (slugs.length) postJSON("/api/watchlist", { action: "sync", slugs: slugs }).catch(function () {});
  }

  // ---- notifications ----
  function loadNotifications() {
    api("/api/notifications").then(function (data) {
      var c = document.getElementById("hvtBellCount");
      if (c) { if (data.unread > 0) { c.textContent = data.unread > 9 ? "9+" : data.unread; c.hidden = false; } else c.hidden = true; }
      var list = document.getElementById("hvtNotifList");
      if (!list) return;
      if (!data.items || !data.items.length) {
        list.innerHTML = '<div class="hvt-notif-empty">' +
          (data.watching ? "No recent changes on your watched agents." :
           'Track agents to get trust-change alerts here.') + "</div>";
        return;
      }
      list.innerHTML = data.items.map(function (n) {
        return '<a class="hvt-notif-item' + (n.unread ? " is-unread" : "") + '" href="/agents/' + esc(n.slug) + '/">' +
          '<span class="hvt-notif-name">' + esc(n.name) + "</span>" +
          '<span class="hvt-notif-detail">' + esc(n.detail || n.label || "") + "</span>" +
          '<span class="hvt-notif-date">' + esc(n.date) + "</span></a>";
      }).join("");
    }).catch(function () {});
  }
  function markRead() {
    postJSON("/api/notifications/read").then(function () {
      var c = document.getElementById("hvtBellCount"); if (c) c.hidden = true;
    }).catch(function () {});
  }

  // ---- styles (scoped, theme-matched) ----
  function injectStyles() {
    if (document.getElementById("hvt-auth-style")) return;
    var s = document.createElement("style");
    s.id = "hvt-auth-style";
    s.textContent =
      ".hvt-auth-slot{display:inline-flex;align-items:center}.hvt-auth-slot:empty{display:none}" +
      "#hvt-compare-tray{position:fixed;bottom:18px;right:18px;z-index:1200;background:var(--accent,#2c5282);color:#fff;border:1px solid var(--accent,#2c5282);padding:10px 16px;font-family:var(--font-mono,ui-monospace,Menlo,monospace);font-size:13px;box-shadow:0 10px 30px rgba(34,28,22,.25);text-decoration:none}" +
      "#hvt-compare-tray[hidden]{display:none}#hvt-compare-tray:hover{filter:brightness(1.08);text-decoration:none}#hvt-compare-tray strong{font-weight:700}" +
      ".hvt-auth{position:relative;display:inline-flex;align-items:center;gap:8px;font-family:var(--font-mono,ui-monospace,Menlo,monospace);font-size:12px}" +
      ".hvt-auth-btn,.hvt-bell{display:inline-flex;align-items:center;gap:6px;cursor:pointer;background:#fff;border:1px solid var(--border,#d5cbbc);color:var(--text,#1f1b17);padding:5px 10px;border-radius:0;font:inherit}" +
      ".hvt-auth-btn:hover,.hvt-bell:hover{border-color:var(--accent-warm,#c67c6d);color:var(--accent-warm,#c67c6d)}" +
      ".hvt-auth-avatar{width:18px;height:18px;border-radius:50%;object-fit:cover}" +
      ".hvt-bell{position:relative;padding:5px 8px}" +
      ".hvt-bell-count{position:absolute;top:-6px;right:-6px;background:var(--accent-warm,#c67c6d);color:#fff;border-radius:9px;padding:0 5px;font-size:10px;line-height:16px;min-width:16px;text-align:center}" +
      ".hvt-auth-pop{position:absolute;top:calc(100% + 6px);right:0;min-width:220px;background:#fff;border:1px solid var(--border,#d5cbbc);box-shadow:0 18px 50px rgba(34,28,22,.16);z-index:1100;display:flex;flex-direction:column}" +
      ".hvt-auth-pop[hidden]{display:none}" +
      ".hvt-auth-item{display:block;padding:10px 12px;color:var(--text,#1f1b17);text-decoration:none;border:0;background:none;text-align:left;cursor:pointer;font:inherit;border-bottom:1px solid var(--border,#eee)}" +
      ".hvt-auth-item:last-child{border-bottom:0}.hvt-auth-item:hover{background:#f4f1eb;color:var(--accent-warm,#c67c6d)}" +
      ".hvt-auth-muted{color:#9a9189;cursor:default}" +
      ".hvt-notif{min-width:320px;max-width:380px}" +
      ".hvt-notif-head{padding:10px 12px;border-bottom:1px solid var(--border,#eee);color:#6f665d;text-transform:uppercase;letter-spacing:.06em;font-size:10px}" +
      ".hvt-notif-list{max-height:340px;overflow:auto}" +
      ".hvt-notif-empty{padding:14px 12px;color:#6f665d}" +
      ".hvt-notif-item{display:grid;gap:2px;padding:10px 12px;border-bottom:1px solid var(--border,#eee);text-decoration:none;color:var(--text,#1f1b17)}" +
      ".hvt-notif-item:hover{background:#f4f1eb}.hvt-notif-item.is-unread{background:#fbf6ee}" +
      ".hvt-notif-name{font-weight:700}.hvt-notif-detail{color:#4a443d}.hvt-notif-date{color:#9a9189;font-size:10px}" +
      "";
    document.head.appendChild(s);
  }
})();
