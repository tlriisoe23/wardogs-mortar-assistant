# WARDOGS Mortar & Artillery Assistant

A tactical voice-activated fire-control assistant, interactive map suite, and ballistic computer for **WARDOGS** (`L81 Mortar` and `SPH-2 Self-Propelled Howitzer`).

---

## Key Capabilities

### 1. Single-Screen Zero-Scroll 1080p Workspace Architecture (`AIS-436` / `AIS-487`)
* **⚡ Always-Visible Top-Bar Omni-Input, PTT & Auto-OCR Strip**:
  * **Smart Omni-Input (`#quickCoordInput`)**: Type or paste directly in the top bar without switching pages:
    * **Single Coordinate Pair**: `78.5 69.5 CL` locks Gun (`CL`), `82.18 71.53` sets Enemy Target, `82.5 71.8 HIT` walks in splash offset.
    * **Single-Line Dual `Gun -> Target` Pair**: `78.5 69.5 -> 82.18 71.53` (or `78.5 69.5 82.18 71.53` / `x78.50 y69.50 x82.18 y71.53`) sets both Gun (`CL`) and Enemy Target in one action.
    * **Direct Range Mode**: `420m`, `1450m`, or `range 420` switches to `🎯 Firing Range` mode and solves the elevation/time-of-flight for that exact distance in meters.
  * **1-Click `📷 Auto-OCR` (`#topOcrToggleBtn`), `🔍 Scan Now` (`Alt+O`) & `🎙️ PTT` (`#topPttToggleBtn`)**: Start/stop the background screen OCR & clipboard watcher, trigger an immediate on-demand scan, or toggle In-Game Push-to-Talk (`Mouse 4` / `Space`) directly from the primary map screen with live status in `#topOcrStatusBadge`.
  * **`🖼️ Paste/OCR` & Global `Ctrl+V` Screenshot/Text Paste**: Paste a raw coordinate string or a cropped screenshot (`Win+Shift+S` $\rightarrow$ `Ctrl+V`) anywhere outside text inputs to extract single or dual `Gun -> Target` coordinates automatically via `POST /api/ocr/extract-image` (`qwen3-vl:2b-instruct` with local `winocr` fallback).
* **🗺️ Page 1 — Tactical Map & Fire Control (Zero-Scroll `100dvh` Fit)**:
  * **1-Click Firing Solution Hero Copy (`#solutionHeroBar`)**: Click anywhere on the Firing Solution Hero to copy the formatted 1-line firing solution (`[WARDOGS L81 MORTAR] ELEV: 632 MIL | AZ: 060.9° (1083 MIL) | RNG: 420m | TOF: 12.1s`) to the clipboard.
  * **4K Offline Base Maps (`4,096 × 4,096 px`) + 16K (`16,384 × 16,384 px`, `1m/px`) Quadtree Tile Pyramid Streaming**: Local `maps/*.webp` base layers are stitched at `4,096 × 4,096 px` (`Level 3`, `4m/px`) and automatically stream `Level 4` (`8,192 × 8,192 px`, `2m/px`) and `Level 5` (`16,384 × 16,384 px`, `1m/px` — 64× higher pixel density than `2,048 × 2,048`) tiles from `cdn.wardogshub.gg` with automatic `wardog-fire-control.pages.dev` mirror failover and progressive parent-tile fallback.
  * **Interactive Tactical Map (Click-to-Correct)**: Right-click to place your Gun/Mortar (`CL`), Left-click to place Enemy Target, and **Shift+Click** where a shell landed to apply an automatic non-destructive ballistic aim offset.
  * **Classic Fire Control (8.5× Deep Building Zoom)**: Embedded 2-way synchronized `wardog-fire-control` view with 8.5× building zoom and 3× faster scroll wheel.
  * **20m Topographic DEM & Ridge Clearance**: Automatic bilinear elevation lookup (`ΔZ`) across **Bakurani**, **Ozeti**, and **Zestafona** (`data/terrain/terrain_dem.json`) plus raycast ridge-collision warnings along the trajectory.
  * **Pop-Out 3D Topographic Recon (`recon.html`)**: Dedicated multi-monitor 3D wireframe terrain mesh with incoming parabolic shell arc and 1m/px satellite spotter reticle (`BroadcastChannel` sync).
  * **Forward Observer 3×3 Nudge Pad**: One-click `ADD`/`DROP`/`LEFT`/`RIGHT` adjustments along the Gun-Target line of fire, centered `🎯 ZERO` reset, and `↩ UNDO` (`Ctrl+Z`).
* **⚙️ Page 2 — Voice Setup & Activity Log**:
  * **Private Coordinate Chat (`CL` & Dual-Pair Rules)**:
    1. **Two pairs on one line** (`78.5 69.5 82.18 71.53` or `78.5 69.5 -> 82.18 71.53`) $\rightarrow$ First pair locks **Gun (`CL`)**, second pair sets **Enemy Target** (or **Splash (`HIT`)** if tagged).
    2. **Add `CL` to a single coordinate line** (`78.5 69.5 CL` or `CL 7850 6950`) $\rightarrow$ Sets and locks your **Current Location** (Gun/Mortar).
    3. **Any other coordinate line** (`82.18 71.53` or `8218 7153`) $\rightarrow$ Automatically assumed to be the **Enemy Target** until a new `CL` is entered.
    4. **Add `HIT` / `SPLASH`** (`82.50 71.80 HIT`) $\rightarrow$ Automatically shifts your Gun Aim Offset to walk the next round onto the target.
  * **Multiline `winocr` Screen OCR, `recent_events` Ring Buffer & In-Game `Ctrl+C` Clipboard Watcher**:
    * Native Windows WinRT OCR (`winocr`) preserves true line boundaries via `res['lines']` (`_extract_text_from_winocr_result`), applies 2×/3× `BICUBIC` + `ImageOps.autocontrast` preprocessing for small HUD/chat crops, filters self-UI text via `SELF_UI_IGNORE_RE`, and queues multi-line `CL` + `TARGET` pairs in a chronological `recent_events` ring buffer so sequential events are never dropped between frontend polls (100% Easy Anti-Cheat safe).
    * Also watches the system clipboard so you can type `78.5 69.5 CL` or `82.18 71.53` in the in-game chat bar and press `Ctrl+A` $\rightarrow$ `Ctrl+C` for instant 100% accuracy.
  * **In-Game Global Push-to-Talk (`win32 GetAsyncKeyState`)**:
    * Hold **Mouse 4** (or any bound key/mouse button) directly inside WARDOGS without Alt-Tabbing to speak coordinates or FO adjustments.
  * **Global Audio Mute (`🔊 AUDIO: ON` / `🔇 MUTED`)**:
    * Top header button and voice commands (`"mute"` / `"unmute"`) silence all Neural AI TTS readouts and PRC-117 radio squelch effects while keeping the passive `⏱️ TOF` readout visible.
* **🖥️ Tauri v3.0 Native Desktop HUD (`src-tauri/`)**:
  * Native Rust/WebView2 desktop wrapper (`1540×940` default window, `0%` background GPU/VRAM polling) with pure-Rust RK4 ballistics (`src-tauri/src/mortar_calc.rs`), 20m bilinear DEM (`src-tauri/src/dem.rs`), detachable `320×110` PIP mini-HUD, and global OS hotkeys (`Alt+M` Lock Gun, `Alt+R` Reset Mission, `Alt+Up/Down` ΔZ ±5m, `Alt+A` Toggle Arc, `Alt+O` Scan OCR Now, `Alt+C` Click-Through Overlay, `Alt+S` Audio Mute).

---

## 2. Ballistic Weapons & Mathematical Models

### Coordinate Geometry (Bakurani, Ozeti, Zestafona, Firing Range)
* **1 grid coordinate unit = 100 meters** ($0.01\text{ unit} = 1\text{ meter}$).
* $+Y$ points **North** ($0^\circ / 360^\circ$), $+X$ points **East** ($90^\circ$).
* **Range ($c$)**:
  $$\Delta X = (X_t - X_m) \times 100\text{ m}, \quad \Delta Y = (Y_t - Y_m) \times 100\text{ m}, \quad c = \sqrt{(\Delta X)^2 + (\Delta Y)^2}$$
* **Azimuth ($\theta$)**:
  $$\theta = \left(\operatorname{atan2}(\Delta X, \Delta Y) \times \frac{180}{\pi} + 360^\circ\right) \bmod 360^\circ, \quad \text{Mils} = \operatorname{round}\left(\theta \times \frac{6400}{360}\right)$$

### Supported Weapons
1. **🟢 L81 Mortar (`132m – 684m` flat sight, `150 – 850 MIL`; extended `80m – 697m` on slope)**:
   * Community-verified 10-mil elevation lookup table with plunge-angle terrain height differential (`ΔZ`) compensation.
2. **🟠 SPH-2 Self-Propelled Howitzer — High Arc (`780m – 2,629m`, `610 – 1,390 MIL`)**:
   * Full RK4 aerodynamic drag trajectory solver (`solve_sph2_terrain_mils`) for exact `ΔZ` elevation solutions and `5.0°` fore/aft chassis pitch compensation (`sph_platform_correct_aim`).
3. **🔵 SPH-2 Self-Propelled Howitzer — Low Arc (`1,181m – 2,629m`, `20 – 600 MIL`)**:
   * Direct/low-angle trajectory table with dual-arc comparison pill in the Firing Solution Hero.

---

## 3. Quick Start

### Launch the Web Audio & Map HUD
Double-click **`start.bat`** or run:
```powershell
python server.py
```
Your browser will open `http://localhost:8765`.

### CLI Mode & Automated Verification Suite (`181` Tests)
```powershell
python mortar_calc.py
python -m pytest -q
```

---

## 4. Repository Structure

* `index.html` — Primary Single-Screen Zero-Scroll Tactical Web HUD (Top-Bar Smart Omni-Input, PTT & Auto-OCR + Page 1 Tactical Map & Fire Control + Page 2 Voice Setup & Activity Log)
* `classic-fire-control.html` & `assets/classic/` — Embedded 8.5× Deep-Zoom Classic Fire Control map with 2-way `postMessage` sync
* `recon.html` — Dedicated multi-monitor 3D Topographic Recon & 1m/px Satellite Spotter Scope pop-out window (`BroadcastChannel` sync)
* `server.py` — Local HTTP server, Neural Edge-TTS endpoint, Global `win32` PTT key hook, and OCR/Clipboard endpoints (`/api/ocr/status`, `/api/ocr/toggle`, `/api/ocr/scan-now`, `/api/ocr/extract-image`, `/api/desktop-hud`)
* `mortar_calc.py` — Python ballistics engine (`L81 Mortar` & `SPH-2` High/Low Arc, RK4 drag solver, DEM lookup)
* `ocr_sniff.py` — Multiline Windows WinRT OCR (`winocr` `res['lines']` + 2×/3× `BICUBIC` autocontrast upscaling + single-line dual `Gun -> Target` parser + `recent_events` ring buffer) + In-Game `Ctrl+C` Clipboard coordinate watcher (`CL` / `TARGET` / `HIT`)
* `src-tauri/` — Tauri v3.0 Native Rust/WebView2 Desktop HUD (`mortar_calc.rs`, `dem.rs`, global hotkeys, and PIP mini-HUD)
* `targets_db.py` — 30 pre-aimed community blind-fire hotspots across Bakurani, Ozeti, Zestafona, and the Firing Range
* `data/terrain/terrain_dem.json` — 20m hypsometric Digital Elevation Models (DEM) for Bakurani, Ozeti, and Zestafona
* `data/map_callouts.json` — Sub-sector tactical landmark callouts
* `tests/` — 181 deterministic offline unit & integration tests (`test_dom_a11y.py`, `test_mortar_calc.py`, `test_ocr_sniff.py`, `test_omniconvert_ocr_bridge.py`, `test_server.py`, `test_server_tts.py`, `test_solver_hardening.py`, `test_targets_schema.py`, `test_tauri_desktop_wrapper.py`, `test_tauri_v3_evolution.py`, `test_v3_desktop_evolution.py`)

---

<!-- AUTO-REPO-INVENTORY:START -->
## Automated Repository Inventory (Auto-Synced)

- **Verification Suite (`pytest`):** `pytest -q` (`>= 11` test modules discovered)
<!-- AUTO-REPO-INVENTORY:END -->
