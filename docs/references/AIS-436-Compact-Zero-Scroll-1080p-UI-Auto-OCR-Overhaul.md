# AIS-436 Compact Zero-Scroll 1080p UI & Auto-OCR Overhaul

# AIS-436: Compact Zero-Scroll 1080p UI, Top-Bar Quick Coords & Multiline Auto-OCR Overhaul

- **Commit**: `bb47c86` (`e73d02a` code + `bb47c86` documentation)
- **Compact Zero-Scroll 1080p Layout (`index.html` & `src-tauri/tauri.conf.json`)**:
  - Viewport-locked `height: 100dvh; overflow: hidden` on desktop (`>=1051px`) with compact `clamp()` typography across Page 1 and Page 2 so the entire HUD fits on a single 1080p screen (`1540x940` / `1920x1080`) without vertical scrolling.
- **Always-Visible Top-Bar Quick Coords & Auto-OCR Strip (`index.html`)**:
  - `#quickCoordInput`: Type `78.5 69.5 CL` (locks Gun), `82.18 71.53` (sets Target), or `82.5 71.8 HIT` (applies splash offset) from either page.
  - `#topOcrToggleBtn` (`📷 Auto-OCR`), `🔍 Scan Now` (`Alt+O`), `🖼️ Paste/OCR` (`Ctrl+V` screenshot/text paste via `POST /api/ocr/extract-image`), and `#topOcrStatusBadge`.
- **Multiline `winocr` & `recent_events` Ring Buffer (`ocr_sniff.py` & `server.py`)**:
  - `_extract_text_from_winocr_result` preserves true line breaks from `res['lines']`.
  - 2x/3x `BICUBIC` + `ImageOps.autocontrast` preprocessing for small crops.
  - `SELF_UI_IGNORE_RE` prevents self-UI loop feedback.
  - `recent_events` ring buffer (`deque(maxlen=16)`) ensures multi-line `CL` + `TARGET` pairs are replayed in order.
  - `extract_text_via_winocr_bytes` provides a local Windows OCR fallback in `POST /api/ocr/extract-image` alongside `qwen3-vl:2b-instruct`.
- **Verification**: `69/69` `pytest` tests passing (`tests/test_mortar_calc.py`, `tests/test_ocr_sniff.py`, `tests/test_ocr_extract_endpoint.py`, `tests/test_tauri_desktop_wrapper.py`, `tests/test_server_security.py`, `tests/test_elevation_and_contours.py`, `tests/test_ui_ergonomics.py`, `tests/test_v3_desktop_features.py`).
