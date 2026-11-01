# AIS-487 Competitive Research, Feature Subtraction & Single-Screen UX

## 1. Competitive Artillery/Mortar Calculator Landscape
- **WARDOGS Community Calculators (`wardogsmortar.com`, `ArtyDogs`, `SCHaulers IDF Calculator`, `wardogshub.gg`, `The Pretender's` Voice Calculator)**:
  - Players use WARDOGS' built-in `Mark Coordinates` (`x78.50 y69.50`) or rangefinder distance pings (`420m`) and want a **single-screen** workflow with zero tab switching.
  - Fastest tools let players paste or type **both Gun + Target coordinates on one line** (`78.5 69.5 82.18 71.53` or `78.5 69.5 -> 82.18 71.53`) or enter a **direct range in meters** (`420m`, `1450m`), and copy the firing solution in a single click.
- **Squad Community Benchmarks (`SquadMC` / `squadmc.ende.pro`, `SquadCalc`)**:
  - No secondary pages for everyday operation; no academic formula tabs; 1-click solution copy on the primary hero banner.

## 2. Feature Subtraction (Removed Bloat in `index.html`)
1. **Removed `📐 BALLISTIC MATH` Tab (`#tabPythBtn`, `#pythagorasViewContainer`)**: Replaced the academic right-triangle homework view with more focus on the Tactical Map and 8.5x Classic Fire Control views.
2. **Removed Inline `3D Topographic FPV` Drawer (`#reconPreviewDrawer`)**: Freed vertical height inside the primary Map card (`recon.html` already provides the dedicated multi-monitor pop-out 3D Recon window).
3. **Removed Duplicate Header & Map-Bar Controls**:
   - Removed duplicate `🎯 FIRING RANGE` top-header button (already in the `MAP:` selector).
   - Removed duplicate `#mapBarLockMortarBtn` (`🔓 Gun Unlocked`) and redundant `➕` / `➖` map-bar buttons (scroll wheel + `resetMapZoom()` handle zoom).
   - Removed redundant `🔊 Compute & Speak Solution` button at the bottom of the Coordinates card (calculations run live on every click/input, and `🔊 Read` is in the Solution Hero).
   - Removed redundant `Custom Meter Adjustment` 2-input form (`#customRangeAdj`, `#customDeflAdj`) and duplicate 3-button clipboard row (`📋 Paste Tgt`, `💥 Paste Hit`, `📤 Copy Sol`) from the bottom of the Forward Observer card, placing `🎯 ZERO` (`clearAimOffset()`) in the center of the 3x3 nudge grid.

## 3. Zero-Friction Additions (`index.html` & `ocr_sniff.py`)
1. **1-Click Top-Bar `🎙️ PTT` Button (`#topPttToggleBtn`, `toggleTopBarPtt()`)**: Toggle In-Game Global Push-to-Talk (`Mouse 4` / `Space`) directly from the top bar alongside `📷 Auto-OCR` and `🔍 Scan Now` without switching to Page 2.
2. **1-Click Firing Solution Hero Copy (`#solutionHeroBar`)**: Clicking anywhere on the Firing Solution Hero copies the 1-line firing solution (`[WARDOGS L81 MORTAR] ELEV: ...`) to the clipboard and flashes `✅ COPIED TO CLIPBOARD!`.
3. **Smart Omni-Input (`#quickCoordInput`) & `ocr_sniff.py` Dual-Pair / Direct-Range Support**:
   - **Single-Line Dual `Gun -> Target` Pair (`_extract_dual_pairs_from_line`, `parseDualCoordLineJs`)**: Entering or scanning `78.5 69.5 82.18 71.53`, `78.5 69.5 -> 82.18 71.53`, `x78.50 y69.50 x82.18 y71.53`, or `7850 6950 8218 7153` sets Gun (`CL`) and Target in one step.
   - **Direct Range Mode**: Entering `420m`, `1450m`, `range 420`, or speaking `"range 420"` immediately solves for that flat-ground meter distance.
4. **Verification**: `71 passed` across 9 deterministic test files (`pytest -q`).
