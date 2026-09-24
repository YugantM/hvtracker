# Dataset DOI via Zenodo (plan 3.3)

Each quarter's export (`/data/exports/hvtrust-<YYYY>-Q<n>.json.gz` and `.csv`,
CC BY 4.0) keeps refreshing until its quarter ends, then freezes. A frozen
quarter can be deposited on Zenodo for a permanent DOI, so papers and reports
can cite a fixed version and the citation becomes a durable referring link.

## Once per quarter, after it ends (Q3 2026: from 1 October)

1. Package it:

   ```bash
   python scripts/package_dataset.py 2026-Q3
   ```

   This downloads the frozen export, checks the JSON and CSV agree, and writes
   `dist/hvtrust-2026-Q3/` (data, README with the data dictionary,
   `.zenodo.json`) plus `dist/hvtrust-2026-Q3.zip`. It refuses to package a
   quarter that hasn't ended.

2. On zenodo.org (your account): New upload → upload the files from
   `dist/hvtrust-2026-Q3/` → fill the form from `.zenodo.json` (type Dataset,
   licence CC BY 4.0, title, description, keywords, related identifiers;
   add yourself as a creator if you want personal credit) → Publish.
   Later quarters: use **New version** on the first record, so every quarter
   shares one concept DOI.

3. Record the DOI where readers look: add it to the export section of the
   `/data-api/` page (`app.py`, the `curl -sO …exports/…` block) and as a
   `preferred-citation`/`references` entry in `CITATION.cff`. The export
   files themselves don't change: a past quarter's file is frozen, and the
   DOI record on Zenodo is the citable copy.

`dist/` is gitignored.
