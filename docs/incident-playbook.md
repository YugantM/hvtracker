# Incident playbook

Incidents are HVTracker's only proven source of search clicks. After
Composio's May 2026 security incident, "is composio safe" held an average
position of 2.8 and drew more clicks than any other query (31 Aug–27 Sep).
People search for a project's safety when something has just gone wrong. A
current page and a prompt post catch that interest.

## Advisories (automatic detection)

`.github/workflows/incident-watch.yml` runs daily. It opens an
`incident-watch` issue for each critical or high OSV advisory, published in
the last 14 days, that affects a listed project's latest release. Older
advisories still show on the page and still cap the score, but they are no
longer news. The profile page and the score cap
(methodology v4.4) update on their own at the next full fetch. The issue lists
what still needs a person:

1. Check that the profile shows the advisory (use `?cb=1`; the edge may serve
   a stale copy).
2. Post on X within 2 days. The issue includes a draft; edit it into your own
   voice.
3. Close the issue once a fixed release ships. The cap lifts on the next full
   fetch.

## Incidents without an advisory (manual)

Vendor breach disclosures, hijacked maintainer accounts, malicious releases
pulled before OSV lists them, and hosted-service bugs never reach OSV. When
you see one about a listed project:

1. Add a `source_note` to the project's roster entry in `agents.json`,
   stating the facts in one or two sentences with a link to the primary
   source. It renders as the "Tracking note" on the profile. Ship it as a
   normal PR.
2. Post on X with the profile link, as above.
3. Remove the note once it's no longer current (for example, the vendor
   published a post-mortem and a fix).

Never change a score by hand. Scores move only through evidence (CLAUDE.md).
