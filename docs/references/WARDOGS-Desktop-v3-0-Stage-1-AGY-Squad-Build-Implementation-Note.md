# WARDOGS Desktop v3.0 Stage 1 AGY Squad Build Implementation Note

# WARDOGS Desktop v3.0 Stage 1 AGY Squad Build Implementation Note

## Implemented Architecture & Deliverables (AIS-340)

### 1. Pure-Rust RK4 Ballistics & 20m Hypsometric Bilinear DEM Engine
- `src-tauri/src/dem.rs`: Implements 20m bilinear hypsometric interpolation over embedded Bakurani, Ozeti, and Zestafona elevation grids (160x160 float points). Includes 100-sample trajectory ridge collision raycasting with 5.0m clearance buffer and raw little-endian f32 byte stream generation for zero-overhead WebGL rendering.
- `src-tauri/src/mortar_calc.rs`: Complete Runge-Kutta 4th-order (RK4) non-linear aerodynamic drag solver with bisection root finding (`solve_sph2_terrain_mils`) for terrain elevation differentials (ΔZ) across High and Low Arc modes. Fully integrates SPH-2 5.0° chassis pitch yaw compensation (`sph_platform_correct_aim`) and Forward Observer adjustment mechanics.

### 2. Native System Tray, Plugins & Security Capabilities
- `src-tauri/src/lib.rs`: Full `TrayIconBuilder` and `MenuBuilder` setup supporting Active, Ghost Click-Through (`Alt+C`), and Audio Muted (`Alt+S`) toggle states, plus instant HUD summon on left-click.
- Plugins configured: `tauri-plugin-single-instance`, `tauri-plugin-deep-link` (handling `wardogs://` URI schemes), `tauri-plugin-store` for persistent configuration, and `tauri-plugin-updater` with Ed25519 Minisign cryptographic verification.
- Capabilities ACL (`src-tauri/capabilities/default.json`): Least-privilege permissions assigned across `main`, `pip-recon`, and `pip-hud` windows.

### 3. Multi-Window Picture-in-Picture Mini-HUD & Zero-Copy IPC
- `pip-hud.html`: 320x110 px frameless, transparent, always-on-top tactical strip with `data-tauri-drag-region`, live mil-dot elevation/azimuth metrics, and event listeners.
- Display auto-discovery: `get_available_monitors` and `snap_window_to_monitor` automatically detects secondary screens and prioritizes `\\.\DISPLAY1`.
- Raw Binary IPC via `tauri::ipc::Response` (`get_dem_heightmap_raw`) and streaming via `tauri::ipc::Channel` (`stream_trajectory_channel`, `stream_hud_telemetry_channel`).
- `/api/desktop-hud` telemetry on `:8099` (and `:8765`) reporting v3.0 capabilities with guaranteed 0% background GPU/VRAM/system polling on `Tanner-Z390`.
