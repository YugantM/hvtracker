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
<p><strong>Scope:</strong> All agents. Coverage depends on upstream indexing.</p>
<p><strong>Sources (tried in order):</strong></p>
<ol>
  <li><strong>Primary — deps.dev:</strong> <code>GET https://api.deps.dev/v3/projects/github.com%2F{owner}%2F{repo}</code> — reads <code>scorecard.overallScore</code> and <code>scorecard.checks</code>.</li>
  <li><strong>Fallback — securityscorecards.dev:</strong> <code>GET https://api.securityscorecards.dev/projects/github.com/{owner}/{repo}</code> — reads <code>score</code> and <code>checks</code>.</li>
</ol>
<p>The fallback is attempted if and only if the primary source returns non-200 or returns 200 with no <code>scorecard</code> field.</p>
<p><strong>What it means:</strong> The OSSF Scorecard score is a weighted aggregate of 10–18 individual checks (Maintained, Code-Review, Branch-Protection, Signed-Releases, Pinned-Dependencies, Vulnerabilities, Token-Permissions, Dangerous-Workflow, and others). HVTracker reports the score as-is; it does not reweight or reinterpret individual checks.</p>
<p><strong>Freshness:</strong> The upstream Scorecard infrastructure runs analyses periodically (typically weekly). HVTracker may report the same score for multiple consecutive days if no new analysis has been completed upstream.</p>
<p><strong>Limitations:</strong> Not all repositories have been indexed. Absence of a score does not imply poor security posture. The check set and weights are controlled by the OpenSSF Scorecard project, not HVTracker, and may change between Scorecard versions.</p>

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

# All published specs, in display order (newest first)
ALL_SPECS = [ELIGIBILITY_V1, PROVENANCE_V01, METHODOLOGY_V2]
