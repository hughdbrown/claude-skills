---
name: pi-menu-microcraft-port
description: Use when a new version of the MicroCraft HTML game (or any single-file HTML/JS game) must be ported or re-synced into the pi-menu repo as a Stellar Unicorn 16x16 app, when Tyler ships a new MicroCraft HTML, when src/pi_menu/microcraft/ must catch up with the HTML at the repo root, or when someone asks to add a new panel app in the pi-menu framework.
---

# Porting a MicroCraft HTML version into pi-menu

## Overview

The HTML file is the specification. The port is a transcription of it into
pure Python that draws on the 16×16 Stellar Unicorn LED panel through the
pi-menu framework. Every number, table, pixel position, draw order and rule
comes from the HTML; nothing is invented, tuned, restyled or "improved".

**Core principle: copy, don't compose.** Three port passes have been made.
Every correction the user had to give came from an LLM composing something
from memory or taste (a recolour of the art, a furnace screen drawn "about
right", a break time for a tile the HTML never lists) instead of copying the
HTML line. The art is drawn verbatim. The layouts are the HTML's hit tests.
The constants are the HTML's constants.

**REQUIRED BACKGROUND:** read [REFERENCE.md](REFERENCE.md) before writing
code. It holds the HTML anatomy, the framework contract, the module map,
extension-point recipes and the test recipes. This file is the procedure.

## Inputs and constraints

- Repo: `~/workspace/tyler/pi-menu`. Python via `.venv/bin/python`
  (3.14 on the dev Mac), tests via `.venv/bin/pytest -q`.
- Reference HTML: the tracked `MicroCraft — 16×16.html` at the repo root.
  The extraction tool reads exactly that path.
- Existing port: `src/pi_menu/microcraft/` (17 modules, ~4,800 lines),
  tests `tests/test_microcraft_*.py`, tool `tools/extract_microcraft_sprites.py`.
- The dev Mac has no `_tkinter` and no panel. Nothing in this workflow
  requires either: every module below `app.py` runs headless, and the
  `Recorder` sink in the session tests captures frames as bytes.
- No new runtime dependencies. Pillow is already a dependency and is used
  by the extraction tool only. Never decode PNGs at run time.
- Tkinter shell, 115200 baud, 20 Hz tick, `FramePump`, the four display
  backends: all fixed framework decisions. Do not touch them.
- The user wants sharp decisions and code, not approval rounds. Decide,
  state the decision in the plan file, and build.

## The procedure

Work through the steps in order. Each step names its output. Do not skip
a step because the delta "looks small"; the 2026-09-13 delta looked like
"a furnace" and was 49 new functions.

### Step 0 — Pin the source version

Output: one paragraph in the plan file naming the file, its line count,
and how it relates to the version already ported.

1. `git log --oneline -- "MicroCraft — 16×16.html"` shows which HTML
   versions were committed and when. `git status` shows untracked copies
   at the root. `cmp` each untracked copy against the tracked file:
   identical copies are just uploads; a different one may be the new
   version that has not yet been committed.
2. Confirm with the user's message which file is "the next version". If
   it is not yet the tracked `MicroCraft — 16×16.html`, copy it over that
   name and commit it alone first: `Use newer HTML game version`. The
   tool, the docs and the tests all refer to that one path.
3. Trap from the first port: the working-tree HTML was 3,910 lines while
   the committed one was 1,380. Port the file the user handed you, and
   make the committed file match before the first code commit.
4. There is no version constant in the HTML. Establish order by content:
   the newer file has every function name of the older one plus more.

### Step 1 — Catalogue the delta

Output: a feature ledger table in the plan file, one row per feature,
columns: HTML symbols | Python module | test file | status.

Strip the base64 first, then diff the previously ported HTML against the
new one. The previous version is the second-newest commit that touched
the tracked file, found from the file's own history, never from `HEAD~1`
(after Step 0's commit `HEAD~1` may or may not be it):

```bash
H="MicroCraft — 16×16.html"; S=$(mktemp -d)
PREV=$(git log -2 --format=%H -- "$H" | tail -1)          # the previously ported version
git show "$PREV:$H" | sed -E "s#data:image/png;base64,[A-Za-z0-9+/=]+#B64#g" > $S/old.js
sed -E "s#data:image/png;base64,[A-Za-z0-9+/=]+#B64#g" "$H" > $S/new.js
diff -u $S/old.js $S/new.js > $S/delta.diff
for v in old new; do grep -E '^\s*function \w+' $S/$v.js | sed -E 's/.*function (\w+).*/\1/' | sort -u > $S/$v.fn; done
comm -13 $S/old.fn $S/new.fn                       # new functions
comm -23 $S/old.fn $S/new.fn                       # removed functions
grep -cE '^@@' $S/delta.diff; wc -l < $S/new.fn    # hunks vs functions: the "changed" measure for Step 2
diff <(grep -E '^\s*(const|let) ' $S/old.js) <(grep -E '^\s*(const|let) ' $S/new.js)   # changed constants, any indent
grep -nE "^\s*\w+\.src = 'data:image/png;base64," "$H"   # sheets
git diff --stat "$PREV" HEAD -- "$H"                # sanity: the diff is not empty
```

Everything in the game is a `const`/`let`/`function` inside one IIFE;
top-level declarations sit at two-space indent, but a few constants live
inside functions at deeper indent (`SPIDER_BG_WEB_CHANCE` inside
`genLayerChunk`), so the constant diff runs at any indent. Read
`delta.diff` end to end. Then read the new HTML end to end once; the diff
tells you what changed, the file tells you how it fits.

Group the delta into the feature categories in REFERENCE.md §4 (tile or
item, sheet, table, recipe, screen, sim, mob, player stat, HUD element,
key, sky or weather effect, terrain pass, loop change). For each row note:

- every HTML symbol that belongs to it (constants, state object,
  functions, the branch in `loop`, the branch in `handleInteract`, the
  key handler, the touch button),
- silent numeric changes (`hp` 10→16, `FLUID_TICK_MS` 150→220 both
  happened without any function changing), found by the `const` diff,
- sheets whose base64 changed length: same name and same size does not
  mean same pixels. Re-decode every sheet every port.

Then check the ledger against the Python: `grep -rn <symbol_or_concept>
src/pi_menu/microcraft/`. A feature the HTML has and the Python lacks is a
row. A feature the Python has and the HTML dropped is a row (removal).
Include the rows that were still open at the last port (REFERENCE.md §8)
so they are ported or explicitly deferred this time.

Ledger granularity: one row per feature as the player sees it. A feature
that spans categories (a chest is a block, a sheet, a recipe and a
screen) is one row whose task lists the categories in the order of
REFERENCE.md §4. A row that a later row depends on (hp and `damage()`
before any mob that bites; a sheet before the tile that uses it) comes
first; write the dependency in the row. One commit per row; split a row
into commits by category only when it would exceed a few hundred lines.

### Step 2 — Choose the strategy: extend or rebuild

Output: one line in the plan file, `Strategy: extend` or
`Strategy: rebuild`, with the reason.

Both strategies use every other step of this procedure unchanged. The
choice only decides whether new code lands inside the existing modules or
in a fresh package that replaces them.

Choose **extend** when all of these hold:

- tile and item ids of the old version are unchanged in the new one
  (ids are only ever appended),
- `VIEW`, `BLOCK`, `WORLD_H`, `WORLD_RADIUS`, `CHUNK_W`, `SURFACE_BASE`
  are unchanged, and the existing branches of `loop` and `draw` keep
  their order (new branches appended for new screens or mobs are fine),
- the existing module boundaries still describe the game (a new feature
  maps onto one of the extension points in REFERENCE.md §4),
- `pytest -q tests/test_microcraft_*.py` is green at the start.

Choose **rebuild** when any of these hold:

- ids were renumbered, the world size or the screen model changed, or the
  existing branches of `loop` were reordered or merged,
- more than about half the HTML's functions are new, removed or changed:
  new plus removed from the `comm` lines, changed approximated by the
  hunk count of `delta.diff`, all against the function count of `new.fn`,
- the user asks for "a complete port starting with the HTML", as on
  2026-09-13,
- the existing package fails its own tests and the failures are in the
  areas the delta touches.

Rebuild means: a new package written from the HTML in the dependency order
of REFERENCE.md §3, reusing the existing modules only by reading them as
worked examples of the framework contract, then deleting the old package
in the final commit. Do not "rebuild" by editing in place and calling it
new; do not "extend" by rewriting a module wholesale and leaving its tests
describing the old behaviour.

### Step 3 — Write the plan and commit it

Output: `docs/superpowers/plans/YYYY-MM-DD-microcraft-<label>.md`, where
`<label>` is the user's file name or the HTML's line count (there is no
version constant), committed alone as `docs(microcraft): plan the port of
<label>`.

The plan holds: the version paragraph (Step 0), the strategy line (Step
2), the feature ledger (Step 1), the deliberate deviations (start from the
list in REFERENCE.md §7 and add only what the panel forces), the key map
if it changed, and one task per ledger row in dependency order with the
tests it will add and its commit message. The 2026-09-09 plan at
`docs/superpowers/plans/2026-09-09-microcraft.md` is the model for shape
only; its key table and its "palette recolour" paragraph describe an
older version and a reverted decision.

### Step 4 — Regenerate the art

Output: `sprites.py` regenerated, the palette and tiles tests green, one
commit.

1. If the HTML added a sheet, append its `(jsVariable, PY_NAME)` pair to
   `SHEETS` in `tools/extract_microcraft_sprites.py` (the tuple's order
   only sets the order in `sprites.py`; it need not match the HTML).
2. Transparency: a pixel is `None` only where alpha is 0, or where the
   HTML itself bakes black to transparent at load (today only
   `furnaceProgressImg`, in `BLACK_IS_TRANSPARENT`). Find such cases by
   reading each sheet's `onload` handler in the HTML. Every other sheet
   keeps `(0, 0, 0)` as an opaque colour.
3. Run `.venv/bin/python tools/extract_microcraft_sprites.py`, then
   `.venv/bin/pytest -q tests/test_microcraft_tiles.py tests/test_microcraft_palette.py`.
   Regenerated pixels change values that tests pin (`UI_SHEET[0][0]` went
   white→black in the last port and the suite was committed red). Fix the
   tests in the same commit as the regenerated sheet.
4. `palette.py` is a pass-through: every `palette.X_SHEET is sprites.X_SHEET`.
   Alias a new sheet there and add it to `test_every_sheet_is_the_html_art_untouched`.
   Do not recolour, lift, re-hue or redraw any tile. If a sheet is hard to
   read on the LEDs, say so in the final report; the user decides.
5. Flat colours the HTML paints with `fillStyle` (bars, washes, the
   player, the button) become named constants holding the HTML's literal
   hex converted to RGB, next to `FUEL_FILL` in `palette.py` or beside
   the drawing code, with the hex in a comment.

### Step 5 — Copy the tables

Output: `tiles.py` (and any table module) matching the HTML, pinned by
tests, one commit.

The HTML's tables are the source of truth and are copied cell for cell:
ids, `SHEET_POS`, `FLUID_SHEET_POS`, `ITEM_SHEET_POS`, `NAMES`, the type
sets, `ARMOR_TYPE_SLOT`, `FLUID_META`, `BREAK_TIME_MS`, `AXE_BLOCKS`,
`PICKAXE_BLOCKS`, the multipliers, `BREAK_DROP_TYPE`, `PICKAXE_TIER`,
`DROP_REQUIRES_PICKAXE_TIER`, `FUEL_UNITS`, `SMELT_RECIPES`, the recipe
pattern lists, the starter kit, the sky keyframes, the cloud type table,
the demo shot list. The same applies to the scalar constants, which are
where silent changes hide: physics (`GRAV`, `MOVE`, `JUMP`, the fall and
swim clamps), `MAX_HP` and the damage and oxygen numbers, the tick periods
(`FLUID_TICK_MS`, `GRASS_TICK_MS`, `CLOUD_COVERAGE_TICK_MS`,
`RAIN_SPAWN_MS`), `Q_DROP_WINDOW_MS`, `DOUBLE_TAP_MS`, `BURN_DURATION_TICKS`,
`GRASS_DECAY_TICKS`, the mob constants. Rules:

- A table entry the HTML does not have does not exist in Python. The
  last port added `WEBBING: 1200` to break times; the HTML falls back to
  the 2500 default. Model the fallback, not a made-up value.
- Transcribe numbers by reading the HTML line, not from memory. The last
  port had tungsten multipliers at 0.16; the HTML says 0.15.
- Pin each table and each constant group with a test that spells out the
  HTML values (see `test_the_starter_kit_matches_the_html`; add
  `test_physics_constants_match_the_html` and
  `test_tick_periods_match_the_html` if they do not exist). When the next
  version changes a number, the test fails and names the line to update.
  A test that uses the constant symbolically (`phys.GRAV * 3`) pins
  nothing.
- Names of slot groups and regions stay the HTML's strings (`'inv'`,
  `'tableCraft'`, `'furnaceFuel'`, `'openCraft'`, `'oxygen'`).

### Step 6 — Implement feature by feature

Output: one commit per ledger row, each with its tests, the suite green
at every commit.

Order: the dependency order in REFERENCE.md §3 (`noise → tiles → sprites →
palette → canvas → terrain → sim → inventory → furnace → player → sky →
weather → demo → render → session → app`). Within a feature, follow the
extension-point recipe for its category in REFERENCE.md §4; each recipe
lists every file and function the feature touches, so nothing is left
half-wired (the item strip in the last port had render, keys and state but
an unreachable branch, so the key did nothing).

Translation rules that apply everywhere:

- One HTML function becomes one Python function or method in the module
  its region maps to. Free functions keep the HTML name in snake_case
  (`simulateFire` → `simulate_fire`); methods drop the noun the class
  already carries (`hitTestFurnaceUI` → `Inventory.hit_furnace`,
  `updateSpiders` → `Spiders.update`). Keep the HTML's argument order and
  its early returns. Always put the HTML function name in the docstring
  so the next diff can find it by grep.
- State lives where the HTML keeps it, with the HTML's key. A per-block
  map (`pebbles` keyed `"layer,x,y"`) is a dict on `World` keyed
  `(layer, x, y)`. An array of mobs (`const spiders = []`) is a list. A
  single global object (`furnace`) is one instance on the session. A
  screen that edits per-block or per-object slots binds `Inventory`'s
  group to that object's slot list while the screen is open (one source
  of truth) instead of copying slots in and out; the furnace's hand
  mirroring (`_sync_furnace_slots` / `_push_furnace_slots`) is the shape
  to replace, not to copy.
- `Math.round` is `noise.round_half_up`, never Python's `round`.
  `Math.floor` on possibly negative values is `math.floor`, never `int`.
  `Math.imul` and `>>> 0` are 32-bit masked arithmetic as in `noise.hash2`.
- `Math.random()` is `self.rng.random()` on the injected `random.Random`.
  `performance.now()` and `frameDt` are `Session.now_ms` and the tick's
  `dt_ms`. `Date.now()` is only for the real moon phase via `wall_clock`.
- Per-frame code in the HTML (60 Hz) that integrates velocity runs as
  physics substeps: `steps = max(1, round(dt_ms / STEP_MS))`. Per-frame
  code that only accumulates time takes the whole tick's `dt_ms`.
- Interval sims (`FLUID_TICK_MS` and friends) are accumulator `while`
  loops in `Session._simulate`; copy the period constant.
- Anything the HTML runs every frame regardless of screen (today
  `updateSelName`, `updateItemStrip`, `updateFurnace`) runs in
  `Session.tick` before the screen branch, not inside it. The last port
  put the furnace inside the world branch, so it stopped while its own
  screen was open.
- Randomness in world generation comes only from hashed noise of
  `(x, y, seed)`. Where the HTML uses `Math.random()` inside chunk
  generation (spider spawn chance), use the injected rng and note the
  deviation.
- Bound scans to the box around the player as `sim._Box` does; never
  scan full 1,250-row columns. Record each bound as a deviation.
- Mobs, drops and any moving thing store x unwrapped as the HTML does,
  and compare positions through `wrap_x`.

### Step 7 — Rendering and layouts are transcribed, not designed

Output: each `draw_*` function is a line-for-line translation of the
HTML's `draw*` function; each screen's layout is pinned by a test that
walks the HTML's hit test.

- Read the HTML's `draw*` function and write the Python in the same
  order of fill and drawImage calls. Every `fillStyle` hex is a constant.
  Every `drawImage(sheet, sx, sy, w, h, dx, dy, w, h)` is
  `canvas.tile(SHEET, sx, sy, dx, dy)` for 2×2, or a loop for other sizes
  (the furnace progress stages are 4×2 bands; `canvas.tile` copies 2×2,
  so the last port showed two of four stages).
- Read the HTML's `hitTest*` function and write `Inventory.hit_<screen>`
  with the same pixel rectangles. Then write the test: for every pixel of
  the 16×16 screen, the region the hit test returns must be what the
  drawn frame shows there (slot art where a slot is, exit tile where the
  exit is). This one test would have caught the furnace screen whose
  backpack rows painted over the progress bar and oxygen button.
- Draw order is the HTML's `draw()` order (REFERENCE.md §2.5). The
  cursor is last. Full-screen washes (flash, damage) come after the HUD.
- HUD rows the HTML draws on the canvas (hp at row 0, oxygen at row 1)
  are drawn on the canvas. Text the HTML puts in the DOM (`#hp`,
  `#selName`, `#layerName`) goes to `status_text()`.

### Step 8 — Session and app wiring

Output: `Screen` enum, `interact`, `back`, `tick`, `framebuffer`,
`status_text` and the key maps in `app.py` all extended; every new key in
the `HELP` string; a session test for every transition.

Map the HTML's `loop` branch structure onto `Session.tick` and
`Session.framebuffer` one branch at a time. Map each keydown handler and
each polled key (`keys['x']` read in an update function) onto a held or a
tapped key; a polled key is held, a handler key is tapped. A held key is a
constant in `HELD_KEYS` plus an entry in `app.HELD_KEYSYMS`. A tapped key
is a constant in `session.py`, an `elif` branch in `Session.press`, and
an entry in `app.TAP_KEYSYMS`; `press` already ends in `push()`, so a new
branch inherits it. If the HTML handler ignores `e.repeat` (the `q`
handler does), the Tk side must filter auto-repeat for that key through
`HeldKeys` rather than `TAP_KEYSYMS`. `release` of a key that changes the
picture, `select_slot` and `tick` also end in `push()`.

### Step 9 — Tests

Output: at least one test file per module touched; the transition,
layout and table tests above; the whole suite green.

- Build the session in tests with
  `Session(recorder, seed=12345, rng=random.Random(1), wall_clock=lambda: 1_700_000_000)`
  and step time with `session.tick()`; never sleep.
- Pure modules take a `World(seed)` and small builders (`shelf()`,
  `row()`, `meadow()` in the sim tests). Stub rng with a class exposing
  only `random()` when a probability must be forced.
- Frames are asserted by pixel through `pixel_offset`; allow ±1 on
  blended pixels only.
- For a screen: one test per region of its hit test, one test that the
  drawn layout matches the hit test, one test per transition in and out
  (Enter on the block, Esc, E), one test that leftovers are returned or
  dropped on close.
- For a sim or mob: one test per rule sentence in the HTML's comments or
  branches (ignites, extinguishes, bakes, recedes, spawns, climbs, falls).
- For a table: one test spelling out the HTML values.
- For the file system and hardware: `tmp_path` for files, `Recorder` or
  `lambda f: None` as the sink, `NullDisplay` when a `Display` is needed,
  the `pico` fixture only when the serial protocol itself is under test.
- When a test fails, first decide whether the test misread the HTML
  (most failures in the first port were the test's expectation, not the
  code), then fix whichever is wrong. Never loosen an assertion to pass.
- Never commit with the suite red. Regenerated art and the tests that
  pin it go in the same commit.

### Step 10 — Verify

Output: a verification section in the final report with the commands
and their results.

```bash
.venv/bin/pytest -q tests/test_microcraft_*.py
.venv/bin/pytest -q
.venv/bin/python - <<'EOF'
import random
from pi_menu.capture import to_image
from pi_menu.microcraft.session import Session, SELECT
frames = []
s = Session(frames.append, seed=12345, rng=random.Random(1), wall_clock=lambda: 1_700_000_000)
s.cursor = [8, 6]; s.press(SELECT)
for _ in range(100): s.tick()
to_image(frames[-1]).save("/tmp/microcraft-world.png")
EOF
```

Save and look at one frame per screen (menu, world, inventory, bench,
table, furnace, any new screen) at scale 24 and compare each against the
HTML's layout by eye. Reach a screen the way the session tests do: set
`session.screen = Screen.X` directly, put stacks into the slots with
`Stack(kind, count)`, and call `session.framebuffer()`; no need to play
to it. On the Mac this is the only way to see the game; `--backend term`
needs Tk. Time one world tick and one fluid tick with `timeit` and record
them against the budget in REFERENCE.md §6; a tick over 12 ms on the Mac
is over budget on a Pi 4.

### Step 11 — Review pass

Output: fixes committed, or a written "nothing found".

Re-read every changed module once with these questions: does any table
entry lack an HTML line to point at; does any `round()` stand where the
HTML has `Math.round`; does any state exist that nothing reads
(`World.spiders`, `World.pebbles` at the last port); is any branch
unreachable; does any screen's frame paint over a region its hit test
owns; does every per-frame HTML call run every tick. Grep the HTML's
new function list once more against the package; every name is either
ported or in the deferred list.

### Step 12 — Docs, registration, deployment

Docs, every port:

- The README's MicroCraft section: keys, screens, and the colour
  paragraph. At commit `9d0880f` that paragraph still describes the
  reverted LED recolour; correct it to "the HTML's art, drawn as is".
- The `HELP` string in `app.py`: every key `HELD_KEYSYMS` and
  `TAP_KEYSYMS` bind (at `9d0880f` it omits `I`). Compare the two maps to
  the string, not memory.
- The plan file's checkboxes ticked and timings recorded.

Registration, only when the app is new:

- `pyproject.toml` `[project.scripts]`, `src/pi_menu/apps.json`,
  `install.sh` `COMMANDS` and `DESKTOP_FILES` plus a `write_desktop_entry`
  call, `README.md` program table and section,
  `tests/test_app_entrypoints.py` `MODULES` list,
  `tests/test_install_script.py` desktop-file assertions.
- An installed Pi keeps `~/.config/pi-menu/apps.json`; the loader merges
  packaged apps the user file lacks (fixed in `f0d77c3`). Mention in the
  report that a re-install is needed for the desktop entry.
- Hardware: nothing in these sessions has run on the panel. Ask the user
  for `pi-menu-doctor` output rather than guessing at the Pimoroni API;
  never write Stellar Unicorn firmware calls from memory.

### Step 13 — Commit and report

- One commit per ledger row, message `feat(microcraft): <what the player
  gets>` or `fix(microcraft): <what was wrong>`, tests included, suite
  green, the attribution trailer the session requires.
- The final message lists: the version ported, the strategy, the ledger
  with each row's status (ported / deviated / deferred), the deviations,
  the verification results verbatim, and anything left for the user to
  decide (LED readability, hardware run).

## Red flags — stop and copy the HTML line instead

| Thought | Reality |
|---|---|
| "I'll make the colours pop on the LEDs" | The art is verbatim. The one time this was done it was reverted as "the assets are wrong". |
| "The furnace screen is roughly fuel, item, output" | Layouts are the HTML's `hitTest*` rectangles. Roughly cost a fix commit and left the bar painted over. |
| "This tile has no break time, I'll give it one" | The HTML's fallback is the rule. Invented entries drift. |
| "I remember the multiplier is 0.16" | Read the line. It is 0.15. |
| "The sheet has the same size, no need to re-extract" | Same size, different base64 length. Always regenerate. |
| "I'll fix the tests after regenerating" | Same commit, or the suite is red in history. |
| "The delta is small, skip the ledger" | The furnace delta was 49 functions. Grep does not lie; instinct does. |
| "Ship the state now, wire the update later" | Dead state (`World.spiders`) was found by a reviewer, not by tests. Every state has a reader in the same commit. |
| "The Mac can't run Tk, so I can't verify" | Everything below `app.py` is headless. Dump frames to PNG and look. |
| "No tests, it's UI" | Layout-versus-hit-test and transition tests are cheap and caught nothing only because they did not exist. |
| "The chest needs its own inventory design" | Read where the HTML keeps it and how it keys it; the state goes there. Design questions are answered by the HTML line, not by architecture. |
| "The skill's recipe doesn't cover this feature" | Find the HTML function that owns it, its state, its `loop` call and its `draw` position; those four facts are the recipe. Add the category to REFERENCE.md §4 in the same PR. |

## Definition of done

1. The tracked HTML at the root is the version ported, and the plan file
   names it.
2. Every function in the HTML's new-function list is ported or in the
   plan's deferred list with a reason.
3. `palette` sheets are the extracted sheets, untouched.
4. Every table in `tiles.py` matches the HTML cell for cell and a test
   pins it.
5. Every screen's drawn layout matches its hit test by test.
6. `pytest -q` is green at every commit.
7. One PNG per screen was rendered from a seeded session and looked at.
8. Tick timing is inside the budget.
9. README and `HELP` name every key and screen.
10. The final report lists deviations and open items.
