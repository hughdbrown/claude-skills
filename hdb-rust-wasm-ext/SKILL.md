---
name: hdb:rust-wasm-ext
description: Build Chrome extensions in Rust/WASM with thin JS bridges using the wasm_bindgen module pattern
---

# hdb:rust-wasm-ext

Build Chrome extensions with maximum Rust and minimum JavaScript using the `wasm_bindgen` module bridge pattern.

## Usage

```
/hdb:rust-wasm-ext <task description>
```

## Description

Implements Chrome extensions as Rust/WASM crates with thin JavaScript bridge files (~15-25 lines each) that wrap Chrome extension APIs. Instead of writing extension logic in JavaScript, all business logic lives in Rust and is compiled to WASM via `wasm-pack`. The bridge pattern uses `#[wasm_bindgen(module = "/bridge.js")]` to create typed imports from JS into Rust, giving full type safety at the Rust/JS boundary.

A Chrome extension has up to three execution contexts, each requiring its own WASM crate:

| Context | Purpose | Loader | Handler Type |
|---------|---------|--------|-------------|
| **Background** (service worker) | State management, API calls, badge updates | Static ES module import | Async (Promise) |
| **Content script** | DOM interaction, page parsing, UI overlays | Dynamic import via `chrome.runtime.getURL()` | Synchronous |
| **Popup** | User interface | ES module import | N/A (framework handles) |

A fourth crate — **shared types** — holds message enums, payload structs, and API types with no WASM dependencies, enabling `cargo test` on pure Rust logic.

## Instructions

When the user invokes `/hdb:rust-wasm-ext <task description>`:

### Phase 1: Understand the scope

1. **Identify which execution contexts are needed.** Not every extension uses all three. A simple popup-only extension needs one crate; a full extension with content script detection and background processing needs all four (types + 3 WASM crates).

2. **Read existing code.** If the extension already exists as JavaScript, read every JS file to understand:
   - What Chrome APIs are used (these become bridge functions)
   - What messages flow between contexts (these become the `Message` enum)
   - What state is maintained (these become `thread_local!` structs)

3. **Map Chrome APIs to bridge functions.** Each Chrome API call that crosses the WASM boundary needs a JS wrapper. Group by context:
   - Background: `chrome.tabs.sendMessage`, `chrome.action.setBadgeText`, `chrome.storage.*`
   - Content: `chrome.runtime.sendMessage`
   - Popup: `chrome.tabs.query`, `chrome.runtime.sendMessage`

### Phase 2: Scaffold the crates

4. **Create the shared types crate first** (pure Rust, no WASM):

```toml
# crates/my-ext-types/Cargo.toml
[package]
name = "my-ext-types"
edition = "2024"

[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
```

Define the `Message` enum with serde tag-based serialization matching the wire format:

```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum Message {
    #[serde(rename = "ACTIVATE")]
    Activate { tab_id: Option<i32> },
    #[serde(rename = "DEACTIVATE")]
    Deactivate { tab_id: Option<i32> },
    // ... other message types
}
```

5. **Create each WASM crate** with this Cargo.toml template:

```toml
[package]
name = "my-ext-bg"  # or my-ext-content, my-ext
edition = "2024"

[lib]
crate-type = ["cdylib", "rlib"]  # cdylib for WASM, rlib for cargo test

[dependencies]
my-ext-types = { path = "../my-ext-types" }
wasm-bindgen = "0.2"
wasm-bindgen-futures = "0.4"
js-sys = "0.3"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
serde-wasm-bindgen = "0.6"
console_error_panic_hook = "0.1"
log = "0.4"
wasm-logger = "0.2"
web-sys = { version = "0.3", features = ["console"] }
```

Context-specific additions:
- **Background**: `gloo-net = { version = "0.6", features = ["http"] }` for HTTP, `web-sys` features: `["console", "Url"]`
- **Content script**: extensive `web-sys` features for DOM: `["Document", "Element", "HtmlElement", "Node", "NodeList", "Window", "Event", "MouseEvent", "EventTarget", "MutationObserver", "MutationObserverInit", ...]`
- **Popup (Yew)**: `yew = { version = "0.21", features = ["csr"] }`, `web-sys` features: `["HtmlInputElement"]`

6. **Write the bridge JS files.** Place each at the crate root (e.g., `crates/my-ext-bg/bg-bridge.js`):

```javascript
// bg-bridge.js — Chrome API wrappers for background service worker WASM.
// Imported via #[wasm_bindgen(module = "/bg-bridge.js")]

/* global chrome */

export function tabsSendMessage(tabId, msg) {
    return new Promise((resolve, reject) => {
        chrome.tabs.sendMessage(tabId, msg, (resp) => {
            if (chrome.runtime.lastError) {
                reject(new Error(chrome.runtime.lastError.message));
            } else {
                resolve(resp || {});
            }
        });
    });
}

export function setBadgeText(tabId, text) {
    chrome.action.setBadgeText({ text, tabId });
}
```

```javascript
// content-bridge.js — Chrome API wrappers for content script WASM.

/* global chrome */

export function sendRuntimeMessage(msg) {
    return new Promise((resolve, reject) => {
        chrome.runtime.sendMessage(msg, (resp) => {
            if (chrome.runtime.lastError) {
                reject(new Error(chrome.runtime.lastError.message));
            } else {
                resolve(resp || {});
            }
        });
    });
}
```

7. **Write the loader JS files.** Place in the extension directory:

**Background loader** (`extension/background/loader.js`) — static ES module import:

```javascript
import init, { setup, handle_message, on_tab_updated, on_tab_removed }
    from "../pkg-bg/my_ext_bg.js";

await init();
setup();

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    const senderTabId = sender.tab ? sender.tab.id : -1;
    handle_message(message, senderTabId).then(sendResponse);
    return true; // keep channel open for async response
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, _tab) => {
    if (changeInfo.status === "complete") on_tab_updated(tabId);
});

chrome.tabs.onRemoved.addListener((tabId) => on_tab_removed(tabId));
```

**Content script loader** (`extension/content/loader.js`) — dynamic import:

```javascript
(async () => {
    try {
        const src = chrome.runtime.getURL("pkg-content/my_ext_content.js");
        const { default: init, setup, handle_message } = await import(src);
        await init();
        setup();

        chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
            const resp = handle_message(message);
            sendResponse(resp);
            return false; // synchronous response
        });
    } catch (e) {
        console.error("[MyExt Content] Failed to load WASM:", e);
    }
})();
```

**Popup init** (`extension/popup-init.js`) — minimal:

```javascript
import init from './pkg/my_ext.js';
init();
```

### Phase 3: Implement the Rust code

8. **Follow `/hdb:rust-dev` batch-first workflow.** Write all Rust files before compiling. Key exports for each crate:

**Background service worker** (`lib.rs`):

```rust
#[wasm_bindgen(module = "/bg-bridge.js")]
extern "C" {
    #[wasm_bindgen(catch, js_name = "tabsSendMessage")]
    async fn tabs_send_message(tab_id: i32, msg: JsValue) -> Result<JsValue, JsValue>;

    #[wasm_bindgen(js_name = "setBadgeText")]
    fn set_badge_text(tab_id: i32, text: &str);
}

#[wasm_bindgen]
pub fn setup() {
    console_error_panic_hook::set_once();
    wasm_logger::init(wasm_logger::Config::new(log::Level::Info));
}

#[wasm_bindgen]
pub fn handle_message(msg_val: JsValue, sender_tab_id: i32) -> js_sys::Promise {
    wasm_bindgen_futures::future_to_promise(async move {
        let msg: Message = serde_wasm_bindgen::from_value(msg_val)
            .map_err(|e| JsValue::from_str(&e.to_string()))?;
        // ... process message
        let resp = OkResponse { ok: true, error: None };
        serde_wasm_bindgen::to_value(&resp)
            .map_err(|e| JsValue::from_str(&e.to_string()))
    })
}

#[wasm_bindgen]
pub fn on_tab_updated(tab_id: i32) -> js_sys::Promise { /* ... */ }

#[wasm_bindgen]
pub fn on_tab_removed(tab_id: i32) { /* ... */ }
```

**Content script** (`lib.rs`):

```rust
#[wasm_bindgen(module = "/content-bridge.js")]
extern "C" {
    #[wasm_bindgen(catch, js_name = "sendRuntimeMessage")]
    async fn send_runtime_message(msg: JsValue) -> Result<JsValue, JsValue>;
}

#[wasm_bindgen]
pub fn setup() { /* same pattern */ }

// Content script message handlers must be SYNCHRONOUS
#[wasm_bindgen]
pub fn handle_message(msg_val: JsValue) -> JsValue {
    let msg: Message = match serde_wasm_bindgen::from_value(msg_val) {
        Ok(m) => m,
        Err(e) => { /* return error response */ }
    };
    match msg {
        Message::Activate { .. } => { /* spawn_local for async work */ }
        Message::GetStatus { .. } => { /* return status synchronously */ }
        _ => { /* ok response */ }
    }
}

// Async operations use spawn_local, not return Promise
#[wasm_bindgen]
pub fn activate() -> js_sys::Promise {
    wasm_bindgen_futures::future_to_promise(async move {
        // ... DOM interaction, send messages
        Ok(JsValue::UNDEFINED)
    })
}
```

**Popup** (`lib.rs` with Yew):

```rust
#[wasm_bindgen(module = "/popup-bridge.js")]
extern "C" {
    #[wasm_bindgen(catch, js_name = "getCurrentTabId")]
    async fn get_current_tab_id() -> Result<JsValue, JsValue>;

    #[wasm_bindgen(catch, js_name = "sendToBackground")]
    async fn send_to_background(msg: JsValue) -> Result<JsValue, JsValue>;

    #[wasm_bindgen(js_name = "closePopup")]
    fn close_popup();
}

#[wasm_bindgen(start)]
pub fn run_app() {
    yew::Renderer::<App>::new().render();
}
```

### Phase 4: Build and verify

9. **Verify Rust code compiles and passes tests:**

```bash
cargo check --workspace
cargo test --workspace
cargo clippy --workspace -- -D warnings
```

10. **Build WASM with wasm-pack:**

```bash
wasm-pack build crates/my-ext-bg --target web --out-dir ../../extension/pkg-bg
wasm-pack build crates/my-ext-content --target web --out-dir ../../extension/pkg-content
wasm-pack build crates/my-ext --target web --out-dir ../../extension/pkg
```

11. **Copy bridge files to extension directory:**

```bash
cp crates/my-ext-content/content-bridge.js extension/content-bridge.js
cp crates/my-ext-bg/bg-bridge.js extension/bg-bridge.js
cp crates/my-ext/popup-bridge.js extension/popup-bridge.js
```

12. **Load in Chrome** and test: `chrome://extensions` → Developer mode → Load unpacked → select `extension/` directory.

## Manifest V3 Configuration

Complete `manifest.json` template for Rust/WASM extensions:

```json
{
    "manifest_version": 3,
    "name": "My Extension",
    "version": "1.0.0",
    "permissions": ["activeTab", "storage", "tabs"],
    "host_permissions": ["http://localhost:8000/*"],
    "action": {
        "default_popup": "popup.html"
    },
    "content_scripts": [
        {
            "matches": ["<all_urls>"],
            "js": ["content/loader.js"],
            "css": ["content.css"],
            "run_at": "document_idle"
        }
    ],
    "background": {
        "service_worker": "background/loader.js",
        "type": "module"
    },
    "web_accessible_resources": [
        {
            "resources": ["pkg-content/*", "content-bridge.js"],
            "matches": ["<all_urls>"]
        }
    ],
    "content_security_policy": {
        "extension_pages": "script-src 'self' 'wasm-unsafe-eval'; object-src 'self'",
        "sandbox": "sandbox allow-scripts; script-src 'self' 'wasm-unsafe-eval'; object-src 'self'"
    }
}
```

**Critical settings:**
- `"type": "module"` — required for `import` in background service worker
- `web_accessible_resources` — content script WASM must be listed here for `chrome.runtime.getURL()` to work
- `'wasm-unsafe-eval'` — required for WASM instantiation in extension pages
- Background WASM (`pkg-bg/*`) does NOT need `web_accessible_resources` — it's loaded directly by the service worker

## Bridge Pattern Reference

### Path Resolution

Bridge JS files live at the crate root. When `wasm-pack` builds the crate:

```
crates/my-ext-content/
├── content-bridge.js          ← bridge JS at crate root
├── Cargo.toml
└── src/lib.rs                 ← #[wasm_bindgen(module = "/content-bridge.js")]
```

`wasm-pack` outputs to `extension/pkg-content/`. The generated JS import becomes `../content-bridge.js`, which resolves to `extension/content-bridge.js`. This is why bridge files are copied from the crate root to the extension root at build time.

### wasm_bindgen Attributes

| Attribute | Purpose | Example |
|-----------|---------|---------|
| `module = "/file.js"` | Import from bridge JS file | `#[wasm_bindgen(module = "/bg-bridge.js")]` |
| `catch` | Convert JS exceptions to `Result<_, JsValue>` | Required for any Chrome API that can fail |
| `js_name = "camelCase"` | Map Rust snake_case to JS camelCase | `#[wasm_bindgen(js_name = "tabsSendMessage")]` |
| `start` | Run function on WASM init | Popup entry point: `#[wasm_bindgen(start)]` |

### Async vs Sync

- **Async bridge functions** (returns `Promise`): use `async fn` + `catch` attribute
- **Sync bridge functions** (no return or immediate): use regular `fn`
- **Background handlers**: return `js_sys::Promise` via `future_to_promise`
- **Content handlers**: return `JsValue` synchronously. Use `wasm_bindgen_futures::spawn_local` for fire-and-forget async work within a synchronous handler

## State Management Patterns

### Content Script State (single instance)

```rust
use std::cell::RefCell;

thread_local! {
    static STATE: RefCell<ContentState> = RefCell::new(ContentState::default());
}

#[derive(Default)]
struct ContentState {
    active: bool,
    items: Vec<Item>,
    count: u32,
}

// Access pattern
STATE.with(|s| {
    let mut state = s.borrow_mut();
    state.active = true;
});
```

### Background State (per-tab)

```rust
use std::cell::RefCell;
use std::collections::HashMap;

#[derive(Debug, Clone, Default)]
pub struct TabState {
    pub active: bool,
    pub found: u32,
    pub captured: u32,
}

thread_local! {
    static TAB_STATE: RefCell<HashMap<i32, TabState>> = RefCell::new(HashMap::new());
}

pub fn get_state(tab_id: i32) -> TabState {
    TAB_STATE.with(|map| map.borrow_mut().entry(tab_id).or_default().clone())
}

pub fn update_state(tab_id: i32, f: impl FnOnce(&mut TabState)) {
    TAB_STATE.with(|map| {
        let mut map = map.borrow_mut();
        let state = map.entry(tab_id).or_default();
        f(state);
    });
}

pub fn remove_state(tab_id: i32) {
    TAB_STATE.with(|map| map.borrow_mut().remove(&tab_id));
}
```

## Closure Lifetime Patterns

WASM closures passed to JavaScript must be explicitly managed. Two patterns:

### Persistent Callbacks (event listeners, observers)

Use `Closure::wrap` + `.forget()` to leak the closure. It lives as long as the JS callback is registered:

```rust
let callback = Closure::wrap(Box::new(move |event: web_sys::Event| {
    // handle event
}) as Box<dyn FnMut(web_sys::Event)>);

element.add_event_listener_with_callback("click", callback.as_ref().unchecked_ref())?;
callback.forget(); // intentional leak — lives as long as the listener
```

### One-Shot Callbacks (timeouts, single-fire events)

Use `Closure::once` + `.forget()`:

```rust
let callback = Closure::once(move || {
    // runs once, then GC'd
});

window.set_timeout_with_callback_and_timeout_and_arguments_0(
    callback.as_ref().unchecked_ref(),
    3000,
)?;
callback.forget();
```

### Detachable Callbacks (listeners that need cleanup)

Store the `Closure` in `thread_local!` state and drop it on cleanup:

```rust
type EventClosure = Closure<dyn FnMut(web_sys::Event)>;

thread_local! {
    static CLICK_HANDLER: RefCell<Option<EventClosure>> = RefCell::new(None);
}

pub fn attach_click_handler(on_click: impl Fn(String) + 'static) {
    let closure = Closure::wrap(Box::new(move |e: web_sys::Event| {
        on_click("clicked".to_string());
    }) as Box<dyn FnMut(web_sys::Event)>);

    // register with JS...

    CLICK_HANDLER.with(|h| *h.borrow_mut() = Some(closure));
}

pub fn detach_click_handler() {
    CLICK_HANDLER.with(|h| {
        if let Some(closure) = h.borrow_mut().take() {
            // remove from JS, then closure is dropped
            drop(closure);
        }
    });
}
```

## MutationObserver for SPA Support

Content scripts on single-page applications need to re-scan when the DOM changes or the URL changes (pushState):

```rust
pub fn start_observing(
    container_selector: Option<&str>,
    on_change: impl Fn() + 'static,
    on_url_change: impl Fn(String) + 'static,
) {
    let doc = document();

    // Watch a specific container or document.body
    let target: web_sys::Node = if let Some(sel) = container_selector {
        doc.query_selector(sel).ok().flatten()
            .map(|el| el.unchecked_into::<web_sys::Node>())
            .unwrap_or_else(|| doc.body().unwrap().unchecked_into())
    } else {
        doc.body().unwrap().unchecked_into()
    };

    // Debounced MutationObserver (500ms)
    let on_change = std::rc::Rc::new(on_change);
    let mutation_callback = Closure::wrap(Box::new(
        move |_mutations: js_sys::Array, _observer: web_sys::MutationObserver| {
            // Cancel previous debounce timer, start new 500ms timer
            // Call on_change() after debounce
        },
    ) as Box<dyn FnMut(js_sys::Array, web_sys::MutationObserver)>);

    let observer = web_sys::MutationObserver::new(
        mutation_callback.as_ref().unchecked_ref()
    ).unwrap();

    let init = web_sys::MutationObserverInit::new();
    init.set_child_list(true);
    init.set_subtree(true);
    observer.observe_with_options(&target, &init).unwrap();
    mutation_callback.forget();

    // URL polling (1s interval) for pushState navigation
    let on_url_change = std::rc::Rc::new(on_url_change);
    let url_poll = Closure::wrap(Box::new(move || {
        let new_url = window().location().href().unwrap_or_default();
        // Compare with stored last URL, call on_url_change if different
    }) as Box<dyn FnMut()>);

    window().set_interval_with_callback_and_timeout_and_arguments_0(
        url_poll.as_ref().unchecked_ref(), 1000
    ).unwrap();
    url_poll.forget();
}
```

Required web-sys features: `MutationObserver`, `MutationObserverInit`.

## Build System (justfile)

```justfile
build-ext:
    wasm-pack build crates/my-ext --target web --out-dir ../../extension/pkg

build-content:
    wasm-pack build crates/my-ext-content --target web --out-dir ../../extension/pkg-content

build-bg:
    wasm-pack build crates/my-ext-bg --target web --out-dir ../../extension/pkg-bg

build-all-wasm: build-ext build-content build-bg
    @echo "All WASM crates built."
    cp crates/my-ext-content/content-bridge.js extension/content-bridge.js
    cp crates/my-ext-bg/bg-bridge.js extension/bg-bridge.js
    cp crates/my-ext/popup-bridge.js extension/popup-bridge.js

test:
    cargo test --workspace

lint:
    cargo clippy --workspace -- -D warnings
    cargo fmt --check
```

**Important**: `--out-dir` is relative to the crate, not the workspace root. Use `../../extension/pkg-*` to output directly into the extension directory.

## WASM Size Optimization

Content scripts load on every page. Keep the WASM binary small:

- **Avoid `regex` crate** — adds ~200KB. Use `str::contains` with word boundary checks for keyword matching
- **Avoid `url` crate** — use `web_sys::Url` in service workers (zero WASM cost) or simple `str::contains` matching in content scripts
- **Enable only needed `web-sys` features** — each feature adds to the binary
- **Use `opt-level = "z"` in release profile** — optimize for size

```toml
[profile.release]
codegen-units = 1
lto = true
opt-level = "z"
panic = "abort"
strip = true
```

If `wasm-pack` build fails with bulk memory errors, add:

```toml
[package.metadata.wasm-pack.profile.release]
wasm-opt = false
```

## Message Passing with serde-wasm-bindgen

All messages between contexts use `serde_wasm_bindgen` for typed conversion:

```rust
// Serialize Rust → JS
let msg = Message::Activate { tab_id: Some(42) };
let js_msg: JsValue = serde_wasm_bindgen::to_value(&msg).unwrap();

// Deserialize JS → Rust
let msg: Message = serde_wasm_bindgen::from_value(js_val)?;
```

**Why not `serde_json`?** `serde_wasm_bindgen` converts directly between Rust types and JS values without going through a JSON string intermediate. This is faster and preserves JS types (numbers, booleans) correctly.

## Guidelines

- **Keep bridge JS files minimal.** Only Chrome API wrappers — no business logic. If you're writing `if` statements in a bridge file, that logic belongs in Rust.
- **Content script handlers must be synchronous.** Chrome's `onMessage` listener expects a synchronous `sendResponse` call for content scripts. Use `wasm_bindgen_futures::spawn_local` for fire-and-forget async work.
- **Background handlers return Promises.** The loader calls `.then(sendResponse)` and returns `true` to keep the channel open.
- **Use `thread_local!` not `static`.** WASM is single-threaded. `thread_local! RefCell<T>` gives interior mutability without `Arc` or `Mutex`.
- **Bridge path `/` means crate root.** `#[wasm_bindgen(module = "/bridge.js")]` resolves relative to the crate root, not the workspace root.
- **Test pure Rust logic with `cargo test`.** Site detection, URL parsing, keyword matching, message serialization — all testable without a browser. The `rlib` in `crate-type` enables this.
- **One shared types crate, no WASM deps.** The types crate only needs `serde` and `serde_json`. This keeps `cargo test` fast and avoids wasm-bindgen in test builds.
- **Prefer `web_sys::Url` over the `url` crate** in the background service worker. `web_sys::Url` uses the browser's URL parser at zero WASM binary cost. The `url` crate adds ~50KB.
- **Respect the user's CLAUDE.md.** Check for project-specific conventions before applying generic patterns.

## Other

- Some AI LLMs suggest changing the Rust edition in Cargo.toml to 2021 from 2024. Their reasoning is mistaken: they are not up to date. The latest Rust edition is 2024 and Cargo.toml files with this should not be changed.
