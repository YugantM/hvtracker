# ---- builder: python deps + freshest scorecard cache -----------------------
# Deps install into a venv that is copied wholesale into the runtime stage;
# curl lives only here (python:slim has none — the old single-stage fetch
# silently fell back to the seed on every build).
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
# pip/setuptools are build-time only — prune them from the venv the runtime
# stage inherits.
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt \
    && /opt/venv/bin/pip uninstall -y pip setuptools wheel 2>/dev/null; true

# Try fetching the latest scorecard cache from the data branch (falls back to COPY'd seed)
COPY scorecard-cache.json ./scorecard-cache.json
RUN curl -sfL https://raw.githubusercontent.com/YugantM/hvtracker/data/scorecard-cache.json -o /tmp/sc.json \
    && mv /tmp/sc.json scorecard-cache.json \
    || echo "Using seed scorecard-cache.json (data branch fetch failed)"

# ---- runtime ----------------------------------------------------------------
FROM python:3.12-slim

WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH"

# Non-root user for runtime — gosu lets the entrypoint chown the volume
# (which may have root-owned files from a prior image) then drop to hvt.
# fonts-dejavu-core is a runtime dep (OG-card text rendering via Pillow).
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends fonts-dejavu-core gosu && rm -rf /var/lib/apt/lists/* \
    && groupadd -r hvt && useradd -r -g hvt -d /app -s /sbin/nologin hvt \
    && mkdir -p /data/site

COPY --from=builder /opt/venv /opt/venv

# Application code
COPY app.py fetch_and_build.py generate_og_card.py specs.py db.py cache.py storage.py schema.sql ./
COPY signing.py mcp_trust.py open_lookup.py verify_log.py mcp_server.py auth.py ./
# Generator inputs: curated seed, scorecard cache, and templates/assets
COPY agents.json template.html ./
COPY --from=builder /build/scorecard-cache.json ./scorecard-cache.json
COPY templates/ templates/
COPY docs/import-candidates.json docs/import-candidates.json
COPY compare/index.html compare/index.html
COPY verify/index.html verify/index.html
COPY scan/index.html scan/index.html
COPY static/ static/
COPY blog_static/ blog_static/
COPY changelog/ changelog/
COPY .well-known/ .well-known/
COPY .nojekyll robots.txt analytics.js auth.js og-v2.png og-verify.png og-provenance.png og-mcp.png og-scan.png favicon.svg hex-bg.svg haystack-logo.png aipass-logo.png composio-logo.svg lightrag-logo.png ./
# render_state.json — baked into the image so that newly-listed agents added
# via git push are synced to the volume on startup (see fetch_and_build.py).
COPY data/render_state.json data/render_state.json
# Seed history snapshots — copied into the volume on first startup if missing.
# Needed so rank-deltas, sparklines, and movers have prior days to compare
# against. Sourced from tracked /seed/history (NOT output/, which .gitignore
# excludes from the `railway up` upload, leaving the seed dir empty).
COPY seed/history/ /app/seed/history/
RUN test -n "$(find /app/seed/history -name '*.json' -print -quit)"

# Ship the exact prebuilt site snapshot from the workspace. This keeps
# emergency hotfix deploys aligned with the verified local container state.
COPY prebuilt/ /app/prebuilt/

RUN chown -R hvt:hvt /app /data

COPY entrypoint.sh /app/entrypoint.sh

ENV OUTPUT_DIR=/data/site
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')"]

ENTRYPOINT ["/app/entrypoint.sh"]
