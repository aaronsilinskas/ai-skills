# kaizen's version comes from the global install, not a per-home pin

kaizen is installed once per machine, and every home runs that install as bare `kaizen`.
A home records only its **synced version**, the release it was last synced with.
Each command compares the two.
A newer install prints a one-line warning to run `kaizen home sync`.
An older install refuses with the upgrade command, because the home's synced files may describe commands that install lacks.
CI checks the synced files with the recorded release through `uvx --refresh-package kaizen-kit --from kaizen-kit==<synced version>`.

A short command for agents and the user mattered more than per-home pins.
Since one user runs every home on a machine, the user upgrading the install is enough to prompt each home's sync.

## Considered Options

- **A per-home pin run through `uv run kaizen`**, with the pin in a `pyproject.toml` dev group that Dependabot bumps.
  Rejected as too verbose for every command, doc and hook.
- **A launcher that re-runs itself at the home's pin through `uvx`.**
  Rejected as hidden behaviour for little gain over a warning.

## Consequences

Dependabot doesn't bump kaizen, so nothing announces a release.
`kaizen home sync` checks PyPI once for a newer release and prints the upgrade command, and no other command uses the network.
