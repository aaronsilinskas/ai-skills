# `home sync` overwrites synced files, and the home's git history keeps local edits

Synced files are kaizen's.
`kaizen home sync` re-renders them and overwrites any local edit, and the home's git history is the record of what changed.
A home's own rules go in the home overlay, which sync never touches.

Sync doesn't try to detect local edits.
A home's synced files are committed to its git repo, so a local edit that sync replaces appears in the diff of the commit that records the sync, and stays recoverable from history.

## Considered Options

- **Refusing to overwrite a locally edited file.**
  This needs a stored checksum of each file sync wrote, and an agent to reconcile the edit before every sync.
  Rejected: git already shows and keeps the edit, so the extra state and friction buy nothing.
- **Merging local edits into the new version**, automatically or by recording an accepted merged copy as a new baseline.
  Rejected: prose conflicts arrive on every release, and homes drift from kaizen's version.
- **Per-home template overrides or patches.**
  Rejected: they stop receiving kaizen's changes, and break when template wording changes.

## Consequences

Commit the home before syncing, then review the sync's diff before committing it.
Anything worth keeping from an overwritten edit moves to the home overlay, or upstream into kaizen's template.
