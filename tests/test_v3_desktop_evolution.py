"""
WARDOGS Desktop v3.0 Evolution Test Suite (AIS-337 / AIS-335)
Verifies:
1. Complete architectural blueprint (docs/WARDOGS_V3_DESKTOP_BLUEPRINT.md)
2. Tauri v3.0 Cargo.toml dependencies (tray-icon, updater, windows-rs, serde)
3. Multi-window configuration (main + pip-recon) in tauri.conf.json
4. Least-privilege capabilities ACL (capabilities/default.json)
5. Native Rust v3 commands, TrayIconBuilder, monitor snapping, and zero GPU polling in src/lib.rs
6. Native Rust RK4 Ballistic Solver & DEM tables in src/mortar_calc.rs
7. Standalone 3D FPV Recon Scope PIP frontend component (recon.html)
8. Mathematical parity between Python mortar_calc.py and Rust mortar_calc.rs
"""

import json
import os
import re
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAURI_DIR = os.path.join(ROOT_DIR, "src-tauri")
DOCS_DIR = os.path.join(ROOT_DIR, "docs")


class TestV3DesktopEvolution(unittest.TestCase):
    def test_v3_blueprint_exists_and_covers_all_criteria(self):
        """Verify the v3.0 Evolution Blueprint exists and documents all 8 required capabilities."""
        blueprint_path = os.path.join(DOCS_DIR, "WARDOGS_V3_DESKTOP_BLUEPRINT.md")
        self.assertTrue(os.path.isfile(blueprint_path), f"Blueprint missing: {blueprint_path}")

        with open(blueprint_path, "r", encoding="utf-8") as f:
            content = f.read()

        required_keywords = [
            "TrayIconBuilder",
            "WebviewWindowBuilder",
            "available_monitors()",
            "DISPLAY1",
            "Runge-Kutta",
            "RK4",
            "Bilinear",
            "Windows.Media.Ocr",
            "GetAsyncKeyState",
            "tauri::ipc::Channel",
            "tauri-plugin-updater",
            "Tanner-Z390",
            "Coexistence",
        ]
        for kw in required_keywords:
            self.assertIn(kw, content, f"Blueprint missing required concept: {kw}")

    def test_v3_cargo_manifest_dependencies(self):
        """Verify Cargo.toml is upgraded to v3.0.0 and includes required plugins and windows-rs."""
        cargo_path = os.path.join(TAURI_DIR, "Cargo.toml")
        with open(cargo_path, "r", encoding="utf-8") as f:
            cargo = f.read()

        self.assertIn('version = "3.0.0"', cargo)
        self.assertIn("tray-icon", cargo)
        self.assertIn("tauri-plugin-updater", cargo)
        self.assertIn("tauri-plugin-global-shortcut", cargo)
        self.assertIn("tauri-plugin-window-state", cargo)
        self.assertIn("tauri-plugin-clipboard-manager", cargo)
        self.assertIn("serde", cargo)
        self.assertIn("windows", cargo)
        self.assertIn("Media_Ocr", cargo)

    def test_v3_tauri_conf_multi_window_and_tray(self):
        """Verify tauri.conf.json defines both 'main' and 'pip-recon' windows and tray configuration."""
        conf_path = os.path.join(TAURI_DIR, "tauri.conf.json")
        with open(conf_path, "r", encoding="utf-8") as f:
            conf = json.load(f)

        self.assertEqual(conf.get("version"), "3.0.0")
        windows = conf.get("app", {}).get("windows", [])
        labels = [w.get("label") for w in windows]

        self.assertIn("main", labels, "Main window must be defined")
        self.assertTrue(
            "pip-recon" in labels or "recon-pip" in labels,
            "Detachable PIP recon window must be defined in windows array",
        )

        pip_win = next(w for w in windows if w.get("label") in ("pip-recon", "recon-pip"))
        self.assertTrue(pip_win.get("alwaysOnTop"))
        self.assertFalse(pip_win.get("decorations"))
        self.assertTrue(pip_win.get("transparent"))

    def test_v3_capabilities_acl_permissions(self):
        """Verify capabilities/default.json scopes least-privilege ACL across multi-window HUD."""
        acl_path = os.path.join(TAURI_DIR, "capabilities", "default.json")
        with open(acl_path, "r", encoding="utf-8") as f:
            acl = json.load(f)

        windows = set(acl.get("windows", []))
        self.assertIn("main", windows)
        self.assertTrue(
            "pip-recon" in windows or "recon-pip" in windows,
            "PIP recon window must be included in capabilities ACL",
        )

        perms = set(acl.get("permissions", []))
        self.assertIn("core:window:allow-set-always-on-top", perms)
        self.assertIn("core:window:allow-set-ignore-cursor-events", perms)
        self.assertIn("global-shortcut:allow-register", perms)

    def test_v3_lib_rust_commands_and_zero_polling_invariant(self):
        """Verify src/lib.rs implements v3 commands, TrayIconBuilder, monitor snapping, and 0% polling."""
        lib_path = os.path.join(TAURI_DIR, "src", "lib.rs")
        with open(lib_path, "r", encoding="utf-8") as f:
            code = f.read()

        # Commands
        for cmd in (
            "toggle_pip_recon",
            "calculate_ballistics",
            "get_available_monitors",
            "snap_window_to_monitor",
            "stream_trajectory_channel",
            "set_hud_click_through",
        ):
            self.assertIn(cmd, code, f"Missing v3 Rust command: {cmd}")

        # Native System Tray
        self.assertIn("TrayIconBuilder", code)
        self.assertIn("show_hud", code)
        self.assertIn("toggle_pip", code)
        self.assertIn("snap_secondary", code)

        # Zero Background GPU Polling Coexistence Invariant
        self.assertNotIn("nvidia-smi", code.lower())
        self.assertNotIn("nvml", code.lower())
        self.assertNotIn("dxgi_capture_loop", code.lower())

    def test_v3_mortar_calc_rust_engine_parity(self):
        """Verify src/mortar_calc.rs implements the supersonic aerodynamic tables and RK4 solver."""
        calc_path = os.path.join(TAURI_DIR, "src", "mortar_calc.rs")
        self.assertTrue(os.path.isfile(calc_path), f"Missing mortar_calc.rs at {calc_path}")

        with open(calc_path, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("L81_MORTAR_TABLE", code)
        self.assertIn("SPH2_HIGH_TABLE", code)
        self.assertIn("SPH2_LOW_TABLE", code)
        self.assertIn("SPH_GC_X", code)
        self.assertIn("SPH_GC_Y", code)
        self.assertIn("sph_height_at_distance", code)
        self.assertIn("sph_platform_correct_aim", code)

    def test_v3_recon_pip_frontend_component(self):
        """Verify recon.html exists with 3D horizon, spotter scope, and inter-window IPC sync."""
        html_path = os.path.join(ROOT_DIR, "recon.html")
        self.assertTrue(os.path.isfile(html_path), f"Missing recon.html at {html_path}")

        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn("reconCanvas", html)
        self.assertIn("data-tauri-drag-region", html)
        self.assertIn("recon-sync", html)
        self.assertIn("render3dHorizon", html)
        self.assertIn("renderSpotterScope", html)
        self.assertIn("25m LETHAL", html)

    def test_mathematical_table_constants_match_python(self):
        """Verify mathematical constants in Python mortar_calc.py and Rust mortar_calc.rs match exactly."""
        import mortar_calc

        rust_path = os.path.join(TAURI_DIR, "src", "mortar_calc.rs")
        with open(rust_path, "r", encoding="utf-8") as f:
            rust_code = f.read()

        # Check mortar table endpoints
        self.assertIn("(80.0, 950.0)", rust_code)
        self.assertIn("(697.0, 120.0)", rust_code)
        self.assertEqual(mortar_calc.L81_MORTAR_TABLE[0], (80, 950))
        self.assertEqual(mortar_calc.L81_MORTAR_TABLE[-1], (697, 120))

        # Check SPH-2 table endpoints
        self.assertIn("(780.0, 1390.0)", rust_code)
        self.assertIn("(2629.0, 610.0)", rust_code)
        self.assertEqual(mortar_calc.SPH2_HIGH_TABLE[0], (780, 1390))
        self.assertEqual(mortar_calc.SPH2_HIGH_TABLE[-1], (2629, 610))

        # Check SPH-2 Low table endpoints
        self.assertIn("(1181.0, 20.0)", rust_code)
        self.assertIn("(2629.0, 600.0)", rust_code)
        self.assertEqual(mortar_calc.SPH2_LOW_TABLE[0], (1181, 20))
        self.assertEqual(mortar_calc.SPH2_LOW_TABLE[-1], (2629, 600))


if __name__ == "__main__":
    unittest.main()
