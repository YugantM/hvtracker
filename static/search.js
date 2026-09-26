// Header search on every page (the homepage keeps its leaderboard search).
// The index loads on first use from /data/search-index.json: one compact row
// per listing, edge-cached, so nothing is fetched until someone searches.
// Without JS the form still submits to /?q=, which the leaderboard honours.
(function () {
  "use strict";
  var box = document.getElementById("hdr-search");
  var input = document.getElementById("hdr-q");
  var list = document.getElementById("hdr-results");
  var btn = document.querySelector(".hdr-search-btn");
  if (!box || !input || !list) return;
  var header = box.closest(".site-header") || document.body;
  var rows = null, loading = null, active = -1, shown = [];

  function load() {
    if (rows) return Promise.resolve(rows);
    if (!loading) {
      loading = fetch("/data/search-index.json")
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (d) {
          rows = (d.rows || []).map(function (r) {
            return { name: r[0], slug: r[1], repo: r[2], category: r[3], score: r[4], grade: r[5],
                     hay: (r[0] + " " + r[2] + " " + r[1]).toLowerCase() };
          });
          return rows;
        })
        .catch(function () { loading = null; return []; });
    }
    return loading;
  }

  // Best first: exact name/slug, then name prefix, then a word in the name
  // starting with the query, then anywhere in name/repo; score breaks ties.
  function rank(q) {
    var terms = q.split(/\s+/).filter(Boolean);
    var out = [];
    rows.forEach(function (r) {
      for (var i = 0; i < terms.length; i++) if (r.hay.indexOf(terms[i]) < 0) return;
      var name = r.name.toLowerCase(), tier = 4;
      if (name === q || r.slug === q) tier = 0;
      else if (name.indexOf(q) === 0) tier = 1;
      else if ((" " + name).indexOf(" " + terms[0]) >= 0) tier = 2;
      else if (name.indexOf(terms[0]) >= 0) tier = 3;
      out.push([tier, -(r.score || 0), r]);
    });
    out.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
    return out.map(function (x) { return x[2]; });
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function option(href, grade, name, sub, score, i) {
    var a = el("a");
    a.href = href;
    a.id = "hdr-opt-" + i;
    a.setAttribute("role", "option");
    a.appendChild(el("span", grade ? "badge grade-" + grade : "badge r-pend", grade || "–"));
    var mid = el("span");
    mid.appendChild(el("span", "r-name", name));
    mid.appendChild(el("span", "r-sub", sub));
    a.appendChild(mid);
    a.appendChild(el("span", "r-score", score == null ? "" : String(score)));
    return a;
  }

  function render(q) {
    list.textContent = "";
    shown = [];
    active = -1;
    input.removeAttribute("aria-activedescendant");
    if (!q) { close(); return; }
    var vs = q.match(/^(.+?)\s+vs\.?\s+(.+)$/);
    if (vs) {
      var a = rank(vs[1].trim())[0], b = rank(vs[2].trim())[0];
      if (a && b && a.slug !== b.slug) {
        shown.push({ href: "/compare/?a=" + encodeURIComponent(a.slug) + "&b=" + encodeURIComponent(b.slug) });
        list.appendChild(option(shown[0].href, null, a.name + " vs " + b.name,
                                "Compare side by side", null, 0));
      }
    }
    rank(q).slice(0, 8 - shown.length).forEach(function (r) {
      var href = "/agents/" + r.slug + "/";
      list.appendChild(option(href, r.grade, r.name, r.category + " · " + r.repo, r.score, shown.length));
      shown.push({ href: href });
    });
    if (!shown.length) list.appendChild(el("div", "r-empty", "No tracked listing matches “" + q + "”."));
    var foot = el("div", "r-foot");
    foot.appendChild(el("span", null, "↑↓ move"));
    foot.appendChild(el("span", null, "↵ open"));
    foot.appendChild(el("span", null, "“a vs b” to compare"));
    list.appendChild(foot);
    list.hidden = false;
    input.setAttribute("aria-expanded", "true");
  }

  function move(step) {
    if (!shown.length) return;
    var opts = list.querySelectorAll("[role=option]");
    if (active >= 0) opts[active].removeAttribute("aria-selected");
    active = (active + step + shown.length) % shown.length;
    opts[active].setAttribute("aria-selected", "true");
    input.setAttribute("aria-activedescendant", opts[active].id);
  }

  function go(i) {
    var hit = shown[i];
    if (!hit) return false;
    if (window.hvtTrack) window.hvtTrack("header_search", { query_length: input.value.trim().length, result_index: i });
    location.href = hit.href;
    return true;
  }

  function close() {
    list.hidden = true;
    input.setAttribute("aria-expanded", "false");
  }

  function setOpen(open) {  // phones: the icon button shows the search row
    header.classList.toggle("search-open", open);
    if (btn) btn.setAttribute("aria-expanded", String(open));
    if (open) { load(); input.focus(); } else close();
  }

  var timer = null;
  input.addEventListener("focus", function () { load(); });
  input.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(function () {
      var q = input.value.trim().toLowerCase();
      load().then(function () { render(q); });
    }, 80);
  });
  input.addEventListener("keydown", function (e) {
    if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
    else if (e.key === "Enter") { if (go(active >= 0 ? active : 0)) e.preventDefault(); }
    else if (e.key === "Escape") { input.value = ""; close(); input.blur(); setOpen(false); }
  });
  document.addEventListener("click", function (e) {
    if (!box.contains(e.target) && !(btn && btn.contains(e.target))) close();
  });
  if (btn) btn.addEventListener("click", function () { setOpen(!header.classList.contains("search-open")); });

  // "/" or ⌘K / Ctrl+K from anywhere that isn't already a text field.
  document.addEventListener("keydown", function (e) {
    var t = e.target, typing = t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));
    if (((e.metaKey || e.ctrlKey) && e.key === "k") || (e.key === "/" && !typing)) {
      if (typing && t === input) return;
      e.preventDefault();
      if (btn && getComputedStyle(btn).display !== "none") setOpen(true);
      else { input.focus(); input.select(); }
    }
  });
})();
