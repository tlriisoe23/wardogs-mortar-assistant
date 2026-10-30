"""
Unit and Invariant Tests for WARDOGS Mortar & Artillery Assistant v3.0 Desktop Evolution (AIS-335).
Verifies:
1. Native Rust RK4 Ballistic Solver (src-tauri/src/mortar_calc.rs) structure and mathematical parity.
2. Multi-Window PIP Recon Scope ('pip-recon') configuration in tauri.conf.json.
3. Native System Tray (TrayIconBuilder) and menu wiring in src-tauri/src/lib.rs.
4. Advanced IPC Primitives: ArrayBuffer zero-serialization Response and Channel streaming.
5. Capabilities ACL least-privilege scoping across multi-window layout.
6. Tanner-Z390 Coexistence Contract (0% background GPU/VRAM/screen polling).
"""

import json
import os
import re
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAURI_DIR = os.path.join(ROOT_DIR, "src-tauri")
SRC_DIR = os.path.join(TAURI_DIR, "src")


class TestTauriV3Evolution(unittest.TestCase):
    def test_v3_rust_mortar_calc_exists_and_complete(self):
        """Verify src-tauri/src/mortar_calc.rs exists with tables, RK4 solver, and pitch compensation."""
        calc_path = os.path.join(SRC_DIR, "mortar_calc.rs")
        self.assertTrue(os.path.isfile(calc_path), f"Missing mortar_calc.rs at {calc_path}")

        with open(calc_path, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("pub const L81_MORTAR_TABLE", code)
        self.assertIn("pub const SPH2_HIGH_TABLE", code)
        self.assertIn("pub const SPH2_LOW_TABLE", code)
        self.assertIn("pub fn sph_height_at_distance", code)
        self.assertIn("pub fn sph_platform_correct_aim", code)
        self.assertIn("pub fn calculate_firing_solution", code)
        self.assertIn("pub struct FiringSolution", code)
        self.assertIn("pub struct TrajectoryStep", code)

    def test_v3_multi_window_pip_recon_config(self):
        """Verify tauri.conf.json defines both 'main' and 'pip-recon' windows with correct properties."""
        conf_path = os.path.join(TAURI_DIR, "tauri.conf.json")
        with open(conf_path, "r", encoding="utf-8") as f:
            conf = json.load(f)

        windows = conf["app"]["windows"]
        labels = [w["label"] for w in windows]
        self.assertIn("main", labels)
        self.assertIn("pip-recon", labels)

        pip_win = next(w for w in windows if w["label"] == "pip-recon")
        self.assertTrue(pip_win["alwaysOnTop"])
        self.assertTrue(pip_win["transparent"])
        self.assertFalse(pip_win["decorations"])
        self.assertGreaterEqual(pip_win["width"], 480)
        self.assertGreaterEqual(pip_win["height"], 320)

    def test_v3_tray_icon_and_menu_wiring(self):
        """Verify TrayIconBuilder, menu items, and event handlers in src/lib.rs."""
        lib_path = os.path.join(SRC_DIR, "lib.rs")
        with open(lib_path, "r", encoding="utf-8") as f:
            code = f.read()

        self.assertIn("TrayIconBuilder", code)
        self.assertIn("MenuBuilder", code)
        self.assertIn("show_hud", code)
        self.assertIn("toggle_pip", code)
        self.assertIn("toggle_click", code)
        self.assertIn("mute_audio", code)
        self.assertIn("quit", code)
        self.assertIn("on_tray_icon_event", code)
        self.assertIn("on_menu_event", code)

    def test_v3_ipc_primitives_wired(self):
        """Verify advanced IPC primitives: ArrayBuffer Response and Channel streaming."""
        lib_path = os.path.join(SRC_DIR, "lib.rs")
        with open(lib_path, "r", encoding="utf-8") as f:
            code = f.read()

        # Zero-serialization raw binary response
        self.assertIn("Response", code)
        self.assertIn("get_dem_heightmap_raw", code)
        self.assertIn("Response::new(", code)

        # High-throughput typed Channel streaming
        self.assertIn("Channel", code)
        self.assertIn("stream_trajectory_channel", code)
        self.assertIn("channel.send(", code)

        # Pure Rust ballistic command
        self.assertIn("calculate_ballistics", code)
        self.assertIn("toggle_pip_recon", code)

    def test_v3_capabilities_acl_covers_pip_and_window_lifecycle(self):
        """Verify capabilities/default.json grants permissions across both main and pip-recon windows."""
        cap_path = os.path.join(TAURI_DIR, "capabilities", "default.json")
        with open(cap_path, "r", encoding="utf-8") as f:
            cap = json.load(f)

        windows = set(cap.get("windows", []))
        self.assertIn("main", windows)
        self.assertIn("pip-recon", windows)

        perms = set(cap.get("permissions", []))
        required = {
            "core:window:allow-create-webview-window",
            "core:window:allow-show",
            "core:window:allow-hide",
            "core:window:allow-set-focus",
            "core:window:allow-set-always-on-top",
            "core:window:allow-set-ignore-cursor-events",
            "global-shortcut:allow-register",
            "window-state:allow-restore-state",
        }
        self.assertTrue(required.issubset(perms), f"Missing permissions: {required - perms}")

    def test_v3_zero_polling_contract_enforced(self):
        """Verify 0% background GPU/VRAM/screen polling contract on Tanner-Z390."""
        for filename in ("lib.rs", "mortar_calc.rs"):
            filepath = os.path.join(SRC_DIR, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("nvidia-smi", content.lower())
            self.assertNotIn("nvml", content.lower())
            self.assertNotIn("std::thread::spawn", content)

    def test_v3_ballistic_table_parity_with_python(self):
        """Verify mathematical parity between Rust mortar_calc.rs and Python mortar_calc.py tables."""
        from mortar_calc import L81_MORTAR_TABLE, SPH2_HIGH_TABLE, SPH2_LOW_TABLE

        calc_path = os.path.join(SRC_DIR, "mortar_calc.rs")
        with open(calc_path, "r", encoding="utf-8") as f:
            rust_code = f.read()

        # Check sample coordinates from L81 Mortar Table
        for dist, mils in [L81_MORTAR_TABLE[0], L81_MORTAR_TABLE[10], L81_MORTAR_TABLE[-1]]:
            pattern = rf"\({dist:.1f},\s*{mils:.1f}\)"
            self.assertTrue(
                re.search(pattern, rust_code),
                f"L81 Table point ({dist}, {mils}) missing or mismatched in Rust solver",
            )

        # Check sample coordinates from SPH-2 High Table
        for dist, mils in [SPH2_HIGH_TABLE[0], SPH2_HIGH_TABLE[20], SPH2_HIGH_TABLE[-1]]:
            pattern = rf"\({dist:.1f},\s*{mils:.1f}\)"
            self.assertTrue(
                re.search(pattern, rust_code),
                f"SPH-2 High Table point ({dist}, {mils}) missing or mismatched in Rust solver",
            )

        # Check sample coordinates from SPH-2 Low Table
        for dist, mils in [SPH2_LOW_TABLE[0], SPH2_LOW_TABLE[15], SPH2_LOW_TABLE[-1]]:
            pattern = rf"\({dist:.1f},\s*{mils:.1f}\)"
            self.assertTrue(
                re.search(pattern, rust_code),
                f"SPH-2 Low Table point ({dist}, {mils}) missing or mismatched in Rust solver",
            )


if __name__ == "__main__":
    unittest.main()
