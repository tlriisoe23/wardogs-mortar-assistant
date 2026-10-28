// WARDOGS Mortar & Artillery Assistant (:8099) — Tauri v2 Native Desktop Wrapper (AIS-198)
// Coexistence Contract for Tanner-Z390:
// 1. 100% event-driven global hotkeys (zero background GPU/VRAM/screen polling loops).
// 2. Native Windows 11 WebView2 shell (~3 MB binary) respecting NVIDIA nvdrsdb Global Base Profile.

use tauri::{Emitter, Manager};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

pub const REGISTERED_HOTKEYS: &[(&str, &str)] = &[
    ("Alt+M", "lock_target"),
    ("Alt+R", "reset_target"),
    ("Alt+Up", "elev_up"),
    ("Alt+Down", "elev_down"),
    ("Alt+A", "toggle_arc"),
    ("Alt+O", "scan_ocr_once"),
    ("Alt+C", "toggle_click_through"),
];

#[tauri::command]
fn trigger_single_shot_ocr() -> Result<String, String> {
    // Strictly on-keypress single-shot OCR trigger; never runs in a background loop.
    Ok("ocr_scan_once_dispatched".to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, shortcut, event| {
                    if event.state == ShortcutState::Pressed {
                        let key_str = shortcut.into_string();
                        if let Some(win) = app.get_webview_window("main") {
                            let _ = win.emit("wardogs-hotkey", key_str);
                        }
                    }
                })
                .build(),
        )
        .setup(|app| {
            let gs = app.global_shortcut();
            for (combo, _action) in REGISTERED_HOTKEYS {
                let _ = gs.register(*combo);
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![trigger_single_shot_ocr])
        .run(tauri::generate_context!())
        .expect("error while running WARDOGS Tauri v2 application");
}
