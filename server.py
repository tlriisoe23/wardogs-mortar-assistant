"""
Local HTTP Server for WARDOGS Ballistic Audio Assistant.
Includes:
- Next-Level Neural AI TTS endpoint (/api/tts) using edge-tts
- Background Screen OCR Watcher (/api/ocr/status, /api/ocr/toggle)
- Native Windows In-Game Global Push-To-Talk Hook (/api/ptt/status, /api/ptt/config, /api/ptt/bind)
  using ctypes.windll.user32.GetAsyncKeyState so players can talk to the assistant inside full-screen
  WARDOGS without ever clicking out or Alt-Tabbing.
"""

import http.server
import socketserver
import urllib.parse
import webbrowser
import threading
import asyncio
import ctypes
import time
import json
import os
import sys

from ocr_sniff import GLOBAL_OCR_WATCHER, capture_and_scan_entries

PORT = int(os.environ.get("PORT", "8765"))
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# In-memory audio cache for instant sub-millisecond replays
TTS_CACHE = {}

# Human-readable names for Windows Virtual-Key (VK) codes
VK_NAMES = {
    0x04: "Middle Mouse (MMB)",
    0x05: "Mouse 4 (Side Back)",
    0x06: "Mouse 5 (Side Forward)",
    0x08: "Backspace",
    0x09: "Tab",
    0x14: "Caps Lock",
    0x20: "Spacebar",
    0x2D: "Insert",
    0x2E: "Delete",
    0x42: "B Key",
    0x43: "C Key",
    0x47: "G Key",
    0x48: "H Key",
    0x4E: "N Key",
    0x54: "T Key",
    0x56: "V Key",
    0x58: "X Key",
    0x5A: "Z Key",
    0x60: "Numpad 0",
    0x61: "Numpad 1",
    0x62: "Numpad 2",
    0x63: "Numpad 3",
    0x64: "Numpad 4",
    0x65: "Numpad 5",
    0x66: "Numpad 6",
    0x67: "Numpad 7",
    0x68: "Numpad 8",
    0x69: "Numpad 9",
    0x6A: "Numpad *",
    0x6B: "Numpad +",
    0x6D: "Numpad -",
    0x70: "F1",
    0x71: "F2",
    0x72: "F3",
    0x73: "F4",
    0x74: "F5",
    0x75: "F6",
    0x76: "F7",
    0x77: "F8",
    0x78: "F9",
    0x79: "F10",
    0x7A: "F11",
    0x7B: "F12",
    0xA0: "Left Shift",
    0xA1: "Right Shift",
    0xA2: "Left Ctrl",
    0xA3: "Right Ctrl",
    0xA4: "Left Alt",
    0xA5: "Right Alt",
    0xC0: "Tilde (`)",
    0xDB: "Left Bracket [",
    0xDD: "Right Bracket ]",
    0xDC: "Backslash \\",
}

def get_vk_name(vk: int) -> str:
    if vk in VK_NAMES:
        return VK_NAMES[vk]
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        return f"{chr(vk)} Key"
    return f"Key 0x{vk:02X}"


class GlobalPTTWatcher:
    """
    Polls Windows GetAsyncKeyState at 50Hz in a background daemon thread so the browser
    can detect global hardware Push-To-Talk presses while inside full-screen WARDOGS.
    """
    def __init__(self):
        self.enabled = False
        self.vk = 0x05  # Default: Mouse 4 (Thumb Back button)
        self.pressed = False
        self.last_press_ts = 0.0
        self.last_release_ts = 0.0
        self.binding_mode = False
        self.bind_deadline = 0.0
        self._user32 = ctypes.windll.user32 if os.name == 'nt' else None
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _is_vk_down(self, vk: int) -> bool:
        if not self._user32:
            return False
        return bool(self._user32.GetAsyncKeyState(vk) & 0x8000)

    def start_bind_capture(self, timeout_sec: float = 6.0):
        self.binding_mode = True
        self.bind_deadline = time.time() + timeout_sec

    def _loop(self):
        # Candidate VKs for "Press any key/mouse button to bind" (excludes Left/Right mouse 0x01/0x02)
        bind_candidates = (
            [0x04, 0x05, 0x06, 0x08, 0x09, 0x14, 0x20, 0x2D, 0x2E, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0xC0, 0xDB, 0xDD, 0xDC]
            + list(range(0x30, 0x5B))
            + list(range(0x60, 0x7C))
        )
        while True:
            now = time.time()
            if self.binding_mode:
                if now > self.bind_deadline:
                    self.binding_mode = False
                else:
                    for cand in bind_candidates:
                        if self._is_vk_down(cand):
                            self.vk = cand
                            self.binding_mode = False
                            break

            if self.enabled:
                is_down = self._is_vk_down(self.vk)
                if is_down and not self.pressed:
                    self.last_press_ts = now
                elif not is_down and self.pressed:
                    self.last_release_ts = now
                self.pressed = is_down
            else:
                self.pressed = False

            time.sleep(0.02)

    def get_status(self) -> dict:
        return {
            "enabled": self.enabled,
            "vk": self.vk,
            "key_name": get_vk_name(self.vk),
            "pressed": self.pressed,
            "binding_mode": self.binding_mode,
            "last_press_ts": self.last_press_ts,
            "last_release_ts": self.last_release_ts,
        }


GLOBAL_PTT_WATCHER = GlobalPTTWatcher()


async def generate_neural_tts(text: str, voice: str) -> bytes:
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice, rate="+8%")
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        if len(audio_data) > 256:
            return audio_data
    except Exception:
        pass
    try:
        import io
        from gtts import gTTS
        buf = io.BytesIO()
        gTTS(text=text, lang="en", tld="us").write_to_fp(buf)
        data = buf.getvalue()
        if len(data) > 256:
            return data
    except Exception:
        pass
    import io, math, struct, wave
    buf = io.BytesIO()
    sample_rate = 22050
    n_samples = int(sample_rate * 0.45)
    frames = bytearray()
    for i in range(n_samples):
        t = i / sample_rate
        freq = 880.0 if t < 0.18 else (1174.66 if t < 0.36 else 0.0)
        env = math.sin(math.pi * (t / 0.18)) if t < 0.18 else (math.sin(math.pi * ((t - 0.18) / 0.18)) if t < 0.36 else 0.0)
        sample = int(12000 * env * math.sin(2.0 * math.pi * freq * t)) if freq > 0 else 0
        frames += struct.pack("<h", max(-32767, min(32767, sample)))
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))
    return buf.getvalue()


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def log_message(self, format, *args):
        # Silence high-frequency background status polls to keep terminal output clean
        if len(args) > 0 and isinstance(args[0], str):
            if '/api/ptt/status' in args[0] or '/api/ocr/status' in args[0]:
                return
        super().log_message(format, *args)

    def _send_json(self, data: dict):
        payload = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path in ('/api/health', '/health'):
            self._send_json({
                "ok": True,
                "status": "healthy",
                "service": "wardogs-mortar-assistant",
                "port": PORT,
                "weapons": ["L81 Mortar", "SPH-2 Self-Propelled Howitzer"],
                "maps": ["Bakurani", "Ozeti", "Zestafona"],
            })
            return

        # Global In-Game Push-To-Talk (PTT) endpoints
        if parsed.path == '/api/ptt/status':
            self._send_json(GLOBAL_PTT_WATCHER.get_status())
            return

        if parsed.path == '/api/ptt/config':
            params = urllib.parse.parse_qs(parsed.query)
            if 'enabled' in params:
                val = params['enabled'][0].strip().lower()
                GLOBAL_PTT_WATCHER.enabled = val in ('1', 'true', 'on', 'yes')
            if 'vk' in params:
                try:
                    vk_val = int(params['vk'][0], 0)
                    if 0x03 <= vk_val <= 0xFE:
                        GLOBAL_PTT_WATCHER.vk = vk_val
                except ValueError:
                    pass
            self._send_json(GLOBAL_PTT_WATCHER.get_status())
            return

        if parsed.path == '/api/ptt/bind':
            GLOBAL_PTT_WATCHER.start_bind_capture(timeout_sec=6.0)
            self._send_json(GLOBAL_PTT_WATCHER.get_status())
            return

        # Check for OCR API endpoints
        if parsed.path == '/api/ocr/status':
            self._send_json(GLOBAL_OCR_WATCHER.get_status())
            return

        if parsed.path == '/api/ocr/scan_once':
            entries = capture_and_scan_entries()
            last_entry = entries[-1] if entries else None
            coords = (last_entry["x"], last_entry["y"]) if last_entry else None
            if last_entry:
                GLOBAL_OCR_WATCHER._record_entry(last_entry, source="ocr_snapshot")
            self._send_json({
                "found": bool(coords),
                "coords": coords,
                "role": last_entry["role"] if last_entry else None,
                "raw_line": last_entry["raw_line"] if last_entry else "",
                "entries": entries,
                "has_winocr": GLOBAL_OCR_WATCHER.get_status().get("has_winocr", False)
            })
            return

        if parsed.path == '/api/ocr/toggle':
            params = urllib.parse.parse_qs(parsed.query)
            state = params.get('state', [''])[0].strip().lower()
            if state == 'on' or state == 'true':
                GLOBAL_OCR_WATCHER.start()
            elif state == 'off' or state == 'false':
                GLOBAL_OCR_WATCHER.stop()
            else:
                if GLOBAL_OCR_WATCHER.is_running:
                    GLOBAL_OCR_WATCHER.stop()
                else:
                    GLOBAL_OCR_WATCHER.start()
            self._send_json(GLOBAL_OCR_WATCHER.get_status())
            return

        # Check for Blind Fire Hotspots Database endpoint
        if parsed.path == '/api/targets':
            targets_file = os.path.join(DIRECTORY, 'data', 'targets.json')
            if os.path.exists(targets_file):
                with open(targets_file, 'rb') as f:
                    payload = f.read()
            else:
                payload = b"[]"
            try:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(payload)
            except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
                pass
            return

        # Check for Neural AI TTS API endpoint
        if parsed.path == '/api/tts':
            params = urllib.parse.parse_qs(parsed.query)
            text = params.get('text', [''])[0].strip()
            voice = params.get('voice', ['en-US-ChristopherNeural'])[0].strip()

            if not text:
                self.send_error(400, "Missing 'text' query parameter.")
                return

            cache_key = f"{voice}:{text}"
            if cache_key in TTS_CACHE:
                audio_bytes = TTS_CACHE[cache_key]
            else:
                try:
                    audio_bytes = asyncio.run(generate_neural_tts(text, voice))
                    if len(TTS_CACHE) < 500:
                        TTS_CACHE[cache_key] = audio_bytes
                except Exception as e:
                    print(f"[TTS Error] {e}")
                    self.send_error(500, f"TTS Generation Error: {e}")
                    return

            try:
                self.send_response(200)
                self.send_header('Content-Type', 'audio/mpeg')
                self.send_header('Content-Length', str(len(audio_bytes)))
                self.end_headers()
                self.wfile.write(audio_bytes)
            except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
                pass
            return

        try:
            super().do_GET()
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass

    def do_HEAD(self):
        try:
            self.do_GET()
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()


class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == '__main__':
    os.chdir(DIRECTORY)

    active_port = PORT
    httpd = None
    for p in range(PORT, PORT + 20):
        try:
            httpd = ThreadedHTTPServer(("", p), Handler)
            active_port = p
            break
        except OSError:
            continue

    if not httpd:
        print(f"Could not bind to any port between {PORT} and {PORT+20}")
        sys.exit(1)

    with httpd:
        url = f"http://localhost:{active_port}/index.html"
        print("=" * 65)
        print("    WARDOGS BALLISTIC AUDIO ASSISTANT // HIGH-DEF SERVER")
        print("=" * 65)
        print(f" Serving live at: {url}")
        print(" Next-Gen Neural AI Speech Engine Active (/api/tts).")
        print(" Native Windows In-Game Global PTT Active (/api/ptt/*).")
        print(" Press CTRL+C to terminate.")
        print("=" * 65)

        if "--no-browser" not in sys.argv:
            try:
                webbrowser.open(url)
            except Exception:
                pass

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")
            httpd.server_close()
            sys.exit(0)
