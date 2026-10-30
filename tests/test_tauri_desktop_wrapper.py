import json
import os
import unittest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAURI_DIR = os.path.join(ROOT_DIR, "src-tauri")


class TestTauriDesktopWrapper(unittest.TestCase):
    def test_tauri_scaffold_files_exist(self):
        """Verify all required Tauri v2 build and icon files exist."""
        required = [
            os.path.join(TAURI_DIR, "Cargo.toml"),
            os.path.join(TAURI_DIR, "build.rs"),
            os.path.join(TAURI_DIR, "tauri.conf.json"),
            os.path.join(TAURI_DIR, "capabilities", "default.json"),
            os.path.join(TAURI_DIR, "src", "main.rs"),
            os.path.join(TAURI_DIR, "src", "lib.rs"),
            os.path.join(TAURI_DIR, "icons", "icon.ico"),
            os.path.join(TAURI_DIR, "icons", "icon.png"),
        ]
        for path in required:
            self.assertTrue(os.path.isfile(path), f"Missing required Tauri file: {path}")

    def test_tauri_conf_valid_and_coexistence_safe(self):
        """Verify tauri.conf.json configures WebView2, global Tauri API, and local/remote CSP."""
        conf_path = os.path.join(TAURI_DIR, "tauri.conf.json")
        with open(conf_path, "r", encoding="utf-8") as f:
            conf = json.load(f)

        self.assertEqual(conf["identifier"], "net.tail0908d2.wardogs-mortar-assistant")
        self.assertTrue(conf["app"]["withGlobalTauri"])
        windows = conf["app"]["windows"]
        self.assertGreaterEqual(len(windows), 1)
        self.assertEqual(windows[0]["label"], "main")
        self.assertTrue(windows[0]["alwaysOnTop"])
        csp = conf["app"]["security"]["csp"]
        self.assertIn("127.0.0.1:8765", csp)
        self.assertIn("pve-ubuntu.tail0908d2.ts.net:8099", csp)

    def test_capabilities_acl_least_privilege(self):
        """Verify capabilities/default.json grants global-shortcut, window-state, and click-through permissions."""
        cap_path = os.path.join(TAURI_DIR, "capabilities", "default.json")
        with open(cap_path, "r", encoding="utf-8") as f:
            cap = json.load(f)

        perms = set(cap.get("permissions", []))
        expected = {
            "core:default",
            "core:window:allow-set-always-on-top",
            "core:window:allow-set-ignore-cursor-events",
            "core:window:allow-set-decorations",
            "global-shortcut:allow-register",
            "global-shortcut:allow-unregister",
            "window-state:allow-restore-state",
            "window-state:allow-save-window-state",
            "clipboard-manager:allow-read-text",
        }
        self.assertTrue(expected.issubset(perms))

    def test_rust_lib_hotkeys_and_zero_polling(self):
        """Verify src-tauri/src/lib.rs registers hotkeys, handles click-through, and has zero GPU polling."""
        lib_path = os.path.join(TAURI_DIR, "src", "lib.rs")
        with open(lib_path, "r", encoding="utf-8") as f:
            code = f.read()

        for combo in ("Alt+M", "Alt+R", "Alt+Up", "Alt+Down", "Alt+A", "Alt+O", "Alt+C", "Alt+S"):
            self.assertIn(combo, code, f"Hotkey {combo} missing from lib.rs")

        self.assertIn("set_ignore_cursor_events", code)
        self.assertIn("wardogs-hotkey", code)
        self.assertIn("ensure_local_backend", code)
        self.assertNotIn("nvidia-smi", code.lower())

    def test_index_html_wires_tauri_hotkey_bridge(self):
        """Verify index.html wires initTauriDesktopBridge() and handleTauriHotkey()."""
        html_path = os.path.join(ROOT_DIR, "index.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn("id=\"tauriHudBadge\"", html)
        self.assertIn("function initTauriDesktopBridge()", html)
        self.assertIn("function handleTauriHotkey(", html)
        self.assertIn("wardogs-hotkey", html)
        self.assertIn("initTauriDesktopBridge();", html)


if __name__ == "__main__":
    unittest.main()
