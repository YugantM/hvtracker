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
             {"id": "s6-5", "num": "6.5", "title": "Public Action Tracking (Behavioral Signals)"},
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
<p><strong>Source:</strong> Scorecard data is generated by running the OSSF Scorecard CLI tool directly against each repository, refreshed weekly. Results are cached in <code>scorecard-cache.json</code> and served from cache during daily builds. If a repository is absent from the cache, the build falls back to <code>https://api.deps.dev/v3/projects/github.com%2F{owner}%2F{repo}</code> and then <code>https://api.securityscorecards.dev/projects/github.com/{owner}/{repo}</code>.</p>
<p><strong>Signal:</strong> The overall score (0–10) and individual check scores from the Scorecard CLI output.</p>
<p><strong>Interpretation:</strong> The OpenSSF Scorecard evaluates security posture across checks including: Maintained, Code-Review, Branch-Protection, Signed-Releases, Pinned-Dependencies, Vulnerabilities, Token-Permissions, Dangerous-Workflow, and others. A score of 10 is the maximum.</p>
<p><strong>Limitation:</strong> The weekly CLI scan runs on GitHub Actions; results are at most 7 days old. Absence of a score does not imply poor security posture.</p>

<h3 id="s6-4"><span class="sec-num">6.4</span> Signed Commit Ratio</h3>
<p><strong>Field:</strong> <code>signed_commits_ratio</code> (float 0.0–1.0 or null)</p>
<p><strong>Source:</strong> <code>GET /repos/{owner}/{repo}/commits?per_page=100</code> — field <code>commit.verification.verified</code> on each result</p>
<p><strong>Signal:</strong> <code>verified_count / total_count</code> across up to 100 most recent commits on the default branch. <code>null</code> if the API request fails.</p>
<p><strong>Interpretation:</strong> The fraction of recent commits carrying a verified GPG, SSH, or S/MIME signature as reported by GitHub's signature verification API.</p>
<p><strong>Limitation:</strong> Web-based commits made through GitHub's UI are signed by GitHub's own key and counted as verified, which may inflate the ratio for projects that accept many web-based edits. This signal measures signature <em>presence</em>, not signature quality or key trust level.</p>

<h3 id="s6-5"><span class="sec-num">6.5</span> Public Action Tracking (Behavioral Signals)</h3>
<p><strong>Field:</strong> <code>public_actions</code> (object or null)</p>
<p><strong>Source:</strong> GitHub Search API — <code>GET /search/commits</code> and <code>GET /search/issues</code></p>
<p><strong>Signal:</strong> For agents with a configured fingerprint, counts the number of public commits or merged PRs created by that agent on GitHub in the trailing 30 days. Fingerprints are one of:</p>
<ul>
  <li><strong>commit_trailer</strong> — a standardized co-author or attribution string appended to commit messages (e.g., Aider's <code>Co-authored-by: aider</code>).</li>
  <li><strong>pr_body</strong> — a standardized footer string appended to PR descriptions (e.g., <code>Generated with Gemini CLI</code>).</li>
  <li><strong>bot_account</strong> — a GitHub App bot account that authors commits or PRs (e.g., <code>openhands-agent</code>).</li>
</ul>
<p><strong>Sub-fields:</strong></p>
<ul>
  <li><code>actions_30d</code> — total count of detected actions in the trailing 30 days.</li>
  <li><code>actions_30d_merged</code> — count of merged PRs specifically (null for commit-based fingerprints).</li>
  <li><code>actions_30d_by_repo</code> — top repos where this agent was active (sampled from first page of search results).</li>
</ul>
<p><strong>NOT included in health score.</strong> Public action counts are displayed on the leaderboard and agent profile pages but do not contribute to the composite health score computed in Section 5. They are an informational signal only.</p>
<p><strong>Limitations:</strong></p>
<ul>
  <li>Only agents with a confirmed, unique fingerprint pattern are tracked. Agents without a detectable fingerprint report <code>null</code>.</li>
  <li>Private repository usage is entirely invisible to this signal.</li>
  <li>GitHub Search API caps results at 1,000 per query. Counts above 1,000 are lower bounds.</li>
  <li>Fingerprint patterns may produce false positives if the pattern string is not sufficiently unique. Each fingerprint is documented and validated in <code>docs/research/agent-fingerprints.md</code>.</li>
</ul>

<h2 id="s7"><span class="sec-num">7.</span> Update Process and Cadence</h2>
<p>The reference implementation <span class="must">MUST</span> execute at least once per calendar day. The production deployment runs at <strong>06:00 UTC</strong> daily via GitHub Actions.</p>
<p>Each Daily Run <span class="must">MUST</span>:</p>
<ol>
  <li>Fetch fresh data for all agents in <code>agents.json</code> from sources defined in Section 4.</li>
  <li>Compute health scores per Section 5.</li>
  <li>Collect all supply chain trust signals per Section 6.</li>
  <li>Collect behavioral signals per Section 6.5 (for agents with configured fingerprints).</li>
  <li>Write a Snapshot to <code>output/history/YYYY-MM-DD.json</code>. Existing Snapshots <span class="must">MUST NOT</span> be modified or deleted.</li>
  <li>Update <code>data.json</code>, <code>index.html</code>, <code>feed.json</code>, <code>sitemap.xml</code>, and all agent profile pages.</li>
  <li>Generate stable data endpoints under <code>data/</code> per the Data Schema Specification v0.1.</li>
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
    <tr><td><strong>v2.0</strong></td><td>2026-05-24</td><td>Added Section 6: Supply Chain Trust Signals. Defined npm provenance, PyPI PEP 740 attestations, OSSF Scorecard (CLI-based, weekly cache), and signed commit ratio. Trust signals are collected but do not affect the health score.</td></tr>
    <tr><td>v1.1</td><td>2026-05-10</td><td>Added npm, PyPI, and Hacker News data sources. Daily historical snapshots introduced. Rank delta computation defined.</td></tr>
    <tr><td>v1.0</td><td>2026-05-01</td><td>Initial specification. GitHub-only signals: stars, freshness (pushed_at), commit activity, forks.</td></tr>
  </tbody>
</table>
""",
}

ELIGIBILITY_V1 = {
    "title": "HVTracker Eligibility Specification",
    "slug": "eligibility",
    "version": "v1.0",
    "status": "Published",
    "date": "2026-05-24",
    "authors": ["HVTracker"],
    "abstract": (
        "This document defines the criteria by which a software project qualifies "
        "for inclusion in the HVTracker leaderboard. It specifies necessary and "
        "sufficient conditions using normative language (MUST, SHOULD, MAY) such "
        "that two independent reviewers applying this specification to any candidate "
        "project will reach the same inclusion or exclusion decision. This "
        "specification supersedes all prior informal or implicit eligibility rules."
    ),
    "sections": [
        {"id": "s1", "num": "1.", "title": "Abstract"},
        {"id": "s2", "num": "2.", "title": "Motivation"},
        {"id": "s3", "num": "3.", "title": "Terminology"},
        {"id": "s4", "num": "4.", "title": "Eligibility Criteria",
         "subsections": [
             {"id": "s4-1", "num": "4.1", "title": "Required Criteria (MUST)"},
             {"id": "s4-2", "num": "4.2", "title": "Recommended Criteria (SHOULD)"},
             {"id": "s4-3", "num": "4.3", "title": "Optional Criteria (MAY)"},
         ]},
        {"id": "s5", "num": "5.", "title": "Disqualification Criteria"},
        {"id": "s6", "num": "6.", "title": "Review Process",
         "subsections": [
             {"id": "s6-1", "num": "6.1", "title": "Adding a New Project"},
             {"id": "s6-2", "num": "6.2", "title": "Reviewing Existing Projects"},
             {"id": "s6-3", "num": "6.3", "title": "Removal Process"},
         ]},
        {"id": "s7", "num": "7.", "title": "Automated Enforcement"},
        {"id": "s8", "num": "8.", "title": "Versioning and Changelog"},
    ],
    "appendices": [
        {"id": "app-a", "num": "A.", "title": "Boundary Cases"},
        {"id": "app-b", "num": "B.", "title": "Criteria Quick Reference"},
    ],
    "body": """
<h2 id="s1"><span class="sec-num">1.</span> Abstract</h2>
<p>This document defines the criteria by which a software project qualifies for inclusion in the HVTracker leaderboard. It specifies necessary and sufficient conditions using normative language such that two independent reviewers applying this specification to any candidate project will reach the same inclusion or exclusion decision.</p>
<p>The key words <span class="must">MUST</span>, <span class="must">MUST NOT</span>, <span class="should">SHOULD</span>, <span class="should">SHOULD NOT</span>, and <span class="may">MAY</span> in this document are to be interpreted as described in <a href="https://www.rfc-editor.org/rfc/rfc2119" target="_blank" rel="noopener">RFC 2119</a>.</p>

<h2 id="s2"><span class="sec-num">2.</span> Motivation</h2>
<p>HVTracker tracks open-source AI agent projects and generates daily health scores. As the index has grown, the question of what belongs in it has become harder to answer by intuition alone. Several failure modes have emerged:</p>
<ul>
  <li>Projects that were once active agents are now archived or unmaintained.</li>
  <li>Some entries are hosted services that expose no inspectable source code.</li>
  <li>Some entries are thin API wrappers with no agent logic of their own.</li>
  <li>Some entries are forks with no independent development activity.</li>
</ul>
<p>Without a formal eligibility specification, the index is subject to arbitrary inclusion driven by novelty rather than fit. A formal specification makes the boundary visible, consistent, and disputable. It also enables automated checking during the build process so violations surface as warnings rather than silent drift.</p>

<h2 id="s3"><span class="sec-num">3.</span> Terminology</h2>
<dl>
  <dt>AI agent</dt>
  <dd>A software system that autonomously performs multi-step tasks by combining a language model with external capabilities such as tool use, memory, code execution, browser control, or file system access. An AI agent takes an underspecified goal as input and determines the sequence of actions required to accomplish it without requiring a human to specify each step.</dd>
  <dt>Autonomous task execution</dt>
  <dd>The capacity of a system to complete a task end-to-end without human confirmation at each step. A system that requires a human to approve every action before proceeding is a tool, not an agent.</dd>
  <dt>Tool use</dt>
  <dd>The capacity of a software system to invoke external functions, APIs, code interpreters, or system interfaces as part of completing a task. Tool use is a necessary but not sufficient condition for agent classification.</dd>
  <dt>Hosted service</dt>
  <dd>A software system delivered exclusively via a networked API or web interface for which no source code is publicly available for inspection, modification, or self-hosting. Hosted services are not eligible regardless of their capabilities.</dd>
  <dt>Thin client</dt>
  <dd>A software package whose primary function is to make API calls to a remote service, containing no agent logic of its own. Not independently eligible.</dd>
  <dt>Framework</dt>
  <dd>A software library or toolkit that enables developers to construct AI agents, providing abstractions for tool use, memory, planning, or multi-agent coordination.</dd>
  <dt>Open-source license</dt>
  <dd>A license that meets the Open Source Definition as maintained by the Open Source Initiative (OSI), or a license widely accepted in the open-source community providing equivalent rights. Includes all OSI-approved licenses and the RAIL family when source is publicly available.</dd>
  <dt>Version control repository</dt>
  <dd>A hosted repository using a distributed version control system (e.g., Git) that is publicly accessible without authentication.</dd>
  <dt>Meaningful activity</dt>
  <dd>At least one of the following within a trailing 12-month window: a merged pull request, a commit to the primary branch, a published release, or a closed issue with a maintainer response. Activity by automated bots (dependency bumps, CI runs) does not count unless accompanied by human commits.</dd>
  <dt>Archived project</dt>
  <dd>A project whose version control repository has been placed in a read-only archived state by its maintainers, or for which maintainers have publicly stated it is no longer maintained.</dd>
  <dt>Abandoned fork</dt>
  <dd>A repository that is a fork of another project and has received zero independent commits since the fork was created, or since the upstream project itself became inactive.</dd>
</dl>

<h2 id="s4"><span class="sec-num">4.</span> Eligibility Criteria</h2>

<h3 id="s4-1"><span class="sec-num">4.1</span> Required Criteria (MUST)</h3>
<p>A candidate project <span class="must">MUST</span> satisfy all of the following to be eligible for inclusion.</p>

<p><strong>4.1.1 Open-source license.</strong> The project <span class="must">MUST</span> be distributed under an open-source license as defined in Section 3. The license <span class="must">MUST</span> be declared in the primary repository (e.g., LICENSE file, SPDX identifier in package manifest). A project with no declared license is not eligible.</p>

<p><strong>4.1.2 Public version control repository.</strong> The project <span class="must">MUST</span> have a publicly accessible version control repository as defined in Section 3. The repository <span class="must">MUST</span> be the primary location for source code and development activity — a mirror is not sufficient if the primary repository is private.</p>

<p><strong>4.1.3 Software deliverable.</strong> The project <span class="must">MUST</span> be primarily delivered as software that can be inspected, cloned, and run by a third party. Projects delivered exclusively as hosted services are not eligible. A project that offers both a hosted service and a self-hostable open-source component is eligible on the basis of the open-source component only.</p>

<p><strong>4.1.4 Agent characteristics.</strong> The project <span class="must">MUST</span> demonstrate at least two of the following three agent characteristics:</p>
<ul>
  <li><strong>(a) Autonomous task execution:</strong> The system can complete a multi-step task given only an initial natural-language goal, without requiring human confirmation at each step.</li>
  <li><strong>(b) Tool use:</strong> The system can invoke external functions, APIs, code interpreters, file systems, or browser interfaces as part of task completion.</li>
  <li><strong>(c) Goal-directed planning:</strong> The system decomposes a goal into sub-tasks, selects actions based on intermediate results, and adapts its plan when an action fails.</li>
</ul>
<p>A system that satisfies only (b) — tool use — without (a) or (c) is a tool-augmented chatbot, not an agent, and is not eligible.</p>

<p><strong>4.1.5 Non-trivial implementation.</strong> The project <span class="must">MUST</span> contain non-trivial agent logic in its own codebase. A package whose sole function is to forward requests to a remote agent API is not eligible on its own. The project <span class="must">MUST</span> contain at least one of: a planning or reasoning loop, a memory system, a tool dispatch mechanism, or a multi-step execution engine implemented in the package itself.</p>

<h3 id="s4-2"><span class="sec-num">4.2</span> Recommended Criteria (SHOULD)</h3>
<p>A candidate project <span class="should">SHOULD</span> satisfy the following. Projects that do not satisfy these criteria are not disqualified but are flagged for manual review.</p>

<p><strong>4.2.1 Meaningful recent activity.</strong> The project <span class="should">SHOULD</span> demonstrate meaningful activity as defined in Section 3 within the trailing 12 months. Projects with no meaningful activity in 12 months are flagged as inactive. They remain on the leaderboard but receive an inactive annotation visible to users.</p>

<p><strong>4.2.2 Installable package.</strong> The project <span class="should">SHOULD</span> be installable via a mainstream package manager (npm, PyPI, Homebrew, Cargo, etc.). Projects distributed only as source tarballs or ZIP archives are technically eligible but harder to track.</p>

<p><strong>4.2.3 Documentation of agent capabilities.</strong> The project <span class="should">SHOULD</span> document its agent characteristics in its README or official documentation. A project that makes no claims about agent behavior in its own documentation cannot be verified against criterion 4.1.4.</p>

<h3 id="s4-3"><span class="sec-num">4.3</span> Optional Criteria (MAY)</h3>
<p><strong>4.3.1 Framework eligibility.</strong> A project <span class="may">MAY</span> be a framework or library that enables agent construction rather than an agent itself, provided it meets all MUST criteria and additionally:</p>
<ul>
  <li>Its primary design goal is enabling agent construction, not general-purpose programming.</li>
  <li>It provides abstractions specific to agent behavior: tool registration, memory interfaces, agent lifecycle management, or multi-agent coordination.</li>
  <li>At least one publicly available project built on the framework qualifies as an agent under 4.1.4.</li>
</ul>
<p>General-purpose utility libraries (HTTP clients, JSON parsers, LLM SDK wrappers with no agent abstractions) are not eligible under this clause.</p>

<h2 id="s5"><span class="sec-num">5.</span> Disqualification Criteria</h2>
<p>A project is disqualified and <span class="must">MUST</span> be removed from the leaderboard if any of the following conditions are met. Disqualification criteria take precedence over eligibility criteria.</p>
<table class="spec-table">
  <thead><tr><th>ID</th><th>Criterion</th><th>Data source</th></tr></thead>
  <tbody>
    <tr><td>5.1</td><td>The project's primary repository has been archived (read-only) by its maintainers.</td><td>GitHub API: <code>archived</code> field</td></tr>
    <tr><td>5.2</td><td>The project has changed its license to one that no longer meets the open-source definition in Section 3. Evaluated as of the most recent release.</td><td>GitHub API: <code>license.spdx_id</code></td></tr>
    <tr><td>5.3</td><td>The project is a fork of another tracked project and has made zero independent commits in the trailing 24 months.</td><td>GitHub API: <code>fork</code> flag + commit comparison</td></tr>
    <tr><td>5.4</td><td>The project's repository has been made private or deleted.</td><td>GitHub API: HTTP 404 on repo endpoint</td></tr>
    <tr><td>5.5</td><td>The project's maintainers have formally requested removal from the index.</td><td>Manual</td></tr>
  </tbody>
</table>

<h2 id="s6"><span class="sec-num">6.</span> Review Process</h2>

<h3 id="s6-1"><span class="sec-num">6.1</span> Adding a New Project</h3>
<p>To add a candidate project, a reviewer applies the criteria in Section 4 in order:</p>
<ol>
  <li>Verify 4.1.1 (license): Check the LICENSE file and SPDX identifier.</li>
  <li>Verify 4.1.2 (repository): Confirm the repository is public and not a mirror.</li>
  <li>Verify 4.1.3 (software deliverable): Confirm the project can be cloned and run.</li>
  <li>Verify 4.1.4 (agent characteristics): Verify at least two of (a), (b), (c).</li>
  <li>Verify 4.1.5 (non-trivial implementation): Confirm agent logic exists in the codebase.</li>
  <li>Check 4.2.1 (recent activity): Note if inactive; flag for annotation, not exclusion.</li>
  <li>Check Section 5 (disqualification): If any apply, the project is excluded regardless of 4.1.</li>
</ol>
<p>The reviewer records their findings in a structured note attached to the pull request that adds the agent to <code>agents.json</code>. The note <span class="must">MUST</span> reference each criterion explicitly.</p>

<h3 id="s6-2"><span class="sec-num">6.2</span> Reviewing Existing Projects</h3>
<p>The automated build process checks criteria 5.1 (archived), 5.4 (private/deleted), and 4.2.1 (recent activity) on every run. Violations are emitted as warnings in the build log and do not block the build. The owner reviews warnings and decides on action.</p>
<p>Criteria that require human judgment (4.1.4, 4.1.5, 5.3) are reviewed manually on a quarterly basis or when flagged.</p>

<h3 id="s6-3"><span class="sec-num">6.3</span> Removal Process</h3>
<p>Before removing a project, the owner reviews the disqualification reason and, where practical, notifies the project maintainers. Removal is recorded in the git commit message with the criterion cited. No project is removed without owner approval.</p>

<h2 id="s7"><span class="sec-num">7.</span> Automated Enforcement</h2>
<p>The build system implements automated checks for the following criteria during each daily cron run. All checks are non-blocking (warnings only). No agent is removed automatically.</p>
<table class="spec-table">
  <thead><tr><th>Check</th><th>Criterion</th><th>Data source</th></tr></thead>
  <tbody>
    <tr><td>Repository archived</td><td>5.1</td><td>GitHub API: <code>archived</code> field</td></tr>
    <tr><td>Repository not found (HTTP 404)</td><td>5.4</td><td>GitHub API: exception handling in fetch</td></tr>
    <tr><td>No activity in 12 months</td><td>4.2.1</td><td>GitHub API: <code>pushed_at</code> field</td></tr>
    <tr><td>No declared license</td><td>4.1.1</td><td>GitHub API: <code>license</code> field</td></tr>
  </tbody>
</table>
<p>Criteria 4.1.4 and 4.1.5 require human review and are not automatically enforced.</p>

<h2 id="s8"><span class="sec-num">8.</span> Versioning and Changelog</h2>
<p>This specification is versioned independently of the HVTracker Methodology Specification. Changes to eligibility criteria increment the minor version (v1.0 → v1.1) for clarifications and the major version (v1.0 → v2.0) for changes that would cause a currently included project to be excluded or a currently excluded project to become eligible.</p>
<table class="spec-table">
  <thead><tr><th>Version</th><th>Date</th><th>Summary</th></tr></thead>
  <tbody>
    <tr><td><strong>v1.0</strong></td><td>2026-05-24</td><td>Initial publication. Defines five MUST criteria, three SHOULD criteria, one MAY clause, five disqualification triggers, and automated enforcement checks for §4.1.1, §4.2.1, §5.1, and §5.4.</td></tr>
  </tbody>
</table>

<h2 id="app-a"><span class="sec-num">A.</span> Boundary Cases</h2>
<p>The following cases illustrate how the criteria apply in ambiguous situations. These are non-normative.</p>
<dl>
  <dt>A.1 Hosted service with open-source server code</dt>
  <dd>A product that offers a hosted SaaS interface and also publishes the server code under an open-source license. Eligible on the basis of the open-source component if it meets 4.1.4 and 4.1.5. The hosted interface is irrelevant to eligibility.</dd>
  <dt>A.2 Research prototype</dt>
  <dd>A repository associated with a published academic paper, containing code that runs an agent experiment but has no releases, no package, and no commits after the paper's publication date. Eligible under 4.1 if agent characteristics are present, but flagged under 4.2.1 as inactive. Not disqualified.</dd>
  <dt>A.3 Model provider SDK</dt>
  <dd>An SDK published by an LLM provider that includes convenience wrappers for function calling and tool use. Eligible under 4.3.1 (framework) only if it includes agent-specific abstractions (e.g., an agent loop, tool registry, multi-step execution engine). A bare function-calling wrapper is not eligible.</dd>
  <dt>A.4 Fork with substantial divergence</dt>
  <dd>A fork of a tracked project that has added its own planning engine, tool integrations, and an independent release history. Not subject to 5.3. Evaluated independently against all criteria in Section 4.</dd>
  <dt>A.5 Partial relicense</dt>
  <dd>A project that relicenses its core under a commercial license but retains an open-source community edition. Eligible only if the community edition meets all criteria in Section 4 independently, without depending on proprietary components for core agent functionality.</dd>
</dl>

<h2 id="app-b"><span class="sec-num">B.</span> Criteria Quick Reference</h2>
<table class="spec-table">
  <thead><tr><th>ID</th><th>Level</th><th>Criterion</th></tr></thead>
  <tbody>
    <tr><td>4.1.1</td><td><span class="must">MUST</span></td><td>Open-source license declared</td></tr>
    <tr><td>4.1.2</td><td><span class="must">MUST</span></td><td>Public version control repository</td></tr>
    <tr><td>4.1.3</td><td><span class="must">MUST</span></td><td>Software deliverable, not hosted-only</td></tr>
    <tr><td>4.1.4</td><td><span class="must">MUST</span></td><td>≥2 of: autonomous execution, tool use, goal-directed planning</td></tr>
    <tr><td>4.1.5</td><td><span class="must">MUST</span></td><td>Non-trivial agent logic in own codebase</td></tr>
    <tr><td>4.2.1</td><td><span class="should">SHOULD</span></td><td>Meaningful activity in trailing 12 months</td></tr>
    <tr><td>4.2.2</td><td><span class="should">SHOULD</span></td><td>Installable via mainstream package manager</td></tr>
    <tr><td>4.2.3</td><td><span class="should">SHOULD</span></td><td>Agent capabilities documented in README</td></tr>
    <tr><td>4.3.1</td><td><span class="may">MAY</span></td><td>Framework eligible if agent-specific abstractions present</td></tr>
    <tr><td>5.1</td><td>DISQUALIFY</td><td>Repository archived</td></tr>
    <tr><td>5.2</td><td>DISQUALIFY</td><td>License no longer open-source</td></tr>
    <tr><td>5.3</td><td>DISQUALIFY</td><td>Abandoned fork, zero independent commits in 24 months</td></tr>
    <tr><td>5.4</td><td>DISQUALIFY</td><td>Repository private or deleted</td></tr>
    <tr><td>5.5</td><td>DISQUALIFY</td><td>Maintainer withdrawal request</td></tr>
  </tbody>
</table>
""",
}

PROVENANCE_V01 = {
    "title": "HVTracker Provenance Profile",
    "slug": "provenance",
    "version": "v0.1",
    "status": "Published",
    "date": "2026-05-24",
    "authors": ["HVTracker"],
    "abstract": (
        "This document specifies the trust signal model used by HVTracker to assess "
        "the supply chain integrity of open-source AI agent projects. It formally defines "
        "the schema, data source, collection method, freshness expectations, and failure "
        "modes for each of the four currently tracked signals: npm provenance attestations, "
        "PyPI PEP 740 attestations, OSSF Scorecard, and signed commit ratio. An extension "
        "model defines how new trust signals may be incorporated in future versions. "
        "This is a v0.x specification; signals are collected and displayed but do not "
        "affect the health score."
    ),
    "sections": [
        {"id": "s1", "num": "1.", "title": "Abstract"},
        {"id": "s2", "num": "2.", "title": "Motivation"},
        {"id": "s3", "num": "3.", "title": "Terminology"},
        {"id": "s4", "num": "4.", "title": "Trust Signals",
         "subsections": [
             {"id": "s4-1", "num": "4.1", "title": "npm Provenance"},
             {"id": "s4-2", "num": "4.2", "title": "PyPI Provenance (PEP 740)"},
             {"id": "s4-3", "num": "4.3", "title": "OSSF Scorecard"},
             {"id": "s4-4", "num": "4.4", "title": "Signed Commit Ratio"},
         ]},
        {"id": "s5", "num": "5.", "title": "Extension Model",
         "subsections": [
             {"id": "s5-1", "num": "5.1", "title": "Inclusion Criteria"},
             {"id": "s5-2", "num": "5.2", "title": "Addition Process"},
             {"id": "s5-3", "num": "5.3", "title": "Removal Process"},
         ]},
        {"id": "s6", "num": "6.", "title": "Verification Process"},
        {"id": "s7", "num": "7.", "title": "Versioning and Changelog"},
    ],
    "appendices": [
        {"id": "app-a", "num": "A.", "title": "Field Reference"},
        {"id": "app-b", "num": "B.", "title": "Coverage as of 2026-05-24"},
    ],
    "body": """
<h2 id="s1"><span class="sec-num">1.</span> Abstract</h2>
<p>This document specifies the trust signal model used by HVTracker to assess the supply chain integrity of open-source AI agent projects. It formally defines the schema, data source, collection method, freshness expectations, and failure modes for each of the four currently tracked signals: npm provenance attestations, PyPI PEP 740 attestations, OSSF Scorecard, and signed commit ratio.</p>
<p>The key words <span class="must">MUST</span>, <span class="must">MUST NOT</span>, <span class="should">SHOULD</span>, <span class="should">SHOULD NOT</span>, and <span class="may">MAY</span> in this document are to be interpreted as described in <a href="https://www.rfc-editor.org/rfc/rfc2119" target="_blank" rel="noopener">RFC 2119</a>.</p>
<div class="note"><strong>v0.x status:</strong> Signals are collected and displayed but do not affect the health score defined in the <a href="/spec/methodology/v2.0">Methodology Specification v2.0</a>. Promotion to v1.0 will occur when the trust model is considered stable enough to inform scoring.</div>

<h2 id="s2"><span class="sec-num">2.</span> Motivation</h2>
<p>Open-source AI agent projects are becoming critical infrastructure. Unlike traditional software libraries, AI agents often operate with broad system permissions — reading files, browsing the web, executing code, and calling external APIs on behalf of users. The integrity of the supply chain from which these agents are installed therefore carries higher stakes than for passive libraries.</p>
<p>HVTracker tracks health signals derived from project activity (stars, commits, forks). These signals measure adoption and development momentum but say nothing about whether the artifacts users install are trustworthy. A project with 50,000 stars and daily commits can still ship a compromised release if its publishing pipeline lacks attestations or its commits go unsigned.</p>
<p>The Provenance Profile addresses this gap. It defines a set of unilaterally observable, publicly verifiable signals that characterize the supply chain trustworthiness of a project's release artifacts. No maintainer participation, registration, or opt-in is required or assumed — all signals are derived from public cryptographic infrastructure.</p>

<h2 id="s3"><span class="sec-num">3.</span> Terminology</h2>
<dl>
  <dt>Trust signal</dt>
  <dd>A binary or scalar value derived from publicly observable cryptographic infrastructure that characterizes one dimension of the supply chain integrity of a software project. Trust signals are not scores and are not aggregated into a composite value in this version.</dd>
  <dt>Attestation</dt>
  <dd>A cryptographically signed statement, produced by a known identity (typically a CI/CD system), asserting facts about a software artifact — most commonly that the artifact was built from a specific source commit in a specific pipeline environment. Attestations are logged to a transparency log so they cannot be silently revoked.</dd>
  <dt>Provenance</dt>
  <dd>The verifiable record of how a software artifact was produced: which source repository, which commit, which build environment, and which pipeline. Provenance is a specific category of attestation that answers "where did this artifact come from?"</dd>
  <dt>Artifact</dt>
  <dd>A published binary or source distribution of a software package — a <code>.whl</code> file on PyPI, a tarball on npm, a container image layer, etc.</dd>
  <dt>Transparency log</dt>
  <dd>An append-only, cryptographically verifiable log of signed records. The primary transparency log used by npm and PyPI provenance is Sigstore's Rekor. Once a record is appended, it cannot be deleted without detection.</dd>
  <dt>Freshness</dt>
  <dd>The degree to which a trust signal reflects the current state of a project rather than a historical state. A signal is fresh if it was collected within one Daily Run of the current build.</dd>
  <dt>Verified signature</dt>
  <dd>A commit signature whose cryptographic validity has been confirmed by GitHub's signature verification API. A verified signature does not imply key quality or trust level — it means the signature is mathematically valid and the signing key is recognized by GitHub.</dd>
  <dt>Trusted Publisher</dt>
  <dd>A mechanism (npm: Provenance, PyPI: OIDC Trusted Publishing) that allows a CI/CD system to publish packages using a short-lived identity token rather than a long-lived API key. Artifacts published via a Trusted Publisher are eligible for provenance attestations.</dd>
  <dt>OSSF Scorecard</dt>
  <dd>An automated tool maintained by the Open Source Security Foundation that evaluates a project's security posture across a fixed set of checks and produces a score from 0 to 10.</dd>
</dl>

<h2 id="s4"><span class="sec-num">4.</span> Trust Signals</h2>

<h3 id="s4-1"><span class="sec-num">4.1</span> npm Provenance</h3>
<p><strong>Field:</strong> <code>npm_provenance</code> &nbsp;|&nbsp; <strong>Type:</strong> <code>boolean | null</code> &nbsp;|&nbsp; <strong>Scope:</strong> agents with a configured <code>npm_package</code></p>
<table class="spec-table">
  <thead><tr><th>Value</th><th>Meaning</th></tr></thead>
  <tbody>
    <tr><td><code>true</code></td><td>The latest published version includes at least one provenance attestation in <code>dist.attestations</code>.</td></tr>
    <tr><td><code>false</code></td><td>The latest published version has no provenance attestations (<code>dist.attestations</code> is absent or null).</td></tr>
    <tr><td><code>null</code></td><td>No <code>npm_package</code> configured, or the API request failed.</td></tr>
  </tbody>
</table>
<p><strong>Source:</strong> <code>GET https://registry.npmjs.org/{package}/latest</code> — signal is <code>true</code> iff <code>dist.attestations</code> is present and non-null.</p>
<p><strong>What it means:</strong> The package publisher used npm's Provenance feature, requiring a Trusted Publisher (GitHub Actions, GitLab CI, CircleCI). The resulting attestation is an in-toto SLSA provenance statement, signed via Sigstore's keyless protocol and logged to the Rekor transparency log. End users can verify via <code>npm audit signatures</code>.</p>
<p><strong>Freshness:</strong> Reflects the <code>latest</code> tag at collection time. Changes on the next Daily Run after a new version is published.</p>
<p><strong>Limitations:</strong> Only the <code>latest</code> tag is checked. The attestation's content is not cryptographically verified by the reference implementation — presence is checked, not validity.</p>

<h3 id="s4-2"><span class="sec-num">4.2</span> PyPI Provenance (PEP 740)</h3>
<p><strong>Field:</strong> <code>pypi_provenance</code> &nbsp;|&nbsp; <strong>Type:</strong> <code>boolean | null</code> &nbsp;|&nbsp; <strong>Scope:</strong> agents with a configured <code>pypi_package</code></p>
<table class="spec-table">
  <thead><tr><th>Value</th><th>Meaning</th></tr></thead>
  <tbody>
    <tr><td><code>true</code></td><td>The last file entry in the package's Simple API response has a non-null <code>provenance</code> field.</td></tr>
    <tr><td><code>false</code></td><td>The last file entry has no <code>provenance</code> field.</td></tr>
    <tr><td><code>null</code></td><td>No <code>pypi_package</code> configured, or the API returned non-200.</td></tr>
  </tbody>
</table>
<p><strong>Source:</strong> <code>GET https://pypi.org/simple/{package}/</code> with <code>Accept: application/vnd.pypi.simple.v1+json</code> (PEP 691). The last element of the <code>files</code> array is checked for a <code>provenance</code> field.</p>
<p><strong>Collection:</strong> Requests <span class="must">MUST</span> be made serially with a minimum 1.2-second delay between PyPI requests. On HTTP 429 the signal is <code>null</code> for that run.</p>
<p><strong>What it means:</strong> The most recently uploaded distribution carries a PEP 740 digital attestation generated by PyPI's Trusted Publishing mechanism. The attestation is cryptographically bound to the source repository and CI run that produced the artifact.</p>
<p><strong>Limitations:</strong> PEP 740 was accepted in 2024; most packages predate it. Packages published via <code>twine</code> with API tokens cannot carry PEP 740 attestations by design. Only the last uploaded file is checked, not the latest stable release tag.</p>

<h3 id="s4-3"><span class="sec-num">4.3</span> OSSF Scorecard</h3>
<p><strong>Fields:</strong> <code>scorecard_score</code> (<code>float | null</code>, range 0–10) &nbsp;·&nbsp; <code>scorecard_checks</code> (<code>object | {}</code>, check name → score)</p>
<p><strong>Scope:</strong> All agents.</p>
<p><strong>Collection:</strong> Scorecard data is generated by running the OSSF Scorecard CLI tool directly against each repository, refreshed weekly via GitHub Actions. Results are cached in <code>scorecard-cache.json</code>; daily builds read from this cache. If a repository is absent from the weekly cache, the daily build falls back to remote APIs (tried in order):</p>
<ol>
  <li><strong>deps.dev:</strong> <code>GET https://api.deps.dev/v3/projects/github.com%2F{owner}%2F{repo}</code> — reads <code>scorecard.overallScore</code> and <code>scorecard.checks</code>.</li>
  <li><strong>securityscorecards.dev:</strong> <code>GET https://api.securityscorecards.dev/projects/github.com/{owner}/{repo}</code> — reads <code>score</code> and <code>checks</code>.</li>
</ol>
<p><strong>What it means:</strong> The OSSF Scorecard score is a weighted aggregate of 10–18 individual checks (Maintained, Code-Review, Branch-Protection, Signed-Releases, Pinned-Dependencies, Vulnerabilities, Token-Permissions, Dangerous-Workflow, and others). HVTracker reports the score as-is; it does not reweight or reinterpret individual checks.</p>
<p><strong>Freshness:</strong> The CLI scan runs weekly; results are at most 7 days old. Daily builds serve the cached value unchanged until the next weekly scan.</p>
<p><strong>Limitations:</strong> Absence of a score does not imply poor security posture. The check set and weights are controlled by the OpenSSF Scorecard project, not HVTracker, and may change between Scorecard versions.</p>

<h3 id="s4-4"><span class="sec-num">4.4</span> Signed Commit Ratio</h3>
<p><strong>Field:</strong> <code>signed_commits_ratio</code> &nbsp;|&nbsp; <strong>Type:</strong> <code>float | null</code>, range 0.0–1.0, rounded to 3 decimal places &nbsp;|&nbsp; <strong>Scope:</strong> All agents.</p>
<table class="spec-table">
  <thead><tr><th>Value</th><th>Meaning</th></tr></thead>
  <tbody>
    <tr><td><code>1.0</code></td><td>All sampled commits carry a verified signature.</td></tr>
    <tr><td><code>0.0 &lt; x &lt; 1.0</code></td><td>Fraction <code>x</code> of sampled commits carry a verified signature.</td></tr>
    <tr><td><code>0.0</code></td><td>No sampled commits carry a verified signature.</td></tr>
    <tr><td><code>null</code></td><td>API request failed or commits list is empty.</td></tr>
  </tbody>
</table>
<p><strong>Source:</strong> <code>GET https://api.github.com/repos/{owner}/{repo}/commits?per_page=100</code> — reads <code>commit.verification.verified</code> on each result. Signal = <code>verified_count / total_count</code>.</p>
<p><strong>What it means:</strong> The fraction of the most recent 100 commits on the default branch that carry a cryptographic signature (GPG, SSH, or S/MIME) verified as mathematically valid by GitHub.</p>
<p><strong>Freshness:</strong> Collected fresh each Daily Run. The sample window slides forward as new commits are pushed.</p>
<p><strong>Limitations:</strong> Commits made through GitHub's web UI are signed by GitHub's own key and counted as verified, which may inflate the ratio. Only 100 commits are sampled. Signature presence is measured, not key quality or trust level.</p>

<h2 id="s5"><span class="sec-num">5.</span> Extension Model</h2>

<h3 id="s5-1"><span class="sec-num">5.1</span> Inclusion Criteria</h3>
<p>A proposed new trust signal <span class="must">MUST</span> satisfy all of the following:</p>
<ol>
  <li><strong>Unilateral observability:</strong> Derivable from public APIs or public cryptographic infrastructure without maintainer participation or opt-in.</li>
  <li><strong>Binary or scalar output:</strong> Produces a <code>boolean</code>, <code>float</code>, or <code>integer</code> value (or <code>null</code> for unavailability). Categorical or free-text signals are not permitted.</li>
  <li><strong>Determinism:</strong> Given the same API response at the same point in time, two independent implementations <span class="must">MUST</span> produce the same signal value.</li>
  <li><strong>Distinct from existing signals:</strong> Measures a dimension of supply chain trust not already covered by the four signals in Section 4.</li>
  <li><strong>Stable upstream source:</strong> The data source <span class="must">MUST</span> be maintained by a known organization and have a documented API.</li>
</ol>

<h3 id="s5-2"><span class="sec-num">5.2</span> Addition Process</h3>
<ol>
  <li>The candidate signal is described in a draft section following the format of Section 4 (schema, data source, collection method, meaning, freshness, failure modes, limitations).</li>
  <li>The draft is reviewed by the owner and merged into a new minor version of this specification (e.g., v0.1 → v0.2).</li>
  <li>The reference implementation is updated to collect the signal. The signal is added to <code>data.json</code> and displayed on agent profile pages.</li>
  <li>The signal is collected for at least 30 days before any discussion of incorporating it into the health score.</li>
</ol>

<h3 id="s5-3"><span class="sec-num">5.3</span> Removal Process</h3>
<p>A signal <span class="may">MAY</span> be removed if the upstream data source becomes unavailable or undocumented, if the signal is found to be non-deterministic or gameable in a way that undermines its value, or if a superior signal that subsumes it is added. Removal increments the minor version. Historical Snapshots retain all fields from their collection date and are not retroactively modified.</p>

<h2 id="s6"><span class="sec-num">6.</span> Verification Process</h2>
<p>HVTracker does not independently verify the cryptographic claims in trust signals — that responsibility lies with the end user and the upstream infrastructure. HVTracker's role is to collect and report whether the relevant cryptographic infrastructure is in use.</p>
<table class="spec-table">
  <thead><tr><th>Signal</th><th>Who verifies the cryptography</th></tr></thead>
  <tbody>
    <tr><td><code>npm_provenance</code></td><td>npm CLI (<code>npm audit signatures</code>); Rekor transparency log</td></tr>
    <tr><td><code>pypi_provenance</code></td><td>PyPI infrastructure; Rekor transparency log</td></tr>
    <tr><td><code>scorecard_score</code></td><td>OpenSSF Scorecard infrastructure; publicly auditable</td></tr>
    <tr><td><code>signed_commits_ratio</code></td><td>GitHub's signature verification API; end users via <code>git verify-commit</code></td></tr>
  </tbody>
</table>
<p>A <code>true</code> or high-ratio value means the relevant verification system reported success — it does not constitute an independent endorsement by HVTracker.</p>

<h2 id="s7"><span class="sec-num">7.</span> Versioning and Changelog</h2>
<p><strong>v0.x:</strong> Signals are collected and displayed but do not affect the health score. The specification is experimental; signals may be added, removed, or redefined with minor version increments.</p>
<p><strong>v1.x:</strong> The signal set is considered stable. Changes that affect which signals are collected or how they are defined increment the major version. Promotion from v0.x to v1.0 requires that the signal set has been stable for at least 90 days and that the owner has reviewed the specification for completeness.</p>
<p>All published versions remain permanently accessible at their versioned URLs. A version <span class="must">MUST NOT</span> be modified after it receives Published status.</p>
<table class="spec-table">
  <thead><tr><th>Version</th><th>Date</th><th>Summary</th></tr></thead>
  <tbody>
    <tr><td><strong>v0.1</strong></td><td>2026-05-24</td><td>Initial publication. Defines four signals: npm provenance, PyPI PEP 740, OSSF Scorecard (deps.dev primary + securityscorecards.dev fallback), signed commit ratio. Extension model and verification process defined.</td></tr>
  </tbody>
</table>

<h2 id="app-a"><span class="sec-num">A.</span> Field Reference</h2>
<table class="spec-table">
  <thead><tr><th>Field</th><th>Type</th><th>Signal</th><th>Since</th></tr></thead>
  <tbody>
    <tr><td><code>npm_provenance</code></td><td><code>boolean | null</code></td><td>npm SLSA provenance attestation</td><td>Methodology v2.0</td></tr>
    <tr><td><code>pypi_provenance</code></td><td><code>boolean | null</code></td><td>PyPI PEP 740 attestation</td><td>Methodology v2.0</td></tr>
    <tr><td><code>has_provenance</code></td><td><code>boolean | null</code></td><td><code>npm_provenance OR pypi_provenance</code> (derived)</td><td>Methodology v2.0</td></tr>
    <tr><td><code>scorecard_score</code></td><td><code>float | null</code></td><td>OSSF Scorecard overall score [0–10]</td><td>Methodology v2.0</td></tr>
    <tr><td><code>scorecard_checks</code></td><td><code>object | {}</code></td><td>Per-check Scorecard scores</td><td>Methodology v2.0</td></tr>
    <tr><td><code>signed_commits_ratio</code></td><td><code>float | null</code></td><td>Fraction of signed commits [0.0–1.0]</td><td>Methodology v2.0</td></tr>
  </tbody>
</table>

<h2 id="app-b"><span class="sec-num">B.</span> Coverage as of 2026-05-24</h2>
<table class="spec-table">
  <thead><tr><th>Signal</th><th>Coverage</th><th>Notes</th></tr></thead>
  <tbody>
    <tr><td><code>signed_commits_ratio</code></td><td>65/65 (100%)</td><td>GitHub API always returns data for accessible repos</td></tr>
    <tr><td><code>npm_provenance = true</code></td><td>4/11 npm-tracked agents</td><td>4 of 11 npm packages use Trusted Publishing</td></tr>
    <tr><td><code>pypi_provenance = true</code></td><td>7/46 PyPI-tracked agents</td><td>Most packages predate PEP 740 (2024)</td></tr>
    <tr><td><code>has_provenance</code></td><td>11/65 (17%)</td><td>At least one of npm or PyPI provenance present</td></tr>
    <tr><td><code>scorecard_score</code></td><td>3/65 (5%)</td><td>securityscorecards.dev fallback added 2026-05-24; untested in production</td></tr>
  </tbody>
</table>
""",
}

DATA_SCHEMA_V01 = {
    "title": "HVTracker Data Schema Specification",
    "slug": "data-schema",
    "version": "v0.1",
    "status": "Published",
    "date": "2026-05-25",
    "authors": ["HVTracker"],
    "abstract": (
        "This document defines the schema for all machine-readable data published "
        "by HVTracker at the /data/ endpoint family. It specifies the URL catalog, "
        "field definitions, data types, nullability rules, refresh cadence, and "
        "the versioning policy governing schema evolution. Consumers implementing "
        "integrations against HVTracker data SHOULD validate against this specification "
        "to ensure compatibility across schema versions."
    ),
    "sections": [
        {"id": "s1", "num": "1.", "title": "Abstract"},
        {"id": "s2", "num": "2.", "title": "Motivation"},
        {"id": "s3", "num": "3.", "title": "Terminology"},
        {"id": "s4", "num": "4.", "title": "Endpoint Catalog",
         "subsections": [
             {"id": "s4-1", "num": "4.1", "title": "/data/latest.json"},
             {"id": "s4-2", "num": "4.2", "title": "/data/agents/<slug>.json"},
             {"id": "s4-3", "num": "4.3", "title": "/data/signals/scorecard.json"},
             {"id": "s4-4", "num": "4.4", "title": "/data/signals/provenance.json"},
             {"id": "s4-5", "num": "4.5", "title": "/data/history/<YYYY-MM-DD>.json"},
             {"id": "s4-6", "num": "4.6", "title": "/data/index.html"},
         ]},
        {"id": "s5", "num": "5.", "title": "Field Definitions",
         "subsections": [
             {"id": "s5-1", "num": "5.1", "title": "Envelope Fields"},
             {"id": "s5-2", "num": "5.2", "title": "Agent Record Fields"},
             {"id": "s5-3", "num": "5.3", "title": "History Point Fields"},
             {"id": "s5-4", "num": "5.4", "title": "Signal Subset Fields"},
         ]},
        {"id": "s6", "num": "6.", "title": "Schema Evolution"},
        {"id": "s7", "num": "7.", "title": "Data License"},
        {"id": "s8", "num": "8.", "title": "Versioning and Changelog"},
    ],
    "appendices": [
        {"id": "app-a", "num": "A.", "title": "Field Quick Reference"},
    ],
    "body": """
<h2 id="s1"><span class="sec-num">1.</span> Abstract</h2>
<p>This document defines the schema for all machine-readable data published by HVTracker at the <code>/data/</code> endpoint family. It specifies the URL catalog, field definitions, data types, nullability rules, refresh cadence, and the versioning policy governing schema evolution.</p>
<p>The key words <span class="must">MUST</span>, <span class="must">MUST NOT</span>, <span class="should">SHOULD</span>, <span class="should">SHOULD NOT</span>, and <span class="may">MAY</span> in this document are to be interpreted as described in <a href="https://www.rfc-editor.org/rfc/rfc2119" target="_blank" rel="noopener">RFC 2119</a>.</p>

<h2 id="s2"><span class="sec-num">2.</span> Motivation</h2>
<p>HVTracker publishes daily health scores and trust signals for open-source AI agent projects. As third-party consumers begin building integrations — dashboards, alerts, research pipelines — the absence of a formal schema creates fragility: a field rename or type change silently breaks downstream consumers.</p>
<p>A formal data schema specification serves three purposes:</p>
<ul>
  <li><strong>Stability contract:</strong> Consumers can depend on documented fields not changing without a version increment.</li>
  <li><strong>Discovery:</strong> The endpoint catalog and field definitions document what data exists, removing the need to reverse-engineer <code>data.json</code>.</li>
  <li><strong>Trust:</strong> A versioned, published schema signals that the dataset is intended as infrastructure, not just a build artifact.</li>
</ul>

<h2 id="s3"><span class="sec-num">3.</span> Terminology</h2>
<dl>
  <dt><strong>Snapshot</strong></dt>
  <dd>A complete dataset capture as of a single daily cron run. Each snapshot contains all agent records with values reflecting the state of the world at generation time.</dd>
  <dt><strong>Agent record</strong></dt>
  <dd>A JSON object representing a single tracked project. Every agent record contains at minimum the fields defined in Section 5.2.</dd>
  <dt><strong>Signal</strong></dt>
  <dd>A measured attribute of an agent record. Signals are either activity signals (stars, commits, HN mentions), trust signals (provenance, scorecard, signed commits), or behavioral signals (future: public action counts).</dd>
  <dt><strong>Envelope</strong></dt>
  <dd>The top-level fields present in every endpoint response, defined in Section 5.1. Envelope fields carry metadata about the response itself rather than about individual agents.</dd>
  <dt><strong>Slug</strong></dt>
  <dd>A URL-safe identifier derived from the agent name by lowercasing and replacing non-alphanumeric characters with hyphens. Used to construct per-agent endpoint URLs.</dd>
  <dt><strong>Null</strong></dt>
  <dd>A JSON <code>null</code> value indicating the signal could not be collected during this cron run. <code>null</code> is semantically distinct from zero and from the absence of a field.</dd>
</dl>

<h2 id="s4"><span class="sec-num">4.</span> Endpoint Catalog</h2>
<p>All endpoints are static JSON files (except the HTML index) served from <code>https://hvtracker.net/data/</code>. Files are regenerated on each daily cron run at 06:00 UTC. CORS header <code>Access-Control-Allow-Origin: *</code> is set on all <code>/data/*</code> responses.</p>

<h3 id="s4-1"><span class="sec-num">4.1</span> /data/latest.json</h3>
<p><strong>Content:</strong> Full snapshot — envelope fields plus an <code>agents</code> array containing all active agent records.</p>
<p><strong>Refresh:</strong> Daily at 06:00 UTC, atomically replaced.</p>
<p><strong>Use case:</strong> Primary integration point. Fetch once daily to get the complete leaderboard.</p>
<p><strong>Size bound:</strong> <span class="should">SHOULD</span> remain under 500 KB. If the dataset grows beyond this, the maintainer <span class="must">MUST</span> split the endpoint or switch to pagination before the next schema version.</p>

<h3 id="s4-2"><span class="sec-num">4.2</span> /data/agents/&lt;slug&gt;.json</h3>
<p><strong>Content:</strong> Single agent record (all fields from Section 5.2) plus a <code>history</code> array containing the last 90 days of daily snapshots for this agent (Section 5.3).</p>
<p><strong>URL construction:</strong> <code>https://hvtracker.net/data/agents/{slug}.json</code> where <code>{slug}</code> is the agent's slug as defined in Section 3.</p>
<p><strong>Refresh:</strong> Daily at 06:00 UTC.</p>
<p><strong>Size bound:</strong> <span class="should">SHOULD</span> remain under 50 KB per file.</p>
<p><strong>Note:</strong> Files for legacy agents are also generated but tagged with <code>"status": "legacy"</code> in the agent record.</p>

<h3 id="s4-3"><span class="sec-num">4.3</span> /data/signals/scorecard.json</h3>
<p><strong>Content:</strong> Envelope fields plus an <code>agents</code> array where each element contains only the fields: <code>repo</code>, <code>name</code>, <code>scorecard_score</code>, <code>scorecard_checks</code>, <code>signed_commits_ratio</code>.</p>
<p><strong>Use case:</strong> Supply-chain security consumers who need trust signals without the full dataset.</p>

<h3 id="s4-4"><span class="sec-num">4.4</span> /data/signals/provenance.json</h3>
<p><strong>Content:</strong> Envelope fields plus an <code>agents</code> array where each element contains: <code>repo</code>, <code>name</code>, <code>has_provenance</code>, <code>npm_provenance</code>, <code>pypi_provenance</code>.</p>
<p><strong>Use case:</strong> Package provenance monitoring, SBOM pipelines.</p>

<h3 id="s4-5"><span class="sec-num">4.5</span> /data/history/&lt;YYYY-MM-DD&gt;.json</h3>
<p><strong>Content:</strong> Full snapshot for the named calendar date (UTC). Same structure as <code>/data/latest.json</code>.</p>
<p><strong>Permanence:</strong> Historical files are never deleted or overwritten. A file at <code>/data/history/2026-05-25.json</code> will remain accessible indefinitely.</p>
<p><strong>Availability:</strong> Files exist for every date on which the cron ran successfully. Gaps are possible during outages.</p>

<h3 id="s4-6"><span class="sec-num">4.6</span> /data/index.html</h3>
<p><strong>Content:</strong> Human-readable HTML catalog listing all available endpoints with descriptions, links, and generation metadata. Not machine-readable.</p>

<h2 id="s5"><span class="sec-num">5.</span> Field Definitions</h2>

<h3 id="s5-1"><span class="sec-num">5.1</span> Envelope Fields</h3>
<p>Every endpoint response (except <code>/data/index.html</code>) is a JSON object containing the following envelope fields at the top level.</p>
<table class="spec-table">
  <thead><tr><th>Field</th><th>Type</th><th>Nullable</th><th>Description</th></tr></thead>
  <tbody>
    <tr><td><code>schema_version</code></td><td><code>string</code></td><td>No</td><td>Schema version string, e.g. <code>"v0.1"</code>. Incremented per Section 6.</td></tr>
    <tr><td><code>generated_at</code></td><td><code>string</code></td><td>No</td><td>ISO 8601 UTC timestamp of this cron run, e.g. <code>"2026-05-25 06:00 UTC"</code>.</td></tr>
    <tr><td><code>methodology_version</code></td><td><code>string</code></td><td>No</td><td>Methodology spec version used to compute scores, e.g. <code>"v2.0"</code>.</td></tr>
    <tr><td><code>license</code></td><td><code>string</code></td><td>No</td><td>Data license declaration. Current value: <code>"CC BY 4.0 — https://creativecommons.org/licenses/by/4.0/"</code>.</td></tr>
    <tr><td><code>updated</code></td><td><code>string</code></td><td>No</td><td>Human-readable generation time (same as <code>generated_at</code>).</td></tr>
    <tr><td><code>total</code></td><td><code>integer</code></td><td>No</td><td>Count of active (non-legacy) agent records in this snapshot.</td></tr>
    <tr><td><code>agents</code></td><td><code>array</code></td><td>No</td><td>Array of agent records. See Section 5.2.</td></tr>
  </tbody>
</table>

<h3 id="s5-2"><span class="sec-num">5.2</span> Agent Record Fields</h3>
<p>Each element of the <code>agents</code> array is an agent record with the following fields.</p>
<table class="spec-table">
  <thead><tr><th>Field</th><th>Type</th><th>Nullable</th><th>Description</th></tr></thead>
  <tbody>
    <tr><td><code>name</code></td><td><code>string</code></td><td>No</td><td>Display name of the project.</td></tr>
    <tr><td><code>repo</code></td><td><code>string</code></td><td>No</td><td>GitHub repository path, e.g. <code>"All-Hands-AI/OpenHands"</code>.</td></tr>
    <tr><td><code>url</code></td><td><code>string</code></td><td>No</td><td>Canonical GitHub URL.</td></tr>
    <tr><td><code>rank</code></td><td><code>integer</code></td><td>No</td><td>Global rank by health score (1 = highest). Active agents only.</td></tr>
    <tr><td><code>previous_rank</code></td><td><code>integer | null</code></td><td>Yes</td><td>Rank from the previous daily snapshot. <code>null</code> for newly added agents.</td></tr>
    <tr><td><code>rank_delta</code></td><td><code>integer | null</code></td><td>Yes</td><td>Change in rank since previous snapshot. Positive = improved rank.</td></tr>
    <tr><td><code>stars</code></td><td><code>integer</code></td><td>No</td><td>GitHub star count at collection time.</td></tr>
    <tr><td><code>stars_fmt</code></td><td><code>string</code></td><td>No</td><td>Human-formatted star count, e.g. <code>"45.2k"</code>.</td></tr>
    <tr><td><code>forks</code></td><td><code>integer</code></td><td>No</td><td>GitHub fork count at collection time.</td></tr>
    <tr><td><code>forks_fmt</code></td><td><code>string</code></td><td>No</td><td>Human-formatted fork count.</td></tr>
    <tr><td><code>last_push</code></td><td><code>string</code></td><td>No</td><td>ISO 8601 UTC timestamp of the most recent push to the default branch.</td></tr>
    <tr><td><code>days_ago</code></td><td><code>integer</code></td><td>No</td><td>Days since <code>last_push</code> as of the collection date.</td></tr>
    <tr><td><code>weekly_commits</code></td><td><code>integer | null</code></td><td>Yes</td><td>Commit count in the trailing 4 weeks. <code>null</code> if the GitHub stats API did not return data.</td></tr>
    <tr><td><code>commits_low_confidence</code></td><td><code>boolean</code></td><td>No</td><td><code>true</code> when <code>weekly_commits</code> was derived from a single-page estimate rather than a full count.</td></tr>
    <tr><td><code>score</code></td><td><code>number</code></td><td>No</td><td>Health score [0–100] computed per Methodology v2.0. One decimal place.</td></tr>
    <tr><td><code>description</code></td><td><code>string | null</code></td><td>Yes</td><td>Repository description from GitHub API.</td></tr>
    <tr><td><code>language</code></td><td><code>string | null</code></td><td>Yes</td><td>Primary programming language reported by GitHub.</td></tr>
    <tr><td><code>open_issues</code></td><td><code>integer</code></td><td>No</td><td>Open issue count at collection time.</td></tr>
    <tr><td><code>category</code></td><td><code>string</code></td><td>No</td><td>HVTracker category. One of: <code>Coding Agents</code>, <code>Agent Frameworks</code>, <code>Workflow Platforms</code>, <code>Browser &amp; Computer Use</code>, <code>LLM Gateways &amp; Infra</code>, <code>Memory &amp; Knowledge</code>, <code>Research &amp; Data</code>, <code>Multi-Agent Systems</code>.</td></tr>
    <tr><td><code>category_rank</code></td><td><code>integer | null</code></td><td>Yes</td><td>Rank within the agent's category.</td></tr>
    <tr><td><code>npm_package</code></td><td><code>string</code></td><td>No</td><td>npm package name if tracked, else empty string.</td></tr>
    <tr><td><code>pypi_package</code></td><td><code>string</code></td><td>No</td><td>PyPI package name if tracked, else empty string.</td></tr>
    <tr><td><code>weekly_downloads</code></td><td><code>integer | null</code></td><td>Yes</td><td>Combined weekly download count (npm + PyPI). <code>null</code> if no package is tracked or download fetch failed.</td></tr>
    <tr><td><code>dl_source</code></td><td><code>string</code></td><td>No</td><td>Source label for <code>weekly_downloads</code>, e.g. <code>"pypi"</code>, <code>"npm+pypi"</code>. Empty string if no downloads tracked.</td></tr>
    <tr><td><code>hn_mentions_30d</code></td><td><code>integer | null</code></td><td>Yes</td><td>Count of Hacker News story mentions in the trailing 30 days. <code>null</code> if no search term configured.</td></tr>
    <tr><td><code>has_provenance</code></td><td><code>boolean | null</code></td><td>Yes</td><td>Derived: <code>true</code> if <code>npm_provenance</code> or <code>pypi_provenance</code> is <code>true</code>.</td></tr>
    <tr><td><code>npm_provenance</code></td><td><code>boolean | null</code></td><td>Yes</td><td>SLSA provenance attestation detected on npm package. <code>null</code> if no npm package tracked.</td></tr>
    <tr><td><code>pypi_provenance</code></td><td><code>boolean | null</code></td><td>Yes</td><td>PEP 740 attestation detected on PyPI package. <code>null</code> if no PyPI package tracked.</td></tr>
    <tr><td><code>signed_commits_ratio</code></td><td><code>number | null</code></td><td>Yes</td><td>Fraction of recent commits with GPG/SSH signatures [0.0–1.0]. <code>null</code> if unavailable.</td></tr>
    <tr><td><code>scorecard_score</code></td><td><code>number | null</code></td><td>Yes</td><td>OSSF Scorecard overall score [0.0–10.0]. <code>null</code> if not yet scanned.</td></tr>
    <tr><td><code>scorecard_checks</code></td><td><code>object</code></td><td>No</td><td>Per-check Scorecard scores as a flat object. Empty object <code>{}</code> if no scorecard data.</td></tr>
  </tbody>
</table>

<h3 id="s5-3"><span class="sec-num">5.3</span> History Point Fields</h3>
<p>Each element of the <code>history</code> array in per-agent endpoint responses (Section 4.2) is a history point:</p>
<table class="spec-table">
  <thead><tr><th>Field</th><th>Type</th><th>Nullable</th><th>Description</th></tr></thead>
  <tbody>
    <tr><td><code>date</code></td><td><code>string</code></td><td>No</td><td>Calendar date of this snapshot, <code>YYYY-MM-DD</code> format (UTC).</td></tr>
    <tr><td><code>rank</code></td><td><code>integer | null</code></td><td>Yes</td><td>Global rank on this date.</td></tr>
    <tr><td><code>score</code></td><td><code>number | null</code></td><td>Yes</td><td>Health score on this date.</td></tr>
    <tr><td><code>stars</code></td><td><code>integer | null</code></td><td>Yes</td><td>Star count on this date.</td></tr>
  </tbody>
</table>

<h3 id="s5-4"><span class="sec-num">5.4</span> Signal Subset Fields</h3>
<p>Signal subset endpoints (Sections 4.3 and 4.4) use the same envelope as Section 5.1 but their <code>agents</code> array contains a reduced record. The exact field set for each subset is defined in Sections 4.3 and 4.4 respectively.</p>

<h2 id="s6"><span class="sec-num">6.</span> Schema Evolution</h2>
<p>The schema is versioned as <code>v{major}.{minor}</code>. The <code>schema_version</code> envelope field carries the current version string.</p>

<h3>6.1 Additive changes (minor version bump)</h3>
<p>The following changes increment the minor version and are considered non-breaking:</p>
<ul>
  <li>Adding a new field to agent records or envelope.</li>
  <li>Adding a new endpoint to the catalog.</li>
  <li>Widening a type (e.g., <code>integer</code> → <code>integer | null</code>).</li>
  <li>Adding new allowed values to an enum field.</li>
</ul>
<p>Consumers <span class="should">SHOULD</span> be written to ignore unknown fields so that minor version bumps do not break integrations.</p>

<h3>6.2 Breaking changes (major version bump)</h3>
<p>The following changes increment the major version:</p>
<ul>
  <li>Removing or renaming an existing field.</li>
  <li>Changing a field's type in a non-widening way.</li>
  <li>Changing the meaning of an existing field.</li>
  <li>Removing an endpoint from the catalog.</li>
  <li>Changing the URL structure of an existing endpoint.</li>
</ul>
<p>When a major version is published, the previous major version's <code>/data/latest.json</code> remains accessible for a minimum of 90 days at a versioned URL (e.g., <code>/data/v0/latest.json</code>).</p>

<h3>6.3 Adding new signal classes</h3>
<p>New signal classes (e.g., behavioral signals introduced in Task 3 of the roadmap) are always introduced as additive fields and result in a minor version bump. They are not included in the health score formula without a Methodology spec version bump.</p>

<h2 id="s7"><span class="sec-num">7.</span> Data License</h2>
<p>All data published at <code>https://hvtracker.net/data/</code> is released under <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">Creative Commons Attribution 4.0 International (CC BY 4.0)</a>.</p>
<p>You are free to share and adapt the data for any purpose, including commercial use, provided you give appropriate credit to HVTracker and link to <code>https://hvtracker.net</code>.</p>
<p>Source data (GitHub stars, commit activity, etc.) is sourced from the GitHub REST API and is subject to GitHub's terms of service. HVTracker does not grant rights to data that it does not own.</p>

<h2 id="s8"><span class="sec-num">8.</span> Versioning and Changelog</h2>
<table class="spec-table">
  <thead><tr><th>Version</th><th>Date</th><th>Summary</th></tr></thead>
  <tbody>
    <tr><td>v0.1</td><td>2026-05-25</td><td>Initial publication. Defines 5 endpoints, 30 agent record fields, envelope format, history points, and schema evolution policy.</td></tr>
  </tbody>
</table>

<h2 id="app-a"><span class="sec-num">A.</span> Field Quick Reference</h2>
<table class="spec-table">
  <thead><tr><th>Field</th><th>Type</th><th>Nullable</th><th>Category</th></tr></thead>
  <tbody>
    <tr><td><code>name</code></td><td>string</td><td>No</td><td>Identity</td></tr>
    <tr><td><code>repo</code></td><td>string</td><td>No</td><td>Identity</td></tr>
    <tr><td><code>url</code></td><td>string</td><td>No</td><td>Identity</td></tr>
    <tr><td><code>rank</code></td><td>integer</td><td>No</td><td>Ranking</td></tr>
    <tr><td><code>previous_rank</code></td><td>integer | null</td><td>Yes</td><td>Ranking</td></tr>
    <tr><td><code>rank_delta</code></td><td>integer | null</td><td>Yes</td><td>Ranking</td></tr>
    <tr><td><code>score</code></td><td>number</td><td>No</td><td>Score</td></tr>
    <tr><td><code>stars</code></td><td>integer</td><td>No</td><td>Activity</td></tr>
    <tr><td><code>forks</code></td><td>integer</td><td>No</td><td>Activity</td></tr>
    <tr><td><code>last_push</code></td><td>string</td><td>No</td><td>Activity</td></tr>
    <tr><td><code>days_ago</code></td><td>integer</td><td>No</td><td>Activity</td></tr>
    <tr><td><code>weekly_commits</code></td><td>integer | null</td><td>Yes</td><td>Activity</td></tr>
    <tr><td><code>weekly_downloads</code></td><td>integer | null</td><td>Yes</td><td>Activity</td></tr>
    <tr><td><code>hn_mentions_30d</code></td><td>integer | null</td><td>Yes</td><td>Community</td></tr>
    <tr><td><code>category</code></td><td>string</td><td>No</td><td>Classification</td></tr>
    <tr><td><code>language</code></td><td>string | null</td><td>Yes</td><td>Classification</td></tr>
    <tr><td><code>has_provenance</code></td><td>boolean | null</td><td>Yes</td><td>Trust</td></tr>
    <tr><td><code>npm_provenance</code></td><td>boolean | null</td><td>Yes</td><td>Trust</td></tr>
    <tr><td><code>pypi_provenance</code></td><td>boolean | null</td><td>Yes</td><td>Trust</td></tr>
    <tr><td><code>signed_commits_ratio</code></td><td>number | null</td><td>Yes</td><td>Trust</td></tr>
    <tr><td><code>scorecard_score</code></td><td>number | null</td><td>Yes</td><td>Trust</td></tr>
    <tr><td><code>scorecard_checks</code></td><td>object</td><td>No</td><td>Trust</td></tr>
  </tbody>
</table>
""",
}

BUILD_REPORT_V01 = {
    "title": "Build Integrity Report",
    "slug": "build-report",
    "version": "v0.1",
    "date": "2026-05-26",
    "status": "Draft",
    "authors": ["HVTracker"],
    "abstract": (
        "Machine-readable self-audit of the HVTracker build pipeline. Generated "
        "on each cron run, reporting configured agents, active agents, eligibility "
        "warnings, failed fetches, and signal coverage statistics."
    ),
    "sections": [
        {"id": "s1", "num": "1", "title": "Purpose"},
        {"id": "s2", "num": "2", "title": "Endpoint"},
        {"id": "s3", "num": "3", "title": "Fields"},
        {"id": "s4", "num": "4", "title": "Usage"},
    ],
    "body": """
<h2 id="s1">1. Purpose</h2>
<p>The build integrity report provides a machine-readable summary of each HVTracker data pipeline run. It answers: <em>"What exactly was generated, from what source, how many succeeded, and what failed?"</em></p>
<p>If HVTracker is to serve as a trust registry, its own data pipeline must be transparent. This report is the self-audit.</p>

<h2 id="s2">2. Endpoint</h2>
<p><code>GET /data/build_report.json</code></p>
<p>Generated during every cron run by <code>fetch_and_build.py</code>. Refreshes daily at 06:00 UTC alongside all other data endpoints.</p>

<h2 id="s3">3. Fields</h2>
<table>
  <thead>
    <tr><th>Field</th><th>Type</th><th>Description</th></tr>
  </thead>
  <tbody>
    <tr><td><code>generated_at</code></td><td>string (ISO 8601)</td><td>Timestamp when the report was generated</td></tr>
    <tr><td><code>data_timestamp</code></td><td>string</td><td>Human-readable timestamp shown on the leaderboard</td></tr>
    <tr><td><code>schema_version</code></td><td>string</td><td>Data schema version (e.g. "v0.1")</td></tr>
    <tr><td><code>methodology_version</code></td><td>string</td><td>Methodology version (e.g. "v2.0")</td></tr>
    <tr><td><code>configured_agents</code></td><td>integer</td><td>Total entries in agents.json (active + legacy)</td></tr>
    <tr><td><code>active_agents</code></td><td>integer</td><td>Successfully fetched and scored agents</td></tr>
    <tr><td><code>legacy_agents</code></td><td>integer</td><td>Legacy agents (inactive &ge;365 days, rendered separately)</td></tr>
    <tr><td><code>total_generated</code></td><td>integer</td><td>Total agent profile pages generated (active + legacy)</td></tr>
    <tr><td><code>categories</code></td><td>object</td><td>Map of category name &rarr; agent count</td></tr>
    <tr><td><code>warnings</code></td><td>array</td><td>Eligibility violations (criterion, repo, detail)</td></tr>
    <tr><td><code>warning_count</code></td><td>integer</td><td>Number of eligibility warnings</td></tr>
    <tr><td><code>failed_fetches</code></td><td>array</td><td>Repos that could not be fetched (404, rate limit, etc.)</td></tr>
    <tr><td><code>missing_repos_count</code></td><td>integer</td><td>Count of failed fetches</td></tr>
    <tr><td><code>package_failures</code></td><td>array</td><td>Repos with configured package but no download data</td></tr>
    <tr><td><code>package_failure_count</code></td><td>integer</td><td>Count of package lookup failures</td></tr>
    <tr><td><code>scorecard_unavailable_count</code></td><td>integer</td><td>Agents without OSSF Scorecard data</td></tr>
    <tr><td><code>fingerprint_agents</code></td><td>array</td><td>Repos with fingerprint-based action tracking configured</td></tr>
    <tr><td><code>fingerprint_agent_count</code></td><td>integer</td><td>Count of fingerprint-tracked agents</td></tr>
  </tbody>
</table>

<h2 id="s4">4. Usage</h2>
<p>Consumers can use this report to:</p>
<ul>
  <li>Monitor pipeline health (failed fetch count trending up = API issue)</li>
  <li>Verify data freshness (compare <code>generated_at</code> against expectations)</li>
  <li>Audit signal coverage (scorecard unavailable count, package failures)</li>
  <li>Track growth (configured vs active agents over time)</li>
</ul>
<p>This report is public. It is part of HVTracker's commitment to transparent data sourcing.</p>
""",
}

RUNTIME_TRUST_V01 = {
    "title": "Runtime Trust Signals",
    "slug": "runtime-trust",
    "version": "v0.2",
    "date": "2026-07-05",
    "status": "Active",
    "authors": ["HVTracker"],
    "abstract": (
        "How HVTracker discovers runtime-trust signals — MCP server support, "
        "external service dependencies, tool/plugin surface, and package "
        "provenance drift — and how they calibrate the production trust score: "
        "a headroom-scaled bonus with absolute penalties, and an evidence-first "
        "tie-break. Live in the production rank since methodology v4.0."
    ),
    "sections": [
        {"id": "s1", "num": "1", "title": "Purpose"},
        {"id": "s2", "num": "2", "title": "Status: Live in the Production Rank"},
        {"id": "s3", "num": "3", "title": "Runtime Discovery Fields"},
        {"id": "s4", "num": "4", "title": "Production Scoring"},
        {"id": "s5", "num": "5", "title": "Data Access"},
        {"id": "s6", "num": "6", "title": "Calibration and Promotion Criteria"},
        {"id": "s7", "num": "7", "title": "Versioning"},
    ],
    "body": """
<h2 id="s1">1. Purpose</h2>
<p>Supply-chain trust tells you whether an agent's <em>code and packages</em> are what they claim. Runtime trust asks a different question: <em>what can this agent reach once it runs?</em> An agent that ships an MCP server, calls many external providers, or exposes a plugin marketplace has a materially different risk surface than a self-contained library — regardless of how clean its build provenance is.</p>
<p>This spec documents the four runtime-trust signals HVTracker discovers for every tracked agent, and the experimental scoring that incorporates them. It exists so the methodology is public <strong>before</strong> any of it affects the production ranking.</p>

<h2 id="s2">2. Status: Live in the Production Rank</h2>
<p>Since methodology v4.0 (2026-07-02), the runtime-calibrated score in &sect;4 <strong>is</strong> the production <code>trust_score</code>/<code>rank</code>/<code>evidence_grade</code> — on the leaderboard, agent pages, the <code>/data</code> API, badges, and signed credentials. Promotion followed the evidence gate in &sect;6 (an upset review); the pre-calibration baseline stays visible on the leaderboard for comparison.</p>
<p>v4.1 (2026-07-05) added a soft ceiling and an evidence-first tie-break (&sect;4). No change ships as a silent reweight: every adjustment is documented here and in the <a href="/methodology/#runtime-calibration">methodology</a>.</p>

<h2 id="s3">3. Runtime Discovery Fields</h2>
<p>Each tracked agent carries four runtime fields, discovered by static analysis of the repository and its published package metadata. Every field reports a <code>status</code>, a <code>confidence</code> (<code>high</code> / <code>medium</code> / <code>low</code>), and an <code>evidence</code> array of human-readable findings, so any consumer can audit why a value was assigned.</p>
<table>
  <thead>
    <tr><th>Field</th><th>Statuses</th><th>What it captures</th></tr>
  </thead>
  <tbody>
    <tr><td><code>mcp_server_support</code></td><td><code>implemented</code>, <code>declared</code>, <code>none</code></td><td>Whether the project ships or declares a Model Context Protocol server</td></tr>
    <tr><td><code>external_service_dependencies</code></td><td><code>providers</code> list + <code>requires_api_keys</code></td><td>Third-party services the agent calls at runtime (LLM providers, APIs)</td></tr>
    <tr><td><code>tool_plugin_surface</code></td><td><code>plugin_system</code>: <code>marketplace</code>, <code>extension-based</code>, <code>declared</code>, <code>none</code>; plus <code>tool_tags</code></td><td>How much third-party code the agent can load and execute</td></tr>
    <tr><td><code>package_provenance_drift</code></td><td><code>match</code>, <code>partial</code>, <code>unknown</code>, <code>not_applicable</code>, <code>warning</code></td><td>Whether the published package matches the tracked repository</td></tr>
  </tbody>
</table>
<p>These fields are recorded in every daily history snapshot, building an append-only time series of runtime-surface drift per agent.</p>

<h2 id="s4">4. Production Scoring</h2>
<p>The runtime-calibrated score is the base trust score plus a bounded runtime adjustment, clamped to [0,&nbsp;100]. Since methodology v4.0 this IS the production <code>trust_score</code>/<code>rank</code>/<code>evidence_grade</code>. Reference implementation: <code>compute_trust_score_v2</code> in <code>fetch_and_build.py</code>. The per-dimension adjustments are:</p>
<table>
  <thead>
    <tr><th>Dimension</th><th>Adjustment</th></tr>
  </thead>
  <tbody>
    <tr><td>MCP server support</td><td><code>implemented</code> +2.0 &middot; <code>declared</code> 0 &middot; <code>none</code> 0</td></tr>
    <tr><td>External dependencies</td><td>&minus;0.5 per provider beyond the first, capped at &minus;3.0; additional &minus;1.0 if API keys are required</td></tr>
    <tr><td>Tool/plugin surface</td><td>&minus;0.3 per tool tag, capped at &minus;1.5; plus <code>marketplace</code> &minus;1.0, <code>extension-based</code> &minus;0.6, <code>declared</code> &minus;0.3</td></tr>
    <tr><td>Provenance drift</td><td><code>match</code> +4.0 &middot; <code>partial</code> +2.0 &middot; <code>unknown</code>/<code>not_applicable</code> 0 &middot; <code>warning</code> &minus;5.0</td></tr>
  </tbody>
</table>
<p><strong>Soft ceiling (v4.1).</strong> The <em>positive</em> terms above are scaled by remaining headroom — <code>factor = min(1, (100 &minus; base) / 20)</code>, i.e. full effect at base &le; 80, phasing to zero at base 100 — before being added. <em>Penalties are not scaled.</em> This prevents bonuses from clamping multiple strong agents onto an identical 100.0.</p>
<p><strong>Tie-break (v4.1).</strong> Agents with an exactly equal score are ordered by hardest-to-fake evidence first: <code>trust_confidence</code> &rarr; OSSF <code>scorecard_score</code> &rarr; <code>signed_commits_ratio</code> &rarr; activity/momentum &rarr; stars &rarr; slug. They share a rank (<code>=N</code>) on the leaderboard.</p>
<p>Each agent publishes <code>trust_score</code>, the net <code>trust_v2_adjustment</code>, the applied <code>trust_v2_headroom_factor</code>, and a per-dimension <code>trust_v2_breakdown</code>, so every point of difference from the base score is attributable.</p>

<h2 id="s5">5. Data Access</h2>
<ul>
  <li><code>GET /data/latest.json</code> — all agents, including runtime fields and v2 scores</li>
  <li><code>GET /data/agents/{slug}.json</code> — per-agent record</li>
  <li><code>GET /data/history/YYYY-MM-DD.json</code> — daily snapshots (runtime-drift time series)</li>
  <li><a href="/methodology/#runtime-calibration">Methodology — Runtime-Trust Calibration</a> — the human-readable adjustment reference</li>
</ul>

<h2 id="s6">6. Calibration and Promotion Criteria</h2>
<p>Runtime signals moved into the production rank only after an upset review demonstrated the change was evidence-backed, against published criteria: maximum acceptable rank churn, protection of high-grade agents from unexplained drops, no single dimension dominating the adjustment, and this spec being published first. The review is re-run after any recalibration — including the v4.1 soft-ceiling and tie-break change, whose near-zero churn (no grade flips) cleared the gate.</p>

<h2 id="s7">7. Versioning</h2>
<p>This spec versions independently of the scoring methodology. Any change to the adjustment table (&sect;4) requires a version bump and a changelog entry; promotion into production rank requires a new major section documenting the cutover and the evidence that gated it.</p>
""",
}

LISTING_V01 = {
    "title": "HVTracker Listing Lifecycle Specification",
    "slug": "listing",
    "version": "v0.1",
    "status": "Published",
    "date": "2026-05-26",
    "authors": ["HVTracker"],
    "abstract": (
        "This document defines the lifecycle states for agent listings in the "
        "HVTracker registry. It specifies how agents are discovered, listed, "
        "verified, and potentially delisted, along with the criteria and evidence "
        "requirements for each state transition. It also defines the evidence "
        "grade system and trust score methodology."
    ),
    "sections": [
        {"id": "s1", "num": "1.", "title": "Abstract"},
        {"id": "s2", "num": "2.", "title": "Motivation"},
        {"id": "s3", "num": "3.", "title": "Listing States"},
        {"id": "s4", "num": "4.", "title": "State Transitions"},
        {"id": "s5", "num": "5.", "title": "Evidence Grade"},
        {"id": "s6", "num": "6.", "title": "HVTrust Score"},
        {"id": "s7", "num": "7.", "title": "Versioning and Changelog"},
    ],
    "appendices": [
        {"id": "app-a", "num": "A.", "title": "State Diagram"},
    ],
    "body": """
<h2 id="s1"><span class="sec-num">1.</span> Abstract</h2>
<p>This document defines the lifecycle states for agent listings in the HVTracker registry. It specifies how agents transition between states, the evidence required at each stage, the evidence grade system, and the HVTrust composite score methodology.</p>
<p>The key words <span class="must">MUST</span>, <span class="must">MUST NOT</span>, <span class="should">SHOULD</span>, <span class="should">SHOULD NOT</span>, and <span class="may">MAY</span> in this document are to be interpreted as described in <a href="https://www.rfc-editor.org/rfc/rfc2119" target="_blank" rel="noopener">RFC 2119</a>.</p>

<h2 id="s2"><span class="sec-num">2.</span> Motivation</h2>
<p>As HVTracker evolves from a leaderboard into a trust registry, agents need a formal lifecycle beyond "tracked or not." A project may be discovered but unreviewed, listed but not yet verified, or previously listed but now delisted due to archival or license changes. The listing lifecycle provides a vocabulary for these states and defines the evidence thresholds for transitions.</p>

<h2 id="s3"><span class="sec-num">3.</span> Listing States</h2>
<p>Every agent in the HVTracker registry <span class="must">MUST</span> be in exactly one of the following states:</p>
<table class="spec-table">
  <thead><tr><th>State</th><th>Description</th><th>Visible on site</th></tr></thead>
  <tbody>
    <tr><td><code>discovered</code></td><td>Agent identified but not yet reviewed for eligibility.</td><td>No</td></tr>
    <tr><td><code>candidate</code></td><td>Submitted for listing (via issue template or discovery). Under review.</td><td>No</td></tr>
    <tr><td><code>listed</code></td><td>Meets eligibility criteria. Tracked with daily signal collection.</td><td>Yes — full leaderboard entry</td></tr>
    <tr><td><code>verified</code></td><td>Listed + additional manual verification of agent identity and capabilities.</td><td>Yes — with verified badge (future)</td></tr>
    <tr><td><code>warning</code></td><td>Listed but flagged for eligibility issues (archived, no license, stale).</td><td>Yes — with warning indicator</td></tr>
    <tr><td><code>legacy</code></td><td>Historically significant but no longer actively maintained (&gt;365 days inactive).</td><td>Yes — in legacy section</td></tr>
    <tr><td><code>delisted</code></td><td>Removed from active tracking due to disqualification criteria.</td><td>No (historical data preserved)</td></tr>
    <tr><td><code>rejected</code></td><td>Reviewed and determined not to meet eligibility criteria.</td><td>No</td></tr>
  </tbody>
</table>

<h2 id="s4"><span class="sec-num">4.</span> State Transitions</h2>
<p>State transitions are triggered either automatically by the daily build or manually by the registry owner.</p>

<table class="spec-table">
  <thead><tr><th>From</th><th>To</th><th>Trigger</th><th>Type</th></tr></thead>
  <tbody>
    <tr><td>—</td><td><code>discovered</code></td><td>Agent identified in universe scan or external source</td><td>Manual</td></tr>
    <tr><td><code>discovered</code></td><td><code>candidate</code></td><td>GitHub issue submitted or owner initiates review</td><td>Manual</td></tr>
    <tr><td><code>candidate</code></td><td><code>listed</code></td><td>Passes all MUST criteria in <a href="/spec/eligibility/v1.0">Eligibility Spec</a></td><td>Manual</td></tr>
    <tr><td><code>candidate</code></td><td><code>rejected</code></td><td>Fails eligibility review</td><td>Manual</td></tr>
    <tr><td><code>listed</code></td><td><code>verified</code></td><td>Owner manually confirms identity and capabilities</td><td>Manual</td></tr>
    <tr><td><code>listed</code></td><td><code>warning</code></td><td>Automated eligibility check fires (§4.1.1, §4.2.1, §5.1)</td><td>Automatic</td></tr>
    <tr><td><code>warning</code></td><td><code>listed</code></td><td>Warning condition resolved (e.g., license added, repo unarchived)</td><td>Automatic</td></tr>
    <tr><td><code>listed</code></td><td><code>legacy</code></td><td>No meaningful activity in 365+ days</td><td>Manual</td></tr>
    <tr><td><code>listed</code></td><td><code>delisted</code></td><td>Disqualification criterion met (§5.1–5.5 in Eligibility Spec)</td><td>Manual</td></tr>
    <tr><td><code>legacy</code></td><td><code>listed</code></td><td>Project resumes activity</td><td>Manual</td></tr>
  </tbody>
</table>

<div class="note"><strong>Current implementation:</strong> As of v0.1, only <code>listed</code> and <code>legacy</code> states are used in production. Other states are defined for future use. Transitions are manual; automated state changes will be added in a future version.</div>

<h2 id="s5"><span class="sec-num">5.</span> Evidence Grade</h2>
<p>Every listed agent receives an evidence grade (A–D) based on how many independent signal types contribute data for that agent. The grade reflects data coverage, not quality.</p>
<table class="spec-table">
  <thead><tr><th>Grade</th><th>Signal types required</th><th>Interpretation</th></tr></thead>
  <tbody>
    <tr><td><strong>A</strong></td><td>≥5</td><td>Comprehensive coverage — GitHub + downloads + trust signals + fingerprints + HN</td></tr>
    <tr><td><strong>B</strong></td><td>4</td><td>Strong coverage — multiple independent signal families</td></tr>
    <tr><td><strong>C</strong></td><td>3</td><td>Moderate coverage — GitHub + two additional signal types</td></tr>
    <tr><td><strong>D</strong></td><td>1–2</td><td>Limited coverage — GitHub only or GitHub + one other source</td></tr>
  </tbody>
</table>
<p><strong>Signal types counted:</strong></p>
<ol>
  <li><strong>GitHub</strong> — always present (stars, commits, freshness, forks, license)</li>
  <li><strong>Package downloads</strong> — npm and/or PyPI weekly downloads are non-null</li>
  <li><strong>Trust infrastructure</strong> — OSSF Scorecard score is non-null OR package provenance is present</li>
  <li><strong>Behavioral fingerprints</strong> — public action tracking returns data</li>
  <li><strong>Community signals</strong> — Hacker News mention count is non-null</li>
</ol>

<h2 id="s6"><span class="sec-num">6.</span> HVTrust Score</h2>
<p>The HVTrust Score is a composite metric (0–100) that measures trust across five dimensions. It is computed alongside the existing health score but uses different inputs and weights.</p>

<table class="spec-table">
  <thead><tr><th>Dimension</th><th>Max</th><th>Inputs</th></tr></thead>
  <tbody>
    <tr><td><strong>Activity</strong></td><td>25</td><td>Freshness (days since push, linear decay over 180d, max 15) + commit activity (log-scaled, max 10)</td></tr>
    <tr><td><strong>Adoption</strong></td><td>20</td><td>Stars (log-scaled vs 100k, max 12) + weekly downloads (log-scaled vs 1M, max 8)</td></tr>
    <tr><td><strong>Transparency</strong></td><td>20</td><td>License present (8 pts) + OSSF Scorecard contribution (scaled to 12 pts)</td></tr>
    <tr><td><strong>Safety</strong></td><td>20</td><td>OSSF Scorecard (scaled to 10 pts) + package provenance (5 pts) + signed commits ratio (scaled to 5 pts)</td></tr>
    <tr><td><strong>Identity</strong></td><td>15</td><td>Evidence grade (A=10, B=7, C=4, D=1) + listing status (listed=5, legacy=2)</td></tr>
  </tbody>
</table>

<pre>trust_score = activity + adoption + transparency + safety + identity</pre>

<p><strong>Relationship to health score:</strong> The health score (stars + freshness + activity + community = 100) measures <em>momentum</em>. The HVTrust score measures <em>trustworthiness</em>. Both are displayed; the leaderboard can be sorted by either. The health score formula is unchanged — HVTrust is purely additive.</p>

<div class="note"><strong>v0.1 status:</strong> The HVTrust score is experimental. Dimension weights and input scaling may change in future versions. The score is computed daily but does not yet affect default sort order.</div>

<h2 id="s7"><span class="sec-num">7.</span> Versioning and Changelog</h2>
<table class="spec-table">
  <thead><tr><th>Version</th><th>Date</th><th>Summary</th></tr></thead>
  <tbody>
    <tr><td><strong>v0.1</strong></td><td>2026-05-26</td><td>Initial publication. Defines 8 listing states, transition triggers, evidence grade system (A–D), and HVTrust composite score (5 dimensions, 100 points).</td></tr>
  </tbody>
</table>

<h2 id="app-a"><span class="sec-num">A.</span> State Diagram</h2>
<pre style="font-family:var(--font-mono);font-size:12px;line-height:1.5;color:var(--text)">
  discovered → candidate → listed → verified
                  ↓           ↓ ↑
               rejected    warning
                              ↓
                           legacy ↔ listed
                              ↓
                           delisted
</pre>
<p>Arrows indicate valid transitions. Bidirectional arrows (↔) indicate the transition can go either way. The <code>delisted</code> state is terminal in practice but historical data is preserved.</p>
""",
}

TRUST_CREDENTIAL_V01 = {
    "title": "HVTracker Trust Credential Specification",
    "slug": "trust-credential",
    "version": "v0.2",
    "status": "Published",
    "date": "2026-06-18",
    "authors": ["HVTracker"],
    "abstract": (
        "This document defines the Trust Credential: a machine-readable, "
        "versioned record by which HVTracker attests the evidence-weighted "
        "trust of an open-source AI agent. It specifies the credential format, "
        "the lookup and discovery mechanism, and the verification procedure. "
        "The credential is designed to let one agent decide whether to trust "
        "another (agent-to-agent, A2A) before interacting with it."
    ),
    "sections": [
        {"id": "s1", "num": "1.", "title": "Abstract"},
        {"id": "s2", "num": "2.", "title": "Terminology"},
        {"id": "s3", "num": "3.", "title": "Discovery"},
        {"id": "s4", "num": "4.", "title": "Credential Format"},
        {"id": "s5", "num": "5.", "title": "Verification"},
        {"id": "s6", "num": "6.", "title": "Revocation and Freshness"},
        {"id": "s7", "num": "7.", "title": "Signing"},
        {"id": "s8", "num": "8.", "title": "Versioning"},
    ],
    "body": """
<h2 id="s1"><span class="sec-num">1.</span> Abstract</h2>
<p>This document defines the <strong>Trust Credential</strong>: a machine-readable record by which HVTracker attests the evidence-weighted trust of an open-source AI agent. The credential lets a consumer — including another agent (agent-to-agent, A2A) — decide whether to trust an agent before interacting with it.</p>
<p>The key words <span class="must">MUST</span>, <span class="must">MUST NOT</span>, <span class="should">SHOULD</span>, and <span class="may">MAY</span> are to be interpreted as described in <a href="https://www.rfc-editor.org/rfc/rfc2119" target="_blank" rel="noopener">RFC 2119</a>.</p>

<h2 id="s2"><span class="sec-num">2.</span> Terminology</h2>
<dl class="terms">
  <dt>Issuer</dt><dd>The trust authority that produces credentials. For this specification the issuer is <code>hvtracker.net</code>.</dd>
  <dt>Subject</dt><dd>The AI agent a credential describes, identified by its source repository and HVTracker slug.</dd>
  <dt>Consumer</dt><dd>Any party — human, tool, or agent — that reads a credential to make a trust decision.</dd>
</dl>

<h2 id="s3"><span class="sec-num">3.</span> Discovery</h2>
<p>A consumer <span class="should">SHOULD</span> begin at the authority descriptor <code>https://hvtracker.net/.well-known/hvtracker.json</code>, which declares the issuer, the methodology, and the endpoint templates.</p>
<p>An agent's credential is retrieved from <code>https://hvtracker.net/data/agents/{slug}.json</code> under the <code>trust_credential</code> key. The full registry is available at <code>https://hvtracker.net/data/latest.json</code>.</p>

<h2 id="s4"><span class="sec-num">4.</span> Credential Format</h2>
<p>A Trust Credential is a JSON object with the following members:</p>
<pre>
{
  "spec": "https://hvtracker.net/spec/trust-credential/v0.2",
  "version": "0.2",
  "issuer": "hvtracker.net",
  "subject": { "repo": "owner/name", "slug": "name", "agent_url": "https://hvtracker.net/agents/name" },
  "methodology_version": "v3.2",
  "issued_at": "2026-06-18T00:00:00Z",
  "expires_at": "2026-06-25T00:00:00Z",
  "trust_score": 0-100,
  "confidence": 0.0-1.0,
  "evidence_grade": "A|B|C|D",
  "dimensions": { "safety": n, "identity": n, "transparency": n, "maintenance": n, "adoption": n },
  "listing_status": "listed|legacy|delisted|...",
  "evidence_hash": "&lt;sha256-hex&gt;",
  "signature": "&lt;base64-ed25519, or null if the build had no key&gt;"
}
</pre>
<p>A consumer <span class="must">MUST</span> treat <code>confidence</code> as a first-class factor: a high <code>trust_score</code> with low <code>confidence</code> reflects thin evidence and <span class="should">SHOULD NOT</span> be relied upon for high-stakes interactions.</p>

<h2 id="s5"><span class="sec-num">5.</span> Verification</h2>
<p>A credential is signed with Ed25519 and verified <strong>offline</strong>: remove the <code>signature</code> member, serialize the remainder as JSON with <strong>sorted keys</strong>, separators <code>(",",":")</code>, and <code>ensure_ascii=false</code>, then verify the base64 <code>signature</code> against the issuer public key published at <code>/.well-known/hvtracker.json</code>. A consumer <span class="must">MUST</span> reject a credential whose signature does not verify, and <span class="should">SHOULD</span> reject one whose <code>methodology_version</code> it does not recognize.</p>
<p>The <code>evidence_hash</code> is a SHA-256 over the canonical score-bearing fields, binding the score to its evidence snapshot. A consumer <span class="must">MUST</span> treat <code>confidence</code> as first-class, and <span class="may">MAY</span> additionally <strong>reproduce</strong> the score from public signals per the methodology (an implementation conforming to the methodology <span class="must">MUST</span> land within 0.1 points). A <code>null</code> signature means the issuing build had no signing key; such a credential <span class="should">SHOULD</span> be verified by reproduction only.</p>

<h2 id="s6"><span class="sec-num">6.</span> Revocation and Freshness</h2>
<p>Each credential carries <code>issued_at</code> and <code>expires_at</code>. A consumer <span class="must">MUST</span> reject a credential after its <code>expires_at</code> and <span class="should">SHOULD</span> prefer the freshest available. A <code>listing_status</code> of <code>delisted</code> <span class="must">MUST</span> be treated as revocation regardless of score.</p>

<h2 id="s7"><span class="sec-num">7.</span> Signing</h2>
<p>Credentials are signed with <strong>Ed25519</strong>. The issuer public key (base64, raw 32 bytes) is published at <code>/.well-known/hvtracker.json</code> under <code>trust_credential.public_key</code>; the <code>signature</code> is a detached signature over the canonical credential (Section 5). Key rotation re-publishes the public key, so a consumer <span class="should">SHOULD</span> fetch the current key from the authority descriptor rather than pinning it.</p>

<h2 id="s8"><span class="sec-num">8.</span> Versioning</h2>
<p>This specification uses <code>vMAJOR.MINOR</code> versioning. Published versions remain accessible at their versioned URLs and <span class="must">MUST NOT</span> be modified after publication.</p>
""",
}

MCP_SERVER_TRUST_V01 = {
    "title": "HVTracker MCP Server Trust Specification",
    "slug": "mcp-server-trust",
    "version": "v0.1",
    "status": "Draft",
    "date": "2026-06-18",
    "authors": ["HVTracker"],
    "abstract": (
        "This document defines a pre-connect trust verdict for Model Context "
        "Protocol (MCP) servers. An MCP client queries HVTracker before "
        "connecting to a server and receives a signed verdict — trusted or not, "
        "with an evidence grade and reasons — so it can decide whether to "
        "establish the session. It is a reputation layer: it rides on the "
        "identity the MCP transport already provides and does not issue identity."
    ),
    "sections": [
        {"id": "s1", "num": "1.", "title": "Abstract"},
        {"id": "s2", "num": "2.", "title": "Lookup"},
        {"id": "s3", "num": "3.", "title": "Verdict Format"},
        {"id": "s4", "num": "4.", "title": "Policy"},
        {"id": "s5", "num": "5.", "title": "Verification"},
    ],
    "body": """
<h2 id="s1"><span class="sec-num">1.</span> Abstract</h2>
<p>This document defines a <strong>pre-connect trust verdict</strong> for Model Context Protocol (MCP) servers. A client <span class="should">SHOULD</span> query the verdict before connecting and use it to decide whether to proceed. The verdict is a reputation signal layered on the server's existing identity (URL + TLS, package, or repository); HVTracker does not issue identity.</p>

<h2 id="s2"><span class="sec-num">2.</span> Lookup</h2>
<p>Query <code>GET /api/v1/mcp/verify?server=&lt;id&gt;</code> where <code>id</code> is a GitHub repository (<code>owner/name</code> or URL) or an npm/PyPI package name. The server is resolved to its HVTracker trust record; an unresolved server returns <code>tracked:false</code> and <span class="must">MUST</span> be treated as unverified.</p>

<h2 id="s3"><span class="sec-num">3.</span> Verdict Format</h2>
<pre>
{
  "server": "owner/name",
  "resolved": "owner/name",
  "tracked": true,
  "trusted": true,
  "grade": "A|B|C|D",
  "trust_score": 0-100,
  "confidence": 0.0-1.0,
  "reasons": [ "..." ],
  "mcp_server_support": "declared|verified|...",
  "tool_permissions": [ "search", "code", ... ],
  "attestation": { ...signed Trust Credential, subject = the MCP server... }
}
</pre>
<p>A consumer <span class="should">SHOULD</span> surface <code>tool_permissions</code> to the user before granting access, and <span class="must">MUST</span> treat <code>confidence</code> as first-class.</p>

<h2 id="s4"><span class="sec-num">4.</span> Policy</h2>
<p>The default verdict is <code>trusted = true</code> when the server's listing is not <code>delisted</code>, <code>warning</code>, or <code>legacy</code>; its evidence grade is <code>A</code>, <code>B</code>, or <code>C</code>; and its trust score is at least 40. A consumer <span class="may">MAY</span> apply a stricter policy (e.g. require build provenance, or grade ≥ B) using the fields in the verdict.</p>

<h2 id="s5"><span class="sec-num">5.</span> Verification</h2>
<p>The <code>attestation</code> is an Ed25519-signed credential (see <a href="/spec/trust-credential/v0.2">Trust Credential v0.2</a>) whose <code>subject</code> is the MCP server. It is verified <strong>offline</strong> against the issuer key in <code>/.well-known/hvtracker.json</code>, exactly as for agent credentials.</p>
""",
}

# All published specs, in display order (newest first)
ALL_SPECS = [MCP_SERVER_TRUST_V01, TRUST_CREDENTIAL_V01, LISTING_V01, BUILD_REPORT_V01, RUNTIME_TRUST_V01, DATA_SCHEMA_V01, ELIGIBILITY_V1, PROVENANCE_V01, METHODOLOGY_V2]
