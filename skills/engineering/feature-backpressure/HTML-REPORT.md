# Audit Report Format

The audit report is one self-contained HTML file: inline CSS, no scripts, no external requests, so it opens from the temp directory anywhere. Write it to `<tmpdir>/feature-audit-<timestamp>.html`, resolving the temp directory from `$TMPDIR`, falling back to `/tmp` (`%TEMP%` on Windows), so each run gets a fresh file and nothing lands in the repo. Open it for the user (`open` on macOS, `xdg-open` on Linux, `start` on Windows) and give them the absolute path.

## Order and cap

- **Candidates** are the features in the cut, merge, shrink and measure buckets.
- Rank them by cost alone, highest first, whatever their bucket, so the costliest features lead. Spread weighs heaviest: compare seams crossed, then interfaces, then files, then classes and functions, and break a tie on lines.
- Show the top 10 as cards. Close the list with a count of the candidates left out, by bucket, so the user can ask for the next batch.
- Keeps and trivials get no cards: show each as a count.
- The ledger gets one line: how many rows were skipped as settled, re-checked, and dropped for features that no longer exist.

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
      .high { background: #dcfce7; color: #166534; } .medium { background: #f5f5f4; color: #44403c; } .low { background: #fafaf9; color: #78716c; border: 1px dashed #a8a29e; }
      .sides { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
      @media (max-width: 40rem) { .sides { grid-template-columns: 1fr; } }
      code { font-family: ui-monospace, monospace; font-size: 13px; }
    </style>
  </head>
  <body>
    <main>
      <header>...</header>
      <section id="candidates">...</section>
      <section id="rest">...</section> <!-- left-out count, keep and trivial counts, ledger line -->
    </main>
  </body>
</html>
```

## Header

The project, the scope audited, the commit, the date, and one line of totals: features found, the count in each bucket, and how many candidates are high-confidence cuts. Straight into the cards after it.

## Candidate card

One `<article>` per candidate:

- **Title**: the feature's name as a user types or sees it (`ticket publish --wait-timeout`), its bucket as a badge, and its confidence as a second badge (`high`, `medium` or `low`).
- **Cost and use**, side by side in the `.sides` grid. Cost: its lines and its spread on two lines, as the skill's **Cost** defines them, and a few words for any failure mode they miss. Use: the count or finding, its source, and the window it covers, counted by the skill's **Counting use** rules.
- **Added**: the date of the commit that added it.
- **Action**: one sentence. For a cut, what goes; for a merge, what it folds into; for a shrink, which parts go; for a measure, the signal it waits for and where it would come from.
- **Confidence**: each of its bucket's criteria, marked held or not held.
- **Value**: the user's rating from the ledger, "not asked: high-confidence cut" for a clear cut, or "ask" for every other candidate.

Prose stays short: one line per field. When a card needs a paragraph, the evidence isn't settled yet.
