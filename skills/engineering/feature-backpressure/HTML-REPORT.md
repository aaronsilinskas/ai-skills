# Audit Report Format

The audit report is one self-contained HTML file: inline CSS, no scripts, no external requests, so it opens from the temp directory anywhere. Write it to `<tmpdir>/feature-audit-<timestamp>.html`, resolving the temp directory from `$TMPDIR`, falling back to `/tmp` (`%TEMP%` on Windows), so each run gets a fresh file and nothing lands in the repo. Open it for the user (`open` on macOS, `xdg-open` on Linux, `start` on Windows) and give them the absolute path.

## Order and cap

- **Candidates** are the features in the cut, merge, shrink and measure buckets.
- Sort them by bucket in that order, then by cost, highest first, so the costliest cuts lead.
- Show the top 10 as cards. Close the list with a count of the candidates left out, by bucket, so the user can ask for the next batch.
- Keeps and trivials get no cards: show each as a count, with the units' names in one collapsed `<details>` list.
- Ledger rows skipped as settled get one line: how many, and that the ledger holds them.

## Scaffold

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Feature audit of {{project}}</title>
    <style>
      body { font: 15px/1.5 system-ui, sans-serif; background: #fafaf9; color: #1c1917; margin: 0; }
      main { max-width: 60rem; margin: 0 auto; padding: 2rem 1rem; }
      article { background: #fff; border: 1px solid #e7e5e4; border-radius: 8px; padding: 1rem 1.25rem; margin: 1rem 0; }
      .badge { display: inline-block; padding: 0 .5rem; border-radius: 999px; font-size: 12px; text-transform: uppercase; letter-spacing: .05em; }
      .cut { background: #fee2e2; color: #991b1b; } .merge { background: #ede9fe; color: #5b21b6; }
      .shrink { background: #fef3c7; color: #92400e; } .measure { background: #e0f2fe; color: #075985; }
      .sides { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
      @media (max-width: 40rem) { .sides { grid-template-columns: 1fr; } }
      code { font-family: ui-monospace, monospace; font-size: 13px; }
    </style>
  </head>
  <body>
    <main>
      <header>...</header>
      <section id="candidates">...</section>
      <section id="rest">...</section>
    </main>
  </body>
</html>
```

## Header

The project, the scope audited, the commit, the date, and one line of totals: units found, then the count in each bucket. Straight into the cards after it.

## Candidate card

One `<article>` per candidate:

- **Title**: the feature's name as a user types or sees it (`ticket publish --wait-timeout`), and its bucket as a badge.
- **Cost and use**, side by side in the `.sides` grid. Cost: what the feature adds (code, tests, docs, config surface, failure modes). Use: the count or finding, its source, and the window it covers, with the method rule applied (calls from the building session dropped, outcomes counted for setup commands, trigger rate for once-per-trigger units).
- **Added**: the date of the commit that added it.
- **Action**: one sentence. For a cut, what goes; for a merge, what it folds into; for a shrink, which parts go; for a measure, the signal it waits for and where it would come from.
- **Value**: the user's rating from the ledger, or "ask" when cost and use leave the feature undecided.

Prose stays short: one line per field. When a card needs a paragraph, the evidence isn't settled yet.

## Rest of the audit

After the cards: the count of candidates left out by bucket, the keep and trivial counts with their names collapsed, and the ledger lines (rows skipped as settled, rows due for a re-check, rows dropped for features that no longer exist).
