# WARDOGS Mortar & Artillery Assistant

A tactical voice-activated fire-control assistant, interactive map suite, and ballistic computer for **WARDOGS** (`L81 Mortar` and `SPH-2 Self-Propelled Howitzer`).

---

## Key Capabilities

### 1. Compact Zero-Scroll 1080p 2-Page Workspace Architecture (`AIS-436`)
* **⚡ Always-Visible Top-Bar Quick Coords & Auto-OCR Strip**:
  * **Quick Coords Input (`#quickCoordInput`)**: Type or paste coordinates directly in the top bar without switching pages (`78.5 69.5 CL` locks Gun, `82.18 71.53` sets Target, `82.5 71.8 HIT` walks in splash offset).
  * **1-Click `📷 Auto-OCR` (`#topOcrToggleBtn`) & `🔍 Scan Now` (`Alt+O`)**: Starts/stops the background screen OCR & clipboard watcher or triggers an immediate on-demand scan from either page, with live status and detected coordinates shown in `#topOcrStatusBadge`.
  * **`🖼️ Paste/OCR` & Global `Ctrl+V` Screenshot/Text Paste**: Paste a raw coordinate string or a cropped screenshot (`Win+Shift+S` $\rightarrow$ `Ctrl+V`) anywhere outside text inputs to extract coordinates automatically via `POST /api/ocr/extract-image` (`qwen3-vl:2b-instruct` with local `winocr` fallback).
* **🗺️ Page 1 — Manual Map & Adjustments (Zero-Scroll `100dvh` Fit)**:
  * **Interactive Tactical Map (Click-to-Correct)**: Right-click to place your Gun/Mortar (`CL`), Left-click to place Enemy Target, and **Shift+Click** where a shell landed to apply an automatic non-destructive ballistic aim offset.
  * **Classic Fire Control (8.5× Deep Building Zoom)**: Embedded 2-way synchronized `wardog-fire-control` view with 8.5× building zoom and 3× faster scroll wheel.
  * **20m Topographic DEM & Ridge Clearance**: Automatic bilinear elevation lookup (`ΔZ`) across **Bakurani**, **Ozeti**, and **Zestafona** (`data/terrain/terrain_dem.json`) plus raycast ridge-collision warnings along the trajectory.
  * **Collapsible 3D Topographic FPV & 1m/px Spotter Scope**: Split-screen 3D wireframe terrain mesh with incoming parabolic shell arc and 1m/px satellite spotter reticle, plus pop-out multi-monitor window (`recon.html`).
  * **Forward Observer Adjustments**: One-click `ADD`/`DROP`/`LEFT`/`RIGHT` adjustments along the Gun-Target line of fire, plus `↩ UNDO` (`Ctrl+Z`).
* **🎙️ Page 2 — Voice, Private `CL` Chat & Auto-OCR**:
  * **Private Coordinate Chat (`CL` Rule)**:
    1. **Add `CL` to a coordinate line** (`78.5 69.5 CL` or `CL 7850 6950`) $\rightarrow$ Sets and locks your **Current Location** (Gun/Mortar).
    2. **Any other coordinate line** (`82.18 71.53` or `8218 7153`) $\rightarrow$ Automatically assumed to be the **Enemy Target** until a new `CL` is entered.
    3. **Add `HIT` / `SPLASH`** (`82.50 71.80 HIT`) $\rightarrow$ Automatically shifts your Gun Aim Offset to walk the next round onto the target.
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

### CLI Mode & Automated Verification Suite (`69` Tests)
```powershell
python mortar_calc.py
python -m pytest -q
```

---

## 4. Repository Structure

* `index.html` — Primary Compact Zero-Scroll 2-Page Tactical Web HUD (Top-Bar Quick Coords & Auto-OCR + Page 1 Manual Map & Adjustments + Page 2 Voice, Private `CL` Chat & Auto-OCR)
* `classic-fire-control.html` & `assets/classic/` — Embedded 8.5× Deep-Zoom Classic Fire Control map with 2-way `postMessage` sync
* `recon.html` — Dedicated multi-monitor 3D Topographic Recon & 1m/px Satellite Spotter Scope pop-out window (`BroadcastChannel` sync)
* `server.py` — Local HTTP server, Neural Edge-TTS endpoint, Global `win32` PTT key hook, and OCR/Clipboard endpoints (`/api/ocr/status`, `/api/ocr/toggle`, `/api/ocr/scan-now`, `/api/ocr/extract-image`, `/api/desktop-hud`)
* `mortar_calc.py` — Python ballistics engine (`L81 Mortar` & `SPH-2` High/Low Arc, RK4 drag solver, DEM lookup)
* `ocr_sniff.py` — Multiline Windows WinRT OCR (`winocr` `res['lines']` + 2×/3× `BICUBIC` autocontrast upscaling + `recent_events` ring buffer) + In-Game `Ctrl+C` Clipboard coordinate watcher (`CL` / `TARGET` / `HIT`)
* `src-tauri/` — Tauri v3.0 Native Rust/WebView2 Desktop HUD (`mortar_calc.rs`, `dem.rs`, global hotkeys, and PIP mini-HUD)
* `targets_db.py` — 30 pre-aimed community blind-fire hotspots across Bakurani, Ozeti, Zestafona, and the Firing Range
* `data/terrain/terrain_dem.json` — 20m hypsometric Digital Elevation Models (DEM) for Bakurani, Ozeti, and Zestafona
* `data/map_callouts.json` — Sub-sector tactical landmark callouts
* `tests/` — 69 deterministic offline unit & integration tests (`test_mortar_calc.py`, `test_ocr_sniff.py`, `test_ocr_extract_endpoint.py`, `test_tauri_desktop_wrapper.py`, `test_server_security.py`, `test_elevation_and_contours.py`, `test_ui_ergonomics.py`, `test_v3_desktop_features.py`)
