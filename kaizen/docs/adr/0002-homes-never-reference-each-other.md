# Homes never reference each other

A user may keep separate homes for unrelated areas of work, and the main risk is information crossing between them.
So no home names or describes another, not even in a git-ignored file, and every isolation check kaizen runs is an allowlist built from the current home's own facts: its root, its registered project paths and repos, and the owners those repos imply.
Anything outside that is refused, whichever home it belongs to.
kaizen itself follows the same rule: nothing it prints, writes or checks names another home, and its templates and tests name no real home, owner or project.

## Considered Options

- **Foreign patterns**: each home lists the other homes' paths and owners to block, committed or in a local untracked file.
  Rejected, because the list itself is a cross-reference.
- **Hashed patterns**: rejected; still a reference, and text search can't match hashes.
- **Owner-level boundaries**: unworkable, because one GitHub owner may hold repos in more than one home, so the boundary is per repo.

## Consequences

An unregistered repo under one of the home's own owners, or a local path outside the home, fails the leak check even when it is legitimate.
Some legitimate text names a path or repo that can't be registered, such as a tool's settings folder or an archived repo, so the home marker may list such paths and repos as allowed, naming only this home's facts.
The fix for a finding is therefore to register it, allow it in the home marker, or remove it.
Third-party owners are never flagged.
