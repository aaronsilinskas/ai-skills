# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

This repo is multi-context, with `kaizen` as its one context.

- **`GLOSSARY-MAP.md`** at the repo root: it points at each context's glossary. Read each one relevant to the topic; for kaizen, that is `kaizen/GLOSSARY.md`.
- **`kaizen/docs/adr/`**: read ADRs that touch the area you're about to work in.
- **`kaizen/docs/domain.md`**: kaizen's domain map, of the code that exists.

There is no root `GLOSSARY.md` or `docs/adr/`. Don't flag their absence or create them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) adds glossaries and ADRs lazily when terms or decisions actually get resolved.

## File structure

```
/
├── GLOSSARY-MAP.md
└── kaizen/
    ├── GLOSSARY.md
    └── docs/
        ├── adr/          ← kaizen's decisions
        └── domain.md
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `GLOSSARY.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal: either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders), but worth reopening because…_
