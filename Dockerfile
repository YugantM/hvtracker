FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY app.py fetch_and_build.py specs.py db.py cache.py storage.py schema.sql ./
# Generator inputs: curated seed, scorecard cache, and templates/assets
COPY agents.json scorecard-cache.json template.html ./
COPY templates/ templates/
COPY .nojekyll robots.txt _headers analytics.js og.png og.svg og-v1.png ./

ENV OUTPUT_DIR=/data/site
EXPOSE 8080

# Generated site + state live on the volume mounted at /data, never in git.
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}"]
