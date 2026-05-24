"""
Specification definitions for HVTracker.
Each spec is a dict consumed by the Jinja2 spec.html.j2 template.
The `body` field is raw HTML rendered directly into the spec document.
"""

METHODOLOGY_V2 = {
    "title": "HVTracker Methodology Specification",
    "slug": "methodology",
    "version": "v2.0",
    "status": "Published",
    "date": "2026-05-24",
    "authors": ["HVTracker"],
    "abstract": (
        "This document defines the measurement methodology used by HVTracker "
        "to compute health scores and supply chain trust signals for open-source "
        "AI agent projects. It specifies the data sources, scoring formula, "
        "provenance signal collection procedures, and update cadence. "
        "Implementations conforming to this specification MUST produce scores "
        "within 0.1 points of the reference implementation given identical inputs."
    ),
    "sections": [
        {"id": "s1", "num": "1.", "title": "Abstract"},
        {"id": "s2", "num": "2.", "title": "Terminology"},
        {"id": "s3", "num": "3.", "title": "Scope and Applicability"},
        {"id": "s4", "num": "4.", "title": "Data Sources",
         "subsections": [
             {"id": "s4-1", "num": "4.1", "title": "GitHub REST API"},
             {"id": "s4-2", "num": "4.2", "title": "npm Registry"},
             {"id": "s4-3", "num": "4.3", "title": "PyPI"},
             {"id": "s4-4", "num": "4.4", "title": "Hacker News"},
         ]},
        {"id": "s5", "num": "5.", "title": "Health Score Formula",
         "subsections": [
             {"id": "s5-1", "num": "5.1", "title": "Stars Component"},
             {"id": "s5-2", "num": "5.2", "title": "Freshness Component"},
             {"id": "s5-3", "num": "5.3", "title": "Activity Component"},
             {"id": "s5-4", "num": "5.4", "title": "Community Component"},
         ]},
        {"id": "s6", "num": "6.", "title": "Supply Chain Trust Signals",
         "subsections": [
             {"id": "s6-1", "num": "6.1", "title": "npm Provenance"},
             {"id": "s6-2", "num": "6.2", "title": "PyPI Provenance (PEP 740)"},
             {"id": "s6-3", "num": "6.3", "title": "OSSF Scorecard"},
             {"id": "s6-4", "num": "6.4", "title": "Signed Commit Ratio"},
         ]},
        {"id": "s7", "num": "7.", "title": "Update Process and Cadence"},
        {"id": "s8", "num": "8.", "title": "Agent Eligibility"},
        {"id": "s9", "num": "9.", "title": "Versioning"},
    ],
    "appendices": [
        {"id": "app-a", "num": "A.", "title": "Reference Implementation"},
        {"id": "app-b", "num": "B.", "title": "Changelog"},
    ],
    "body": """
<h2 id="s1"><span class="sec-num">1.</span> Abstract</h2>
<p>This document defines the measurement methodology used by HVTracker to compute health scores and supply chain trust signals for open-source AI agent projects. It specifies the data sources, scoring formula, provenance signal collection procedures, and update cadence.</p>
<p>Implementations conforming to this specification <span class="must">MUST</span> produce scores within 0.1 points of the reference implementation given identical inputs. The scoring formula is deterministic given its inputs; variation may arise only from differences in API response timing.</p>
<p>The key words <span class="must">MUST</span>, <span class="must">MUST NOT</span>, <span class="should">SHOULD</span>, <span class="should">SHOULD NOT</span>, and <span class="may">MAY</span> in this document are to be interpreted as described in <a href="https://www.rfc-editor.org/rfc/rfc2119" target="_blank" rel="noopener">RFC 2119</a>.</p>

<h2 id="s2"><span class="sec-num">2.</span> Terminology</h2>
<dl>
  <dt>Agent</dt>
  <dd>An open-source software project, tracked by HVTracker, that implements or supports autonomous AI agent behavior. Agents <span class="must">MUST</span> be open-source (see Section 8).</dd>
  <dt>Health Score</dt>
  <dd>A scalar value in the range [0, 100] representing the composite activity and adoption health of an agent, computed according to Section 5.</dd>
  <dt>Provenance Signal</dt>
  <dd>A binary or scalar value derived from public cryptographic infrastructure indicating the supply chain trustworthiness of an agent's release artifacts (see Section 6).</dd>
  <dt>Reference Implementation</dt>
  <dd>The canonical Python implementation at <a href="https://github.com/YugantM/hvtracker/blob/main/fetch_and_build.py" target="_blank" rel="noopener">fetch_and_build.py</a> in the HVTracker repository.</dd>
  <dt>Snapshot</dt>
  <dd>A complete JSON export of the leaderboard state at a single point in time, archived to <code>output/history/YYYY-MM-DD.json</code>.</dd>
  <dt>Daily Run</dt>
  <dd>One execution of the reference implementation, producing a new Snapshot and updating all output files.</dd>
</dl>

<h2 id="s3"><span class="sec-num">3.</span> Scope and Applicability</h2>
<p>This specification governs the production HVTracker leaderboard at <a href="https://hvtracker.net">hvtracker.net</a> and any conforming implementations that wish to replicate or extend it.</p>
<p>This specification does <em>not</em> govern:</p>
<ul>
  <li>Runtime correctness benchmarks or task-completion evaluations.</li>
  <li>Closed-source or proprietary AI agent products.</li>
  <li>Agents not listed in the reference <code>agents.json</code> registry.</li>
</ul>
<p>All signals defined in this specification are unilaterally observable from public APIs. No maintainer participation, registration, or opt-in is required or assumed.</p>

<h2 id="s4"><span class="sec-num">4.</span> Data Sources</h2>
<p>All data <span class="must">MUST</span> be fetched from the public APIs listed in this section. Authenticated requests <span class="should">SHOULD</span> use a GitHub personal access token to raise the rate limit from 60 to 5,000 requests per hour.</p>

<h3 id="s4-1"><span class="sec-num">4.1</span> GitHub REST API</h3>
<p><strong>Base URL:</strong> <code>https://api.github.com</code></p>
<p>The following endpoints are used per agent:</p>
<table class="spec-table">
  <thead><tr><th>Endpoint</th><th>Fields consumed</th><th>Notes</th></tr></thead>
  <tbody>
    <tr><td><code>GET /repos/{owner}/{repo}</code></td><td><code>stargazers_count</code>, <code>forks_count</code>, <code>pushed_at</code>, <code>description</code>, <code>language</code>, <code>open_issues_count</code></td><td>Primary metadata fetch</td></tr>
    <tr><td><code>GET /repos/{owner}/{repo}/stats/commit_activity</code></td><td>Weekly commit totals, last 52 weeks</td><td>Returns HTTP 202 while computing; implementation <span class="must">MUST</span> retry up to 3 times with exponential backoff</td></tr>
    <tr><td><code>GET /repos/{owner}/{repo}/commits</code></td><td><code>verification.verified</code> on each commit</td><td>Used for signed commit ratio (Section 6.4); sample of last 100 commits</td></tr>
  </tbody>
</table>
<p>Commit activity for the last four weeks is computed as the sum of the <code>total</code> field across the last four elements of the commit activity array. If the Stats API returns an empty array, the implementation <span class="must">MUST</span> fall back to the Commits API with a <code>since</code> parameter of 30 days prior.</p>

<h3 id="s4-2"><span class="sec-num">4.2</span> npm Registry</h3>
<p><strong>Download counts:</strong> <code>https://api.npmjs.org/downloads/point/last-week/{package}</code></p>
<p><strong>Provenance:</strong> <code>https://registry.npmjs.org/{package}/latest</code> — field <code>dist.attestations</code></p>
<p>Only agents with a non-empty <code>npm_package</code> field in <code>agents.json</code> are queried. npm API requests <span class="may">MAY</span> be made in parallel; the npm API does not publish a strict rate limit for anonymous reads.</p>

<h3 id="s4-3"><span class="sec-num">4.3</span> PyPI</h3>
<p><strong>Download counts:</strong> <code>https://pypistats.org/api/packages/{package}/recent</code> — field <code>data.last_week</code></p>
<p>PyPI stats requests <span class="must">MUST</span> be made serially with a minimum 1.2-second delay between requests. On HTTP 429, the implementation <span class="must">MUST</span> fall back to the cached value from the most recent prior Snapshot.</p>
<p><strong>Provenance:</strong> <code>https://pypi.org/simple/{package}/</code> with <code>Accept: application/vnd.pypi.simple.v1+json</code> — field <code>files[-1].provenance</code>. A non-null value indicates a PEP 740 attestation is present on the latest release file.</p>

<h3 id="s4-4"><span class="sec-num">4.4</span> Hacker News</h3>
<p><strong>API:</strong> Algolia HN Search — <code>https://hn.algolia.com/api/v1/search</code></p>
<p>Story mentions are counted over the last 30 days using a per-agent <code>hn_search_term</code> configured in <code>agents.json</code>. Agents without an <code>hn_search_term</code> receive a null value. The Algolia API allows 10,000 requests per hour; a 0.3-second sleep <span class="should">SHOULD</span> be applied between requests as a courtesy.</p>

<h2 id="s5"><span class="sec-num">5.</span> Health Score Formula</h2>
<p>The health score is a real number in [0, 100], computed as the sum of four components. All components are non-negative and bounded by their respective maxima.</p>
<pre>score = stars_score + freshness_score + activity_score + community_score</pre>
<p>The score is rounded to one decimal place for display.</p>

<h3 id="s5-1"><span class="sec-num">5.1</span> Stars Component</h3>
<p><strong>Maximum: 30 points</strong></p>
<pre>stars_score = min(30, ln(1 + stars) / ln(1 + 100_000) × 30)</pre>
<p>Log-scaled against a fixed anchor of 100,000 stars. A project with 100,000 stars earns the full 30 points. Log scaling prevents megarepos from dominating the leaderboard linearly.</p>

<h3 id="s5-2"><span class="sec-num">5.2</span> Freshness Component</h3>
<p><strong>Maximum: 25 points</strong></p>
<pre>days_since = (now_utc - pushed_at).days
freshness_score = max(0.0, 25 × (1 − days_since / 180))</pre>
<p>Linear decay to zero over 180 days of inactivity. A push today earns the full 25 points. A push 180 or more days ago earns 0 points.</p>

<h3 id="s5-3"><span class="sec-num">5.3</span> Activity Component</h3>
<p><strong>Maximum: 25 points</strong></p>
<pre>activity_score = min(25, ln(1 + commits_4wk) / ln(1 + 100) × 25)</pre>
<p>Where <code>commits_4wk</code> is the sum of commits in the last four weeks per Section 4.1. Log-scaled; 100 commits in four weeks earns the full 25 points.</p>

<h3 id="s5-4"><span class="sec-num">5.4</span> Community Component</h3>
<p><strong>Maximum: 20 points</strong></p>
<pre>community_score = min(20, ln(1 + forks) / ln(1 + 20_000) × 20)</pre>
<p>Fork count as a proxy for downstream reuse. Log-scaled against 20,000 forks.</p>

<div class="note">
  <strong>Non-score signals:</strong> Download counts (npm/PyPI), Hacker News mentions, and all supply chain trust signals (Section 6) are collected and displayed but are <strong>not</strong> incorporated into the composite health score in this version. They are reported independently.
</div>

<h2 id="s6"><span class="sec-num">6.</span> Supply Chain Trust Signals</h2>
<p>Supply chain trust signals are independently observable boolean or scalar values derived from public cryptographic infrastructure. They <span class="must">MUST NOT</span> affect the health score. They <span class="must">MUST</span> be collected on every Daily Run and stored in the Snapshot.</p>
<p>All signals are unilaterally observable. No maintainer action is required for a signal to be collected.</p>

<h3 id="s6-1"><span class="sec-num">6.1</span> npm Provenance</h3>
<p><strong>Field:</strong> <code>npm_provenance</code> (boolean or null)</p>
<p><strong>Source:</strong> <code>https://registry.npmjs.org/{package}/latest</code></p>
<p><strong>Signal:</strong> <code>true</code> if the response body contains a non-null <code>dist.attestations</code> field; <code>false</code> if the field is absent or null; <code>null</code> if the agent has no <code>npm_package</code> configured or the request fails.</p>
<p><strong>Interpretation:</strong> A <code>true</code> value indicates the latest published version includes an in-toto SLSA provenance attestation signed via Sigstore and logged to the Rekor transparency log.</p>
<p><strong>Limitation:</strong> Only the latest version is checked. Historical versions are not evaluated.</p>

<h3 id="s6-2"><span class="sec-num">6.2</span> PyPI Provenance (PEP 740)</h3>
<p><strong>Field:</strong> <code>pypi_provenance</code> (boolean or null)</p>
<p><strong>Source:</strong> <code>https://pypi.org/simple/{package}/</code> with <code>Accept: application/vnd.pypi.simple.v1+json</code></p>
<p><strong>Signal:</strong> <code>true</code> if the last file entry in the <code>files</code> array has a non-null <code>provenance</code> field; <code>false</code> if absent; <code>null</code> if no <code>pypi_package</code> is configured or the request fails.</p>
<p><strong>Interpretation:</strong> A <code>true</code> value indicates the latest release was published via a Trusted Publisher and carries a PEP 740 digital attestation, generated by the PyPA GitHub Actions publishing workflow.</p>
<p><strong>Limitation:</strong> Packages published via <code>twine</code> with API tokens will not have PEP 740 attestations regardless of build pipeline quality.</p>

<h3 id="s6-3"><span class="sec-num">6.3</span> OSSF Scorecard</h3>
<p><strong>Fields:</strong> <code>scorecard_score</code> (float 0–10 or null), <code>scorecard_checks</code> (object mapping check name to score)</p>
<p><strong>Source:</strong> <code>https://api.deps.dev/v3/projects/github.com%2F{owner}%2F{repo}</code></p>
<p><strong>Signal:</strong> The <code>scorecard.overallScore</code> field from the deps.dev project response, plus all individual check scores from <code>scorecard.checks</code>.</p>
<p><strong>Interpretation:</strong> The OpenSSF Scorecard evaluates security posture across checks including: Maintained, Code-Review, Branch-Protection, Signed-Releases, Pinned-Dependencies, Vulnerabilities, Token-Permissions, Dangerous-Workflow, and others. A score of 10 is the maximum.</p>
<p><strong>Limitation:</strong> Not all repositories have Scorecard coverage in deps.dev. Absence of a score does not imply poor security posture.</p>

<h3 id="s6-4"><span class="sec-num">6.4</span> Signed Commit Ratio</h3>
<p><strong>Field:</strong> <code>signed_commits_ratio</code> (float 0.0–1.0 or null)</p>
<p><strong>Source:</strong> <code>GET /repos/{owner}/{repo}/commits?per_page=100</code> — field <code>commit.verification.verified</code> on each result</p>
<p><strong>Signal:</strong> <code>verified_count / total_count</code> across up to 100 most recent commits on the default branch. <code>null</code> if the API request fails.</p>
<p><strong>Interpretation:</strong> The fraction of recent commits carrying a verified GPG, SSH, or S/MIME signature as reported by GitHub's signature verification API.</p>
<p><strong>Limitation:</strong> Web-based commits made through GitHub's UI are signed by GitHub's own key and counted as verified, which may inflate the ratio for projects that accept many web-based edits. This signal measures signature <em>presence</em>, not signature quality or key trust level.</p>

<h2 id="s7"><span class="sec-num">7.</span> Update Process and Cadence</h2>
<p>The reference implementation <span class="must">MUST</span> execute at least once per calendar day. The production deployment runs at <strong>06:00 UTC</strong> daily via GitHub Actions.</p>
<p>Each Daily Run <span class="must">MUST</span>:</p>
<ol>
  <li>Fetch fresh data for all agents in <code>agents.json</code> from sources defined in Section 4.</li>
  <li>Compute health scores per Section 5.</li>
  <li>Collect all supply chain trust signals per Section 6.</li>
  <li>Write a Snapshot to <code>output/history/YYYY-MM-DD.json</code>. Existing Snapshots <span class="must">MUST NOT</span> be modified or deleted.</li>
  <li>Update <code>data.json</code>, <code>index.html</code>, <code>feed.json</code>, <code>sitemap.xml</code>, and all agent profile pages.</li>
</ol>
<p>Rank deltas are computed by comparing the current run's ranks against the most recent prior Snapshot. If no prior Snapshot exists, all rank deltas are marked as "NEW".</p>

<h2 id="s8"><span class="sec-num">8.</span> Agent Eligibility</h2>
<p>To be listed in the HVTracker registry, an agent <span class="must">MUST</span>:</p>
<ul>
  <li>Be open-source with a public GitHub repository.</li>
  <li>Implement or materially support autonomous AI agent behavior.</li>
  <li>Have at least one public release or a non-trivial commit history.</li>
</ul>
<p>An agent <span class="must">MUST NOT</span> be listed if:</p>
<ul>
  <li>Its source code is closed-source or proprietary. (Closed-source agents lack the supply chain signals this methodology depends on.)</li>
  <li>The GitHub repository is private, archived, or deleted.</li>
</ul>
<p>Agent addition and removal decisions are made by the HVTracker maintainer. The agent registry is defined by <code>agents.json</code> in the reference implementation repository.</p>

<h2 id="s9"><span class="sec-num">9.</span> Versioning</h2>
<p>This specification uses semantic versioning of the form <code>vMAJOR.MINOR</code>:</p>
<ul>
  <li><strong>MAJOR</strong> increments when the scoring formula changes in a way that would reorder a substantial fraction of the leaderboard.</li>
  <li><strong>MINOR</strong> increments when new signals are added, data sources change, or non-score-affecting methodology changes are made.</li>
</ul>
<p>All published versions of this specification remain permanently accessible at their versioned URLs. A version <span class="must">MUST NOT</span> be modified after it receives Published status. Corrections <span class="must">MUST</span> be issued as a new version with a Superseded marker on the prior version.</p>
<p>The current specification version is recorded in the <code>methodology_version</code> field of every Snapshot and in the <code>data.json</code> export.</p>

<h2 id="app-a"><span class="sec-num">A.</span> Reference Implementation</h2>
<p>The reference implementation is maintained at:</p>
<pre>https://github.com/YugantM/hvtracker</pre>
<p>The primary scoring and data collection logic is in <code>fetch_and_build.py</code>. The agent registry is in <code>agents.json</code>. Historical Snapshots are in <code>output/history/</code>.</p>
<p>The reference implementation is open-source under the MIT License. The dataset (Snapshots, methodology, brand) is proprietary.</p>

<h2 id="app-b"><span class="sec-num">B.</span> Changelog</h2>
<table class="spec-table">
  <thead><tr><th>Version</th><th>Date</th><th>Summary</th></tr></thead>
  <tbody>
    <tr><td><strong>v2.0</strong></td><td>2026-05-24</td><td>Added Section 6: Supply Chain Trust Signals. Defined npm provenance, PyPI PEP 740 attestations, OSSF Scorecard, and signed commit ratio. Trust signals are collected but do not affect the health score.</td></tr>
    <tr><td>v1.1</td><td>2026-05-10</td><td>Added npm, PyPI, and Hacker News data sources. Daily historical snapshots introduced. Rank delta computation defined.</td></tr>
    <tr><td>v1.0</td><td>2026-05-01</td><td>Initial specification. GitHub-only signals: stars, freshness (pushed_at), commit activity, forks.</td></tr>
  </tbody>
</table>
""",
}

# All published specs, in display order (newest first)
ALL_SPECS = [METHODOLOGY_V2]
