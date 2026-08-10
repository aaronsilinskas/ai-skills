# Logic Prototype

A single self-contained HTML file that lets the user drive a state model by hand. Use this when the question is about **business logic, state transitions, or data shape** — the kind of thing that looks reasonable on paper but only feels wrong once you push it through real cases.

## When this is the right shape

- "I'm not sure if this state machine handles the edge case where X then Y."
- "Does this data model actually let me represent the case where..."
- "I want to feel out what the API should look like before writing it."
- Anything where the user wants to **press buttons and watch state change**.

If the question is "what should this look like" — wrong branch. Use [UI.md](UI.md).

## The artifact

**One HTML file — plain HTML, CSS, and JS, no build step and no server.** The user double-clicks it and it opens in a browser. Everything lives inline in that one file. This is deliberately the whole thing: no `package.json`, no bundler, no dev server, nothing to install. It's the easiest artifact in the world to share and to run.

The file has three parts:

1. A **labelled state panel** that renders the full current state after every action.
2. **Always-available free-play buttons** — one per action — so the user can poke at the model in any order.
3. **Tabbed guided walkthroughs** — named scenarios, each with an ordered sequence of buttons, that reset to a known state and step through a case worth examining.

Behind all three sits a **pure reducer** in a `<script>` module — the one part worth keeping.

## Process

### 1. State the question

Before writing code, write down what state model and what question you're prototyping. One paragraph, as a comment at the top of the `<script>` or visible on the page. A logic prototype that answers the wrong question is pure waste — make the question explicit so it can be checked later, whether the user is watching now or returning to it AFK.

### 2. Isolate the logic in a pure reducer

Put the actual logic — the bit that's answering the question — behind a small, pure interface that could be lifted out and dropped into the real codebase later. Everything else in the file (the state panel, the buttons, the tabs) is throwaway; the reducer shouldn't be.

Write it as a pure reducer with the shape `(state, action) => state`: given the current state and an action, it returns the next state. No I/O, no DOM, no `console.log` for control flow — just data in, data out. The UI dispatches actions to it and re-renders from whatever it returns; nothing flows the other direction.

```js
// pure — this is the bit that outlives the prototype
function reduce(state, action) {
  switch (action.type) {
    case 'addUser':   return { ...state, users: [...state.users, action.user] };
    case 'tickClock': return { ...state, now: state.now + 1 };
    default:          return state;
  }
}
```

Keep the reducer honest about this contract even when the underlying model is a state machine or a set of transformations — the `(state, action) => state` shape is what makes it liftable. This is what makes the prototype useful past its own lifetime: once the question's been answered, the validated reducer lifts into the real module and the HTML shell gets thrown away.

**Python-canonical exception.** This repo's convention is that logic is canonical in Python. The logic prototype is the one place that doesn't hold: the artifact is intrinsically JS, because it has to run in a browser with zero setup. So when the host codebase is Python, lifting the reducer means **translating** it — porting the `(state, action) => state` function to idiomatic Python (a `reduce(state, action) -> state` function, or a match statement over action types) — not literally moving the JS. The prototype validated the *shape and behaviour*; the real code re-expresses it in the host language.

### 3. Build the labelled state panel

Render the full current state into a fixed panel, updated after every action. Pretty-print it diff-friendly — one field per line, or formatted JSON in a `<pre>`. Label it clearly ("Current state") and give field names or section headers visual weight (bold, a heading) with less important context (timestamps, IDs, derived values) dimmed. The user should be able to glance at the panel and see exactly what each action changed.

### 4. Add always-available free-play buttons

One button per action the reducer understands, laid out plainly and enabled at all times. Clicking a button dispatches that action through the reducer and re-renders the state panel. This is the sandbox: the user pokes the model in whatever order they like, chasing the "wait, that shouldn't be possible" moments. If an action needs a parameter, a small input next to the button is fine — keep it minimal.

### 5. Add tabbed guided walkthroughs

Alongside free play, offer **named scenarios as tabs**. Each tab is one walkthrough worth stepping through — the edge cases that motivated the prototype ("X then Y then Z", "double-submit", "clock tick mid-flow"). Selecting a tab **resets state to a known starting point** for that scenario, and lays out an **ordered sequence of buttons** underneath. The user clicks them in order and watches the state panel evolve, one deliberate step at a time.

Each scenario dispatches the same actions through the same reducer as free play — the walkthrough is just a curated path, not separate logic. Resetting on tab-select is what makes a scenario reproducible: the user can always return to a tab and get the same sequence from the same start.

### 6. Hand it over

Point the user at the file — "double-click `<name>.html`". They'll drive it themselves; the interesting moments are when they say "wait, that shouldn't be possible" or "huh, I assumed X would be different" — those are the bugs in the _idea_, which is the whole point. If they want new actions or new walkthrough tabs added, add them. Prototypes evolve.

### 7. Capture the answer

When the prototype has done its job, the answer to the question is the only thing worth keeping. If the user is around, ask what it taught them and fold the validated reducer into the real code (translating to the host language where that's Python). Then commit the HTML file to a throwaway `prototype/<name>` branch and leave a context pointer to it on the issue, so the exploration is recoverable without cluttering `main`. See SKILL.md rule 6 for the full capture flow; defer the issue-pointer mechanics to the project's agent docs.

## Anti-patterns

- **Don't add tests.** A prototype that needs tests is no longer a prototype.
- **Don't add a build step or a server.** The whole value is a single file the user double-clicks. No bundler, no framework, no `npm install`.
- **Don't wire it to a real database.** State lives in memory unless the question is specifically about persistence.
- **Don't generalise.** No "what if we wanted to support X later." The prototype answers one question.
- **Don't blur the reducer and the UI together.** If the reducer references the DOM, buttons, or rendering, it's no longer liftable. Keep it a pure `(state, action) => state` function that the UI calls into.
- **Don't ship the HTML shell into production.** The shell is optimised for being poked by hand in a browser. The reducer behind it — translated to the host language where needed — is the bit worth keeping.
