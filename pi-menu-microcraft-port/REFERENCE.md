# Reference: the HTML, the framework, the package

Companion to [SKILL.md](SKILL.md). Everything here was verified against
the pi-menu repo at commit `9d0880f` (2026-09-13; package of 17 modules,
4,763 lines, 249 tests) and the 5,420-line `MicroCraft — 16×16.html`
committed in `a90ede6`. Line numbers are for that HTML; grep by symbol
when the file has moved on.

## 1. Anatomy of the HTML

```
1-179     <head>: CSS
180-266   <body>: <canvas id="game" width="16" height="16">, HUD spans #hp #selName #layerName,
          touch buttons (#btnLeft ... .hotbtn[data-slot])
267-268   <script> (() => {            one IIFE; top-level declarations at 2-space indent
269-5416  the game
5417-5420 })(); </script></body></html>
```

Top-level `const`/`let`/`function` sit at two-space indent; a handful of
constants are declared inside functions at deeper indent
(`SPIDER_BG_WEB_CHANCE` inside `genLayerChunk`), and some lines declare
two constants (`const WORLD_SPAWN_X = player.x, WORLD_SPAWN_Y = player.y`).
So grep constants at any indent and read the hits:

```bash
grep -nE '^\s*(const|let|var) ' "MicroCraft — 16×16.html"        # every constant and state variable
grep -nE '^\s*function \w+' "MicroCraft — 16×16.html"             # every function (about 200 lines, 193 unique names in this version)
grep -nE "^\s*\w+\.src = 'data:image/png;base64," "MicroCraft — 16×16.html"   # every sheet
```

### 1.1 Regions of the file, in order

| Region | Symbols | Python home |
|---|---|---|
| screen constants | `VIEW = 16`, `BLOCK = 2`, `COLS`, `ROWS` | `player.py` (`BLOCK`, `COLS`, `ROWS`), `display.protocol.WIDTH` |
| pixel font | `FONT_3X5`, `GLYPH_*`, `pixelTextWidth`, `drawPixelText` | `render.py` |
| world, day, moon, sky | `WORLD_H`, `WORLD_RADIUS`, `wrapX`, `localDayFrac`, `moonPhaseFrac`, `skyColorsAt`, `positionOnArc`, `drawMoonDisc`, `drawEclipse`, `drawSkyAndCelestials` | `noise.py` (`wrap_x`), `sky.py` |
| tile ids and tables | `const SKY = 0, ...`, `SHEET_POS`, `FLUID_SHEET_POS`, `FLOW_TILES`, `MIRRORED_TILES`, item ids, `ITEM_SHEET_POS`, `ITEM_NAMES`, `ITEMS`, `TOOL_TYPES`, `BUCKET_TYPES`, `ARMOR_TYPES`, `SINGLE_STACK_TYPES`, `ARMOR_TYPE_SLOT`, `NAMES`, `FLUIDS`, `FLUID_META`, `flowTileFor` | `tiles.py` |
| sheets | `sheet`, `itemSheet`, `fluidSheet`, `fireSheet`, `breakSheet`, `spiderSheet`, `uiSheet`, `craftBtnImg`, `furnaceProgressImg`, `furnaceOxygenBtnImg`, each with an `onload` | `sprites.py` (generated), `palette.py` |
| noise and terrain | `hash2`, `hash1`, `noise1D`, `noise2D`, `terrainDetailAt`, `mountainFieldAt`, `continentMaskAt`, `oceanFactorAt`, `oceanFloorRawAt`, `spiderZoneAt`, `spiderNestTopAt`, `frontHeightAt`, `backHeightAt`, `isWaterColumn`, `surfaceRefAt`, `treeInCell` | `noise.py`, `terrain.Generator` |
| chunks | `genLayerChunk` (nested `bedTileAt`, `caveValueAt`, `nestValueAt`), `ensureChunk`, `blockAtLayer`, `setBlockAtLayer`, `blockAt`, `solid`, `solidAt`, `fluidAt` | `terrain.Generator.generate_chunk`, `terrain.World` |
| block sims | `simulateFluidsForLayer`, `simulateFluids`, `simulateFire`, `simulateGrass`, `drawFireOverlay`, `igniteWithStick`, `findSpawnX` | `sim.py`, `render._fire_overlay`, `terrain.Generator.find_spawn_x` |
| player damage | `lavaAt`, `waterAt`, `damagePlayer`, `MAX_HP`, `SAFE_FALL_BLOCKS`, `LAVA_DAMAGE_INTERVAL_MS`, `OXYGEN_*`, `DROWN_*`, `DAMAGE_FLASH_DURATION_MS` | `player.py` (not yet ported, §8) |
| clouds, weather, lightning, waves, rain | `rollCloudGap` ... `stormCoverAt`, `buildBoltPoints` ... `drawLightningBolts`, `isOpenWaterSurface` ... `drawWaterSurfaceWaves`, `spawnRain`, `updateRain`, `drawCloudList`, `drawWeatherParticles`, `drawRain` | `weather.py` |
| input | `rowSpan`, `colSpan`, `toggleActiveLayer`, `moveCursor`, `dropHeldItem`, `bindHold`, `bindRepeat`, `bindTap`, the keydown handlers | `player.py` (spans), `session.py`, `app.py` |
| inventory data, furnace sim | `stackMaxFor`, `FUEL_UNITS`, `SMELT_RECIPES`, `updateFurnace`, `pressOxygenButton`, the `furnace` state object | `tiles.stack_max_for`, `furnace.py` |
| hotbar and item strip | `selectSlot`, `updateSelName`, `currentSelectedStackForStrip`, `hoveredSlotStack`, `updateItemStrip`, `drawItemStrip` | `inventory.py`, `render.ItemStrip`, `session.py` |
| inventory ops, drops | `findStackWithRoom`, `findEmptySlot`, `pickupBlock`, `addItemsToInventory`, `pebbleColorFor`, `averageColorFor`, `spawnItemDrop`, `updateItemDrops` | `inventory.py`, `player.Drops`, `palette.AVERAGE_COLOUR` |
| spiders | `findSurfaceRow`, `groundRowAt`, `makeSpiderLegs`, `spawnSpider`, `updateSpiders`, `updateWalkingSpider`, `updateFallingSpider`, `updateClimbingSpider`, `drawSpiders`, leg helpers, `SPIDER_*`, `LEG_*` | a new `mobs.py` (not yet ported, §8) |
| screens | `let menuOpen/invOpen/craftOpen/tableCraftOpen/furnaceOpen`, `open*UI`, `close*UI`, `hitTest*`, `handle*Click`, `draw*UI`, `getSlot`, `setSlot`, `splitStack`, `handleSlotClick` | `session.Screen`, `inventory.Inventory.hit_*`, `render.draw_*` |
| recipes | `matchShapedRecipe`, `getCraftRecipeOutput`, `matchesPattern9`, `STONE_TOOL_PATTERNS`, `metalToolRecipes`, `METAL_TOOL_PATTERNS`, `metalArmorRecipes`, `ARMOR_SHAPE_PATTERNS`, `METAL_ARMOR_PATTERNS`, `getTableCraftRecipeOutput`, `handleOutputSlotClick`, `handleTableOutputSlotClick` | `inventory.py` |
| world interaction | `cursorWorldPos`, `placeAtCursor`, `breakTimeFor`, `breakTimeForHeld`, `breakDropTypeFor`, `canDropWithHeld`, `resetBreaking`, `updateBreaking`, `drawBreakOverlay`, `handleInteract`, `BREAK_TIME_MS`, `AXE_*`, `PICKAXE_*`, `BREAK_DROP_TYPE`, `PICKAXE_TIER`, `DROP_REQUIRES_PICKAXE_TIER`, `TUNGSTEN_ORE_PICKAXES` | `tiles.py` (tables), `player.Breaker`, `player.place_at`, `session.interact` |
| physics and render | `update`, `drawTile`, `draw`, `drawHpRow`, `drawOxygenRow`, `drawCursor`, `GRAV`, `MOVE`, `JUMP` | `player.Player.step`, `render.draw_world`, `render.draw_cursor` |
| menu and demo | `MENU_ROWS`, `BTN_PIXELS`, `drawMenu`, `pickDemoShot`, `demoCamYAt`, `updateDemoCam`, `pointInButton` | `render.py`, `demo.py` |
| main loop | `loop` | `session.tick`, `session.framebuffer` |

### 1.2 Ids

Block ids `< 100`, item ids `>= 100`, both declared as one comma-continued
`const`. New blocks are appended after the highest block id (27..33 so far,
fluid flow tiles 13..26 sit in between); new items after the highest item
id (131). Items that reuse art get duplicate sheet coordinates (armor
uses its ingot's cell).

### 1.3 Sheets

Each sheet is:

```js
  const NAME = new Image();
  let NAMEReady = false;
  NAME.onload = () => { NAMEReady = true; /* sometimes more */ };
  NAME.src = 'data:image/png;base64,...';
```

Read the `onload`: it may compute `AVG_COLOR`, sample `UI_BG_COLOR`, or
bake black to transparent into a canvas (`furnaceProgressImg`). That
baking is the only reason a sheet gets `BLACK_IS_TRANSPARENT` in the
extraction tool.

| JS | Python | size (w×h) | note |
|---|---|---|---|
| `sheet` | `BLOCK_SHEET` | 16×16 | 2×2 tiles; rows 0-2 used, per the comment above the ids |
| `itemSheet` | `ITEM_SHEET` | 16×16 | black is opaque; `AVG_COLOR` skips it |
| `fluidSheet` | `FLUID_SHEET` | 8×4 | row 0 lava, row 1 water; left flows are mirrored right art |
| `fireSheet` | `FIRE_SHEET` | 8×2 | 4 frames, `FIRE_FRAME_MS = 150` |
| `breakSheet` | `BREAK_SHEET` | 8×2 | 4 crack stages |
| `spiderSheet` | `SPIDER_SHEET` | 2×2 | body only; legs are procedural lines |
| `uiSheet` | `UI_SHEET` | 16×16 | `UI_EMPTY_X = 0`, `UI_EXIT_X = 2`, `UI_BG_X = 4` on row 0 |
| `craftBtnImg` | `CRAFT_BUTTON` | 2×2 | |
| `furnaceProgressImg` | `FURNACE_PROGRESS_SHEET` | 4×8 | four 4×2 stages stacked; black baked transparent |
| `furnaceOxygenBtnImg` | `FURNACE_OXYGEN_BUTTON` | 2×2 | flipped every `OXYGEN_BTN_FLIP_MS = 400` |

Non-PNG art: `FONT_3X5`, `BTN_PIXELS` (8×3 RGB triples, `null` clear),
`MENU_ROWS` (16 strings of `g|p|b`). These are copied as literals.

### 1.4 Screens and the loop

No mode enum: five booleans tested in a fixed order, `menuOpen`, `invOpen`,
`craftOpen`, `tableCraftOpen`, `furnaceOpen`. Each `openXxxUI` clears the
others and calls `resetBreaking()`; each `closeXxxUI` returns grid
contents via `clearCraftSlotsToInventory` / `returnItemsToInventory`,
dropping what does not fit at the player's feet.

`loop(ts)`, per frame:

```
updateSelName(); updateItemStrip(); updateFurnace(frameDt);        // always
if (menuOpen)          { sims; updateDemoCam(); draw(demoCam); drawMenu(); }
else if (invOpen)        drawInventory();
else if (craftOpen)      drawCraftingUI();
else if (tableCraftOpen) drawTableCraftingUI();
else if (furnaceOpen)    drawFurnaceUI();
else                   { update(); updateBreaking(frameDt); updateItemDrops(); updateSpiders(frameDt); sims; draw(); }
drawItemStrip(); drawCursor(); requestAnimationFrame(loop);
```

`sims` = item drops, fluids+fire every `FLUID_TICK_MS = 220`, grass every
`GRASS_TICK_MS = 500`, cloud motion, `weatherTick` every
`CLOUD_COVERAGE_TICK_MS = 250`, `spawnRain` every `RAIN_SPAWN_MS = 160`,
`updateRain`, `updateLightning`.

`draw(cam)` order: sky and celestials → overcast wash then storm wash (if
below the clouds) → background layer with fire overlay, darkened
`rgba(0,0,0,0.5)`, pebble pixels on SKY cells → front layer → water
surface waves → clouds → player `#ffe75e` 2×2 (not in demo) → rain →
lightning → break overlay → item drops → spiders → hotbar → hp row (row
0) → oxygen row (row 1, when underwater or refilling) → screen flash
`rgba(235,240,255, f*0.85)` → damage wash `rgba(255,0,0,0.5)`. Then the
loop adds the item strip and the cursor (`globalCompositeOperation =
'difference'`).

### 1.5 Keys

Handlers set `keys[k]` and dispatch: arrows → `moveCursor`; `1`-`8` →
`selectSlot`; `enter` → `handleInteract()`; `l` → `toggleActiveLayer()`;
`q` three taps in `Q_DROP_WINDOW_MS = 600` → `dropHeldItem()`; `e` →
`toggleInventory()`; `escape` closes whichever screen is open. Polled
every frame from `keys{}`: `a`, `d`, space (jump), `backspace`
(`updateBreaking`), `i` (`updateItemStrip`). Polled keys are held keys in
the port; handler keys are tapped keys. Touch buttons bind to the same
names through `bindHold(el, key)`, `bindRepeat`, `bindTap`.

| HTML | Session key | Tk keysyms |
|---|---|---|
| `a` / `d` | `LEFT` / `RIGHT` (held) | `a A` / `d D` |
| `w`, space | `JUMP_KEY` (held) | `w W space` |
| backspace | `BREAK` (held) | `BackSpace` |
| `i` | `SHOW_STRIP` (held) | `i I` |
| arrows | `CURSOR_*` (tap, auto-repeat welcome) | `Left Right Up Down` |
| enter | `SELECT` | `Return KP_Enter` |
| `1`..`8` | `select_slot(n-1)` | `1`..`8` |
| `e` | `INVENTORY` | `e E` |
| `l` | `LAYER` | `l L` |
| `q` ×3 | `DROP` | `q Q` |
| escape | `BACK_KEY` | `Escape` |
| (none) | capture PNG | `c C` (framework convention) |

### 1.6 Recipe formats

1. 2×2 bench, hand-coded in `matchShapedRecipe` → `{ type, count, consume: [n,n,n,n] }`; unshaped log → planks in `getCraftRecipeOutput`.
2. 3×3 patterns: nine-character row-major arrays, `'C'` material, `'S'` stick, `'.'` empty; `matchesPattern9(slots9, pattern, materialType)`. `STONE_TOOL_PATTERNS`, `METAL_TOOL_PATTERNS` (from `metalToolRecipes(material, pickaxe, sword, axe)`), `METAL_ARMOR_PATTERNS` (from `ARMOR_SHAPE_PATTERNS` × `metalArmorRecipes`). `getTableCraftRecipeOutput` priority: stone tools → metal tools → metal armor → unshaped log → any 2×2 window of the bench recipes with the rest empty.
3. Smelting: `SMELT_RECIPES[INPUT] = { heat, timeMs, outputType }`, fuel from `FUEL_UNITS`.

### 1.7 Slot-click rules (`handleSlotClick`)

1. First press on a non-empty slot selects it.
2. Second press on the same slot deselects.
3. Two presses within `DOUBLE_TAP_MS` arm a split; the next press on an empty slot moves half.
4. Press on a different slot: merge if same kind (overflow stays), else swap.
5. Output slots: if empty, craft and consume, place the result; the next press picks it up.
6. Armor slots accept only the piece whose `ARMOR_TYPE_SLOT` is that row; the gate must apply in both directions (the last port gated only the destination, so a helmet in hand could swap dirt into the armor row).

### 1.8 Physics (per 60 Hz frame in `update`)

`vx = ±MOVE` while held, else `vx *= 0.5`; jump `vy = -JUMP` on ground;
swim stroke `vy -= GRAV * 2.2` in fluid; `vy += GRAV * 0.35` in fluid
else `GRAV`; clamp fall to `0.4` (air) or `0.08` (fluid), swim-up to
`-0.12`; move x then y against `solidAt` using `colSpan`/`rowSpan`;
`y > WORLD_H - 2` teleports to the antipode; snap to the half-block
pixel grid after 1 s idle. Fall damage, lava damage and oxygen live in
the same function in the newest HTML (§8).

### 1.9 Fluids, fire, grass

Fluids: sources permanent; a cell fed from above becomes DOWN; otherwise
level = lowest neighbour + 1, tapering to 3 on solid ground and 1 in air;
unfed tiles recede; sky between two sources becomes a source. Fire:
`FLAMMABLE` touching lava ignites, burns `BURN_DURATION_TICKS = 30`,
bakes adjacent CLAY to BRICK each tick, water extinguishes and the block
survives. Grass: covered grass dies after `GRASS_DECAY_TICKS = 24`;
sunlit dirt below `GRASS_LINE_Y` bordering grass greens with
`GRASS_SPREAD_CHANCE`; additions are collected and applied after the scan.

## 2. The framework contract

| Piece | Where | Signature or fact |
|---|---|---|
| frame | `display/protocol.py` | `WIDTH = HEIGHT = 16`, `FRAME_BYTES = 768`, row-major RGB, x fastest, `pixel_offset(x, y) = (y * 16 + x) * 3`; `Display.set_frame` raises on any other length |
| backends | `display/__init__.py` | `add_display_args(parser)` adds `--backend {auto,serial,term,null}`, `--port`, `--brightness` (0.5); `open_display(backend="auto", port=None, brightness=0.5) -> Display` |
| pump | `display/pump.py` | `FramePump(display)`; `.submit(framebuffer: bytes)` keeps the newest frame; `.error`; `.set_brightness(f)`; `.close()`. `pump.submit` is the session's sink. Never touch the display from the Tk thread. |
| held keys | `platformer/keys.py` | `HeldKeys().press(key) -> bool` (fresh press only), `.release(key)` deferred, `.settle() -> list` once a tick. Filters X11 auto-repeat. |
| capture | `capture.py` | `to_image(framebuffer, scale=24)` (PIL), `save_frame(framebuffer, prefix=...) -> Path` into `~/Pictures` |
| tick | `session.py` | `TICK_HZ = 20`, `TICK_MS = 50.0`; `player.STEP_MS = 1000/60` |
| session | `session.py` | `Session(sink, seed=None, rng=None, wall_clock=time.time)`; `press(key)`, `release(key)`, `select_slot(i)`, `tick(dt_ms=TICK_MS)`, `framebuffer() -> bytes`, `status_text() -> str`; `now_ms` is the only game clock; `rng` the only randomness; `wall_clock` only for the real moon |
| app | `app.py` | `MicroCraftApp(root, pump, seed=None)`; `HELD_KEYSYMS`, `TAP_KEYSYMS`, `HELP`; `main(argv) -> int` does argparse → `open_display` → `FramePump` → Tk mainloop → `pump.close()` |
| registration | `pyproject.toml`, `apps.json`, `install.sh`, `README.md`, `tests/test_app_entrypoints.py`, `tests/test_install_script.py` | see §10 |

Nothing under `microcraft/` except `app.py` imports Tk or a display.
Keep it that way; that is what makes the port testable on a Mac with no
`_tkinter`.

## 3. Module map and dependency order

Lowest first; implement and test in this order.

| Module | Holds | Public names to keep stable |
|---|---|---|
| `noise.py` | `MASK`, `WORLD_RADIUS`, `WORLD_PERIOD`, `wrap_x` (floats too), `round_half_up` (JS `Math.round`), `hash2`, `hash1`, `noise1d`, `noise2d` | all |
| `tiles.py` | every id and table of §1.1 "tile ids and tables" plus break tables, `FluidMeta`, `flow_tile_for`, `is_lava`, `is_water`, `solid`, `break_time_ms(kind, held)` | all |
| `sprites.py` | generated sheets: tuple of rows of `(r,g,b)` or `None` | sheet names |
| `palette.py` | `X_SHEET = sprites.X_SHEET` for every sheet, `UI_BG_COLOUR`, flat fill constants, `tile_art(kind) -> (sheet, sx, sy, mirrored)`, `AVERAGE_COLOUR` | all; `lift()` exists and is unused |
| `canvas.py` | `Canvas` (float RGB, 768 values): `fill`, `vertical_gradient`, `set`, `rect`, `invert`, `tile` (2×2 only), `radial`, `line`, `get`, `to_bytes`; `lerp_colour`, `hex_colour` | all |
| `terrain.py` | constants (`WORLD_H = 1250`, `SURFACE_BASE = 250`, `GRASS_LINE_Y = 228`, `TREE_LINE_Y = 238`, `SEA_LEVEL = 258`, `CHUNK_W = 32`, `FRONT = 0`, `BACK = 1`), `Generator` (heights, `find_spawn_x`, `generate_chunk` pipeline), `World` (`get`, `set`, `column`, `solid_at`, `fluid_at`, `burning`, `grass_covered`, `pebbles`, `spiders`) | all |
| `sim.py` | `BLOCK_SIM_RADIUS = 32`, `_Box`, `simulate_fluids`, `simulate_fire`, `simulate_grass`, `StickLighter` | all |
| `inventory.py` | group name strings, `Stack`, `Recipe`, `STARTER_*`, `STONE_TOOL_PATTERNS`, `Inventory` (slots, `slot_click`, recipes, `*_output_click`, `close_*`, static `hit_*`) | all |
| `furnace.py` | `FUEL_UNITS`, `SMELT_RECIPES`, heat constants, `Furnace.update(dt_ms)`, `press_oxygen`, fractions, `empty_back_to` | all |
| `player.py` | `BLOCK`, `COLS`, `ROWS`, physics constants, `STEP_MS`, key names, `row_span`, `col_span`, `camera`, `Player.step`, `ItemDrop`, `Drops`, `Breaker`, `place_at` | all |
| `sky.py` | `DayClock`, `moon_phase_frac`, `sky_colours_at`, `position_on_arc`, `make_stars`, `draw_sky`, eclipse | all |
| `weather.py` | `Weather` (clouds, cover, rain, lightning, waves, `fluid_or_wave_at`, `draw_*`), `make_cloud(x, rng, opts)` | all |
| `demo.py` | `SHOTS`, `ANCHORS`, `Demo(gen, spawn_x).update(dt_ms)`, `cam_x`, `cam_y`, `time_frac`, `moon_phase` | all |
| `render.py` | `draw_world(canvas, world, weather, cam_x, cam_y, *, sky_frac, moon_phase, stars, now_ms, ref_y, player=None, breaker=None, inventory=None, drops=None, active_layer=FRONT, item_strip=None)`, `draw_menu`, `point_in_button`, `draw_inventory`, `draw_bench`, `draw_table`, `draw_furnace`, `draw_cursor`, `ItemStrip`, `FONT_3X5` | all |
| `session.py` | keys, periods, `Screen`, `Session` | all |
| `app.py` | Tk shell | `main` |

## 4. Extension-point recipes by feature category

Each recipe lists every place a feature of that category touches. A
feature is done when every line applies or is consciously not needed.

### 4.1 New block or item

1. `tiles.py`: id constant with the HTML's number; `SHEET_POS` or `ITEM_SHEET_POS`; `NAMES` (only if the HTML names it); membership in `TOOL_TYPES` / `BUCKET_TYPES` / `ARMOR_TYPES` / `SINGLE_STACK_TYPES` / `ARMOR_SLOT` / `FLAMMABLE` / `AXE_BLOCKS` / `PICKAXE_BLOCKS` / `BREAK_TIME_MS` / `BREAK_DROP_TYPE` / tier tables exactly as the HTML has it.
2. Art: regenerate `sprites.py`; a new sheet → `SHEETS` in the tool, alias in `palette.py`, sizes in `test_microcraft_tiles.py`, identity in `test_microcraft_palette.py`.
3. `palette.tile_art` needs a branch only for a new sheet type.
4. Terrain placement: a pass in `Generator.generate_chunk` or a new `_xxx` method, pure in `(x, y, seed)` via `self.hash2` / `noise2d`; anything the pass computes must be stored on `World` and read by render or sim in the same commit.
5. Starter kit if the HTML's `hotbar`/`inv` initialisers changed.
6. Tests: `test_microcraft_tiles.py` (names, sheet bounds, tables), `test_microcraft_terrain.py` (placement rule with the `SEEDS` parametrisation and `pytest.skip` when a seed lacks the feature).

### 4.2 New recipe

- Bench: `Inventory.match_shaped` / `bench_recipe`.
- Table: pattern lists mirroring the HTML's (`STONE_TOOL_PATTERNS`, metal tools, armor). `Inventory._matches9(slots9, pattern)` today has no material argument; extend it to `(slots9, pattern, material)` as the HTML's `matchesPattern9(slots9, pattern, materialType)` when metal recipes are ported. Keep `table_recipe`'s priority chain identical to `getTableCraftRecipeOutput`.
- Smelting: `furnace.SMELT_RECIPES`, `FUEL_UNITS`.
- `Recipe(kind, count, consume)` with `consume` parallel to the grid; `_output_click` consumes generically.
- Tests: one per recipe, both axe hands for shaped tools, shifted 2×2 windows on the table, output crafts once and consumes then.

### 4.3 New screen

1. `session.Screen` member.
2. `Inventory.hit_<screen>(px, py) -> (region, index)` transcribed from `hitTestXxxUI`; region strings are the HTML's.
3. `render.draw_<screen>(canvas, inventory, ..., now_ms)` transcribed from `drawXxxUI` in call order; `_crafting_screen` and `_backpack_and_hotbar(canvas, inventory, top, blink)` are the templates. Check that the backpack/hotbar rows do not cover a region the hit test owns.
4. `Session.interact` branch (from `handleXxxUIClick`), `Session.back` branch (from the `escape` case), `Session.framebuffer` branch, `Session._hovered_slot`, the hard-coded tuple of slot groups in `Session.framebuffer`'s item-strip branch (the HTML's `STRIP_HOVER_REGIONS`; a new group missing there means `I` shows nothing on the new screen), `status_text`, and the `tick` decision (does the world run behind it: only MENU and WORLD do in the HTML).
5. Opening from a placed block: the CRAFTING_TABLE / FURNACE pattern in `interact` (skipped while holding a STICK).
6. A screen that edits slots owned by something other than the bag (a furnace, a chest at `(layer, x, y)`) keeps one source of truth: give `Inventory` a way to bind a group name to an external slot list (`inventory.bind(GROUP, slots)` on open, `unbind` on close, `_slots(group)` consulting the binding), so `slot_click`, `get`, `set` and the renderer all read the object's own list. The furnace today copies slots in and out by hand (`_sync_furnace_slots` / `_push_furnace_slots`); replace that with a binding when the furnace is next touched, and do not copy it for a new screen. Per-block contents live on `World` in a dict keyed `(layer, x, y)`, mirroring the HTML's `"layer,x,y"` map key; read the HTML's `closeXxxUI` and `updateBreaking` to learn whether contents stay in the block, return to the bag, or drop when the block breaks.
7. Any per-frame update the HTML runs regardless of screen goes in `Session.tick` before the branch.
8. New keys: a held key is a constant in `session.HELD_KEYS` plus `app.HELD_KEYSYMS`; a tapped key is a constant in `session.py`, an `elif` branch in `Session.press`, and `app.TAP_KEYSYMS`; then `HELP` and README.
9. Tests: layout-versus-hit-test over all 256 pixels, every region's click, every transition, leftovers on close, a frame of 768 bytes.

### 4.4 New sim (fluid-like)

`simulate_<x>(world, cx, cy[, rng])` in `sim.py` using `_Box` and
`columns_touching`; period constant and accumulator loop in
`Session._simulate`; deviation note if the HTML scanned whole columns;
tests per rule.

### 4.5 New mob

A `mobs.py` (or one module per mob kind) with a class per mob holding the
HTML's state fields verbatim, and a container class (`Spiders`, `Bats`)
holding the HTML's collection in the HTML's shape: `const spiders = []`
is a list, so the container wraps a list, not a dict (the empty
`World.spiders: dict` at `9d0880f` is a leftover to delete or replace).
Spawn where the HTML spawns: grep the `spawnXxx(` call sites. A call
inside `genLayerChunk` is a chunk-generation rule (goes in the terrain
pass; `Math.random()` there becomes the injected rng and is a recorded
deviation); a call inside `updateXxx` is a per-tick rule (goes in the
container's `update`). `update(world, player, rng, dt_ms)` is called from
`Session.tick` at the HTML's position in the world branch (after
`updateItemDrops`), and from the menu branch only if the HTML's menu
branch calls it; bound the work to `BLOCK_SIM_RADIUS`. `draw(canvas,
cam_x, cam_y, now_ms)` is called from `render.draw_world` at the HTML's
draw position (after drops, before hotbar) through a new keyword
argument. Procedural parts (spider legs via Bresenham `drawSpiderLegLine`)
use `canvas.line` or a `canvas.set` loop. A mob that hurts the player
calls `Player.damage(amount)`, which means the §4.6 row comes first in
the ledger. Tests: spawns where and when the HTML says (force chance with
a stub rng), does not spawn elsewhere, each mode transition (walk → fall
→ climb), draws inside the frame at the right layer, is not stepped
outside the radius, stands still while a screen is open.

### 4.6 Player stat (hp, oxygen)

None of this exists at `9d0880f` (`Player.hp = 10` is display-only);
create it. Fields on `Player` (`hp`, `max_hp`, `oxygen_ms`, `fall_start_y`,
`was_on_ground`, spawn point captured at construction as the HTML's
`WORLD_SPAWN_X/Y`); per-frame accumulation in `Player.step` taking the
substep's `dt_ms`; `Player.damage(amount)` translating `damagePlayer`
(respawn at the spawn point with full hp on 0); flash timers on the
session; HUD rows drawn in `render.draw_world` at the HTML's pixel rows
(hp row 0, oxygen row 1); `status_text` shows the number. Tests: a fall of
N blocks costs the HTML's amount, lava ticks every interval, oxygen drains
and refills at the HTML's rates, death respawns with full hp.

### 4.9 Full-frame render effect (lighting, tint, wash, flash)

Find the HTML's draw call and its position in `draw()`. A wash is a
`canvas.rect(0, 0, 16, 16, colour, alpha)` at that position. A light or
darkness effect that multiplies pixels (a torch radius, cave darkness) is
a pass over `canvas.px` in `render.py` placed at the HTML's position, with
the falloff formula copied from the HTML; if the HTML composites through
`globalCompositeOperation`, map it to the `Canvas` primitive (`multiply`
→ per-channel product, `difference` → `invert`, `lighter` → additive
clamp) and add the primitive to `canvas.py` with a test. State that
drives it (a torch flag, a flash timer) lives on the session or the
player as the HTML has it.

### 4.10 Player-carried toggle (torch, layer, mode)

A boolean on the session or player as the HTML has it (`let torchOn`),
a tapped key (§4.3 step 8), a `status_text` word, its render effect via
§4.9, and, if the HTML makes it an item, the §4.1 row as well. Tests: the
key flips it, the frame differs with it on, `status_text` names it.

### 4.7 Sky or weather effect

`sky.draw_sky` for celestial things, `Weather.draw_<x>` for things
between the layers and the player, called from `render.draw_world` in
the HTML's order. Randomness from `Weather.rng`.

### 4.8 Loop change

Re-derive `Session.tick` and `Session.framebuffer` from `loop` and
`draw`; a test in `test_microcraft_session.py` asserts each branch's
effect (the furnace advances while its screen is open; sims run on the
menu).

## 5. Translation table

| JS | Python |
|---|---|
| `Math.round(v)` | `noise.round_half_up(v)` |
| `Math.floor(v)` | `math.floor(v)` (never `int()` for negatives) |
| `Math.imul(a, b)`, `x >>> 0` | `(a * b) & MASK`, `x & MASK` as in `noise.hash2` |
| `Math.random()` | `rng.random()` (injected) |
| `performance.now()`, `frameDt` | `Session.now_ms`, the tick's `dt_ms` |
| `Date.now()` | `wall_clock()` (moon only) |
| `ctx.fillStyle = '#rrggbb'; ctx.fillRect(x, y, w, h)` | `canvas.rect(x, y, w, h, COLOUR)` with `COLOUR = hex_colour('#rrggbb')` or a literal triple and the hex in a comment |
| `ctx.fillStyle = 'rgba(r,g,b,a)'` | `canvas.rect(..., (r, g, b), alpha=a)` |
| `ctx.drawImage(sheet, sx, sy, 2, 2, dx, dy, 2, 2)` | `canvas.tile(SHEET, sx, sy, dx, dy, mirrored=...)` |
| `drawImage` of a non-2×2 band | explicit loop over `canvas.set` |
| `globalCompositeOperation = 'difference'` | `canvas.invert(x, y)` |
| gradient fill | `canvas.vertical_gradient` / `canvas.radial` |
| `keys['x']` polled in an update | held key (`HELD_KEYS`) |
| keydown handler action | tapped key |
| `let xxxOpen` | `Screen.XXX` |
| `getSlot('group', i)` | `inventory.get(GROUP, i)`; group constants hold the HTML strings |
| per-frame velocity integration | `steps = max(1, round(dt_ms / STEP_MS))` substeps |
| `setInterval`-style accumulators | `while acc >= PERIOD` loops in `_simulate` |

## 6. Performance budget

Measured on the dev Mac (about 3× a Pi 4); keep the Mac under 12 ms so
the Pi stays under a 50 ms tick:

| Work | Budget (Mac) | Last measured |
|---|---|---|
| world frame (two layers, waves, clouds, rain) | ≤ 6 ms | 1-3 ms |
| fluid + fire tick, 65×65 box | ≤ 4 ms | 0.7-1.5 ms |
| grass tick | ≤ 3 ms | |
| cloud motion near camera | ≤ 2 ms | ~1 ms |
| fresh chunk | ≤ 40 ms | 14 ms |

Techniques already in use: `bytearray` columns read by slice,
`set(column[lo:hi]) & kinds` to skip idle columns, particles integrated
only within `PARTICLE_ACTIVE_RANGE = 40`, sheets as literals,
`_draw_cloud_list` writing `canvas.px` directly.

```bash
.venv/bin/python -m timeit -s "import random; from pi_menu.microcraft.session import Session, SELECT; s=Session(lambda f: None, seed=12345, rng=random.Random(1), wall_clock=lambda: 0); s.cursor=[8,6]; s.press(SELECT)" "s.tick()"
```

## 7. Deliberate deviations already accepted

- Sim boxes bounded to ±32 blocks in y as well as x.
- Cloud particles integrate only within 40 blocks of the camera.
- Fixed 20 Hz tick with three 60 Hz physics substeps.
- Injected clock and rng; `--seed`.
- Esc from the world returns to the opening screen; the world is kept.
- Touch controls dropped; HUD text (`#hp`, `#selName`, `#layerName`) in the Tk status line.
- Cursor drawn by inverting the pixel.
- Menu button art copied by hand from `BTN_PIXELS`.
- No persistence (same as the HTML).

Any new deviation is written in the plan with the reason and, if it is
visible, in the final report.

## 8. Open items at commit 9d0880f (verify with grep before relying on this)

Present in the 5,420-line HTML, absent or wrong in the port:

| Item | HTML symbols | State in Python |
|---|---|---|
| spider mobs | `spawnSpider`, `updateSpiders`, `drawSpiders`, `SPIDER_*`, `LEG_*` | nests, webbing, `SPIDER_SHEET` and an empty `World.spiders` exist; nothing spawns, moves or draws |
| hp, damage, respawn | `MAX_HP = 16`, `damagePlayer`, `SAFE_FALL_BLOCKS`, `LAVA_DAMAGE_INTERVAL_MS`, `damageFlashMs`, `drawHpRow` | `Player.hp = 10`, display only |
| oxygen, drowning | `OXYGEN_MAX_MS = 8000`, `OXYGEN_REFILL_RATE`, `DROWN_DAMAGE_INTERVAL_MS`, `drawOxygenRow` | absent |
| pebbles | `PEBBLE_CHANCE`, `pebbleColorFor`, pebble branch in `updateBreaking` | `_scatter_pebbles` result discarded |
| break drop rules | `BREAK_DROP_TYPE`, `PICKAXE_TIER`, `DROP_REQUIRES_PICKAXE_TIER`, `TUNGSTEN_ORE_PICKAXES`, `canDropWithHeld` | always drops the block's own kind |
| tool tables | `PICKAXE_BLOCKS` includes DIRT, GRASS, SAND, CLAY; tungsten mult 0.15; no WEBBING break time | Python lacks the four, has 0.16, adds `WEBBING: 1200` |
| metal tool and armor recipes | `metalToolRecipes`, `metalArmorRecipes`, `matchMetal*` | only stone tools |
| furnace screen | `hitTestFurnaceUI`: fuel (0,2), item (2,2), progress x4-7 row 2, output (8,2), oxygen (8,4), fuel bar y=4, heat bar y=5 | item at (4,2), oxygen at (12,2); backpack rows paint over the progress bar; 2 of 4 progress stages |
| furnace runs every frame | `updateFurnace` before the branch | only in MENU/WORLD branches |
| item strip on inventory screens | `updateItemStrip`, `hoveredSlotStack`, `keys['i']` | unreachable branch; `I` does nothing |
| armor gate | both directions | destination only |
| moon phase offset | `MOON_PHASE_OFFSET_MS` | absent |
| `--seed` | | seeds terrain only, not `rng` |
| held keys on focus loss | | no `<FocusOut>` clearing |
| `q` ignores auto-repeat | handler checks `e.repeat` | `q` is in `TAP_KEYSYMS`, so holding Q 600 ms drops an item |
| `HELP` text | | omits the `I` key that `HELD_KEYSYMS` binds |
| README colour paragraph | | still describes the reverted LED recolour |
| `World.spiders`, `World.pebbles` | | declared, never filled or read |

Inherited from the HTML and left alone: cloud x unwrapped across the
seam; item drop x unwrapped.

## 9. Test recipes

Fixtures and helpers that exist:

- `tests/test_microcraft_session.py`: `Recorder` sink (`frames`, `last`), `colour_at(frame, x, y)`, `game` fixture, `start(session)`, `put_cursor(session, x, y)`.
- `tests/test_microcraft_render.py`: `scene` fixture (`World(31)`, cleared weather), `draw(world, weather, cam_x, cam_y, **extra) -> Canvas`, `tile_pixels(canvas, bx, by)`, `SKY_ROW = 120`.
- `tests/test_microcraft_sim.py`: `AlwaysRoll(value)` rng stub, `shelf()`, `row()`, `meadow()` builders.
- `tests/test_microcraft_terrain.py`: `SEEDS = (1, 42, 123456789, 2147483646)`.
- `tests/test_microcraft_inventory.py`: `bag` fixture (`Inventory(starter_kit=False)`).
- `tests/conftest.py`: `pico` fixture running the real firmware over a pty (serial protocol tests only).

Layout-versus-hit-test skeleton:

```python
def test_furnace_layout_matches_its_hit_test():
    canvas = Canvas()
    inv = Inventory(starter_kit=False)
    render.draw_furnace(canvas, inv, Furnace(), now_ms=0)
    for y in range(16):
        for x in range(16):
            region, index = Inventory.hit_furnace(x, y)   # regions: "exit", "oxygen", "bg", slot groups
            if region == "exit":
                assert canvas.get(x, y) == UI_SHEET[y % 2][UI_EXIT_X + x % 2]
            elif region in (FURNACE_FUEL, FURNACE_ITEM, FURNACE_OUTPUT, BACKPACK, HOTBAR):
                assert canvas.get(x, y) == SLOT_COLOUR
    # and the pixels the HTML reserves for the progress band (x 4..7, y 2..3)
    # and the bars (y 4 and 5, x 0..7) are not slots in the hit test
    for x in range(4, 8):
        assert Inventory.hit_furnace(x, 2)[0] == "bg"
```

The region strings a hit test returns are the HTML's: today `"exit"`,
`"openCraft"`, `"oxygen"`, `"qty"`, `"bg"` and the slot-group constants.
A new region string comes from the new `hitTestXxxUI`.

Per-frame-regardless-of-screen skeleton:

```python
def test_furnace_advances_while_its_screen_is_open(game):
    session, _ = game
    start(session)
    furnace = session.furnace
    furnace.fuel_slot = Stack(tiles.COAL, 1)
    furnace.item_slot = Stack(tiles.CLAY, 1)
    session.tick()                       # loads the fuel; heat only rises via the button
    for _ in range(10):
        furnace.press_oxygen()           # HEAT_MAX = 10 covers every recipe's heat
    session._open_furnace()
    before = furnace.progress_ms
    for _ in range(40):
        session.tick()
    assert furnace.progress_ms > before  # fails at 9d0880f: _simulate runs only on MENU/WORLD
```

## 10. Registration checklist (new app only)

- [ ] `pyproject.toml` `[project.scripts]`: `pi-<game> = "pi_menu.<game>.app:main"`
- [ ] `src/pi_menu/apps.json`: `id`, `name`, `description`, `command: ["{python}", "-m", "pi_menu.<game>.app"]`, `hold: "on-error"`
- [ ] `install.sh`: `COMMANDS`, `DESKTOP_FILES`, a `write_desktop_entry` call, the usage text
- [ ] `README.md`: program table row and a usage section with the key map
- [ ] `tests/test_app_entrypoints.py`: `MODULES` list and the `--list` test
- [ ] `tests/test_install_script.py`: the desktop file and its `Exec`
- [ ] note in the report: an installed Pi merges new packaged apps into its user `apps.json` (`f0d77c3`), but the desktop entry needs a re-install
