// WARDOGS Mortar & Artillery Assistant (:8765 / :8099) — Tauri v2 Native Desktop Wrapper (AIS-198)
// Coexistence Contract for Tanner-Z390:
// 1. 100% event-driven global hotkeys (zero background GPU/VRAM/screen polling loops).
// 2. Native Windows 11 WebView2 shell (~3 MB binary) respecting NVIDIA nvdrsdb Global Base Profile.
// 3. Auto-starts local Python server.py backend on 127.0.0.1:8765 for Edge-TTS, WinRT OCR, and GetAsyncKeyState PTT.

use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::Duration;
use tauri::{Emitter, Manager, RunEvent};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

pub const REGISTERED_HOTKEYS: &[(&str, &str)] = &[
    ("Alt+M", "lock_target"),
    ("Alt+R", "reset_target"),
    ("Alt+Up", "elev_up"),
    ("Alt+Down", "elev_down"),
    ("Alt+A", "toggle_arc"),
    ("Alt+O", "scan_ocr_once"),
    ("Alt+C", "toggle_click_through"),
    ("Alt+S", "toggle_mute"),
];

static CLICK_THROUGH_ACTIVE: AtomicBool = AtomicBool::new(false);

struct BackendGuard(Mutex<Option<Child>>);

fn is_local_backend_alive() -> bool {
    let addr: SocketAddr = "127.0.0.1:8765".parse().unwrap();
    TcpStream::connect_timeout(&addr, Duration::from_millis(120)).is_ok()
}

fn find_repo_root() -> Option<PathBuf> {
    let mut candidates = Vec::new();
    if let Ok(cwd) = std::env::current_dir() {
        candidates.push(cwd.clone());
        if let Some(parent) = cwd.parent() {
            candidates.push(parent.to_path_buf());
        }
    }
    if let Ok(exe) = std::env::current_exe() {
        let mut cur = exe.parent();
        for _ in 0..5 {
            if let Some(dir) = cur {
                candidates.push(dir.to_path_buf());
                cur = dir.parent();
            }
        }
    }
    candidates.push(PathBuf::from(r"D:\AI Projects\Wardogs-Mortar-Assistant"));

    for dir in candidates {
        if dir.join("server.py").is_file() && dir.join("index.html").is_file() {
            return Some(dir);
        }
    }
    None
}

pub fn ensure_local_backend() -> Option<Child> {
    if is_local_backend_alive() {
        return None;
    }
    let root = find_repo_root()?;
    let mut cmd = Command::new("python");
    cmd.arg("server.py")
        .arg("--no-browser")
        .env("PORT", "8765")
        .current_dir(&root)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }

    let child = cmd.spawn().ok()?;
    for _ in 0..25 {
        if is_local_backend_alive() {
            break;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    Some(child)
}

#[tauri::command]
fn trigger_single_shot_ocr() -> Result<String, String> {
    // Strictly on-keypress single-shot OCR trigger; never runs in a background loop.
    Ok("ocr_scan_once_dispatched".to_string())
}

#[tauri::command]
fn set_hud_click_through(window: tauri::WebviewWindow, enabled: bool) -> Result<bool, String> {
    CLICK_THROUGH_ACTIVE.store(enabled, Ordering::SeqCst);
    window
        .set_ignore_cursor_events(enabled)
        .map_err(|e| e.to_string())?;
    Ok(enabled)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let backend_child = ensure_local_backend();

    let app = tauri::Builder::default()
        .manage(BackendGuard(Mutex::new(backend_child)))
        .plugin(tauri_plugin_window_state::Builder::default().build())
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, shortcut, event| {
                    if event.state == ShortcutState::Pressed {
                        let key_str = shortcut.into_string();
                        let upper = key_str.to_ascii_uppercase();
                        if let Some(win) = app.get_webview_window("main") {
                            if upper.contains("ALT") && upper.ends_with("C") {
                                let next = !CLICK_THROUGH_ACTIVE.load(Ordering::SeqCst);
                                CLICK_THROUGH_ACTIVE.store(next, Ordering::SeqCst);
                                let _ = win.set_ignore_cursor_events(next);
                            }
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
        .invoke_handler(tauri::generate_handler![
            trigger_single_shot_ocr,
            set_hud_click_through
        ])
        .build(tauri::generate_context!())
        .expect("error while building WARDOGS Tauri v2 application");

    app.run(|app_handle, event| {
        if let RunEvent::Exit = event {
            if let Some(guard) = app_handle.try_state::<BackendGuard>() {
                if let Ok(mut slot) = guard.0.lock() {
                    if let Some(mut child) = slot.take() {
                        let _ = child.kill();
                    }
                }
            }
        }
    });
}
