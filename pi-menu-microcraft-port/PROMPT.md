# Prompt: port the new MicroCraft HTML into pi-menu

Paste this as the task, after the skill is loaded. Fill in the file name.

---

Port `<new HTML file>` into the `pi-menu` repo as the `pi-microcraft`
app, following the `pi-menu-microcraft-port` skill exactly.

1. Read SKILL.md and REFERENCE.md in full before touching code.
2. Step 0: pin the version. If the file I named is not the tracked
   `MicroCraft — 16×16.html`, copy it over that name and commit it alone.
3. Step 1: build the feature ledger from the stripped diff of the
   previous tracked HTML against the new one, plus the open items in
   REFERENCE.md §8. Every new function name is in a ledger row.
4. Step 2: choose extend or rebuild by the rule in SKILL.md and write
   the reason.
5. Step 3: write and commit the plan under `docs/superpowers/plans/`.
6. Steps 4-8: regenerate the art untouched, copy every table cell for
   cell, implement one ledger row per commit in dependency order,
   transcribe every `draw*` and `hitTest*` function, wire the session
   and the keys.
7. Step 9: tests with every commit; the suite green at every commit.
8. Step 10: run the suite, dump one PNG per screen from a seeded
   session and look at each, time a tick.
9. Step 11: the review pass.
10. Step 12: README section and `HELP` string for every key and screen
    (registration too if the app is new).
11. Step 13: the final report with the ledger, deviations, verification
    output verbatim, and open items.

Rules that are not negotiable:

- The art is the HTML's, extracted and drawn verbatim. No recolour.
- Tables, constants, layouts and draw order come from the HTML line,
  never from memory.
- Nothing runs on the panel or in Tk during this task; everything below
  `app.py` is headless and is verified by tests and PNG dumps.
- No new runtime dependencies.
- Do not stop until the definition of done in SKILL.md is met or an
  item is written up as deferred with a reason.
