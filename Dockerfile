FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY app.py fetch_and_build.py generate_og_card.py specs.py db.py cache.py storage.py schema.sql ./
# Generator inputs: curated seed, scorecard cache, and templates/assets
COPY agents.json scorecard-cache.json template.html ./
COPY templates/ templates/
COPY compare/index.html compare/index.html
COPY blog_static/ blog_static/
COPY changelog/ changelog/
COPY .well-known/ .well-known/
COPY .nojekyll robots.txt analytics.js og-v2.png og-provenance.png ./
# render_state.json — baked into the image so that newly-listed agents added
# via git push are synced to the volume on startup (see fetch_and_build.py).
COPY data/render_state.json data/render_state.json
# Seed history snapshots — copied into the volume on first startup if missing.
# Needed so rank-deltas, sparklines, and movers have prior days to compare against.
COPY output/history/ /app/seed/history/

ENV OUTPUT_DIR=/data/site
EXPOSE 8080

# Generated site + state live on the volume mounted at /data, never in git.
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}"]
