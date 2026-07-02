---
name: domain-modeling
description: Build and sharpen a project's domain docs — the map (`domain.md`: modules, key types, constraints) and the language (`domain-language.md`: canonical terms + what to avoid). Use when pinning down terminology, adding a module/type/constraint to the domain map, or when another skill needs to keep the domain docs current.
argument-hint: "term, module, or constraint to capture (or leave blank to review the domain)"
---

# Domain Modeling

Actively build and sharpen the project's domain docs *as you design* — inline, the moment things crystallise, not as a separate chore. Two artifacts, one clean boundary:

- **`domain.md` — the map.** Module layout, key types (and where they live), and project constraints. Structure and navigation.
- **`domain-language.md` — the language.** The glossary: canonical terms and the words to avoid. Meaning and naming.

(Merely *reading* these for context is not this skill — that's a one-line habit any skill can do. This skill is for when you're *changing* the model.)

## What goes where

For any fact that comes up, route it by kind:

- **Structure** — a new module, a key type and where it lives, a project-wide constraint → **`domain.md`**
- **Meaning** — what a term means, and which words to avoid for it → **`domain-language.md`**
- **Mechanics** — how a class works internally, method signatures, algorithms → the **code** (carried by naming + tests), not these docs
- **Decisions** — "why we chose X over Y" → the work's **GitHub issue** (grilling captures it there)

The two docs must not overlap: **never define a term in `domain.md`** (that's the language's job), and **never record structure or mechanics in `domain-language.md`** (it stays a glossary). Duplication between them is the main way they drift out of sync.

## File structure

Both docs live under `docs/` (or at the repo root):

```
/
├── docs/
│   ├── domain.md              ← the map
│   └── domain-language.md     ← the language
└── src/
```

When the language grows too large for one file, promote it to a folder split by subdomain, with a short index; `domain.md` is the natural place to link the pieces:

```
/
├── docs/
│   ├── domain.md
│   └── domain-language/
│       ├── README.md      ← index of subdomains
│       ├── effects.md
│       ├── game.md
│       └── hardware.md
└── src/
```

Create files lazily — only when you have something to write.

> **A language folder is an organizational split, not a semantic one.** It is *not* a DDD **context map** — that documents the relationships between genuinely *separate* models, each with its own language, where the same word can mean different things across the boundary (often separate services or repos). Only reach for a context map if you actually have multiple distinct models to integrate; don't design for it otherwise.

## During the session

### Challenge against the glossary

When the user uses a term that conflicts with the existing language in `domain-language.md`, call it out immediately. "Your glossary defines 'cancellation' as X, but you seem to mean Y — which is it?"

### Sharpen fuzzy language

When the user uses vague or overloaded terms, propose a precise canonical term. "You're saying 'account' — do you mean the Customer or the User? Those are different things."

### Discuss concrete scenarios

When domain relationships are being discussed, stress-test them with specific scenarios. Invent scenarios that probe edge cases and force the user to be precise about the boundaries between concepts.

### Cross-reference with code

When the user states how something works, check whether the code agrees. If you find a contradiction, surface it: "Your code cancels entire Orders, but you just said partial cancellation is possible — which is right?"

### Update the docs inline

Capture changes the moment they land — don't batch them up.

- **A term is resolved, coined, or sharpened** → update `domain-language.md`, using the format in [domain-language-format.md](./domain-language-format.md).
- **A new module, key type, or project constraint appears** → update the relevant section of `domain.md` (module layout, key types and their location, or constraints).

### Keep the map honest

`domain.md` holds only structure: what modules exist, what the key types are and where they live, what constraints apply. Keep it free of term *definitions* (those belong in `domain-language.md` — link to it, don't restate it) and of implementation *mechanics* (those belong in the code). When a module is renamed, moved, or removed, fix `domain.md` in the same pass so the map never lies about the code.

### Where decisions go

Neither doc records decisions. Durable "why we chose X over Y" rationale lives in the work's GitHub issue (grilling captures it there as the plan is sharpened), not in a separate decision document.

## Reviewing the whole domain

Inline maintenance is the default. When the user asks to *review the domain* for inconsistencies, sweep the sources against each other and report the drift before fixing (with the user):

- Does `domain.md`'s structure still match the code (modules, key type locations, constraints)?
- Does `domain-language.md` match how terms are actually used in the code and conversation?
- Do the two docs overlap anywhere — a term defined in both, or structure/mechanics leaking into the language file? Collapse it to one home.
