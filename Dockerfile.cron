FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fetch_and_build.py specs.py agents.json scorecard-cache.json template.html ./
COPY templates/ templates/
COPY .nojekyll CNAME robots.txt _headers analytics.js og.png og.svg og-v1.png ./
COPY output/ output/
COPY data/ data/
COPY badge/ badge/
COPY blog/ blog/
COPY categories/ categories/
COPY compare/ compare/
COPY spec/ spec/
COPY roadmap/ roadmap/
COPY badges/ badges/
COPY docs/ docs/

COPY cron_runner.sh .
RUN chmod +x cron_runner.sh

CMD ["./cron_runner.sh"]
