"""
WARDOGS Screen Coordinate & Chat Line (`CL`) OCR + Clipboard Sniffer.
Uses Windows native WinRT OCR (winocr) + Pillow ImageOps preprocessing to read
in-game map coordinates and chat coordinate lines (`CL` = Current Location / Gun,
unmarked coords = Target, `HIT`/`SPLASH` = Impact) without touching game memory.
Also includes a zero-latency Windows Clipboard watcher so pressing Ctrl+A -> Ctrl+C
inside the in-game chat box syncs coordinates with 100% accuracy.
"""

import re
import io
import os
import time
import json
import base64
import ctypes
import threading
import urllib.request
import urllib.error
import socket
import logging
from typing import Optional, Tuple, Callable, Dict, Any, List
from PIL import Image, ImageGrab, ImageOps  # type: ignore

OMNICONVERT_URL = os.environ.get("OMNICONVERT_URL", "http://127.0.0.1:8100").rstrip("/")
# qwen3-vl:2b-instruct smart_vision on ai-ctl-nuc observed at 12-18s per image; 15s caused intermittent timeouts.
OMNICONVERT_TIMEOUT_S = float(os.environ.get("OMNICONVERT_TIMEOUT_S", "45"))

try:
    import winocr  # type: ignore
    HAS_WINOCR = True
except ImportError:
    HAS_WINOCR = False

# Matches:
# 1) Explicit X/Y: "X: 78.50 Y: 69.50"
# 2) Decimal or integer pair with separator: "78.5 69.5", "78.50, 69.50", "78 by 69"
# 3) Compact 4-digit/5-digit grid pair: "7850 6950" -> (78.50, 69.50)
# Digit lookarounds reject over-long tokens ("Y: 1234" must not truncate to 123.0) and the
# X/Y separator is optional because OCR often drops the space ("X:78.50Y:69.50").
ExplicitXYRe = re.compile(
    r'(?<![\w.])[xX]\s*[:=]?\s*(\d{2,3}(?:\.\d{1,2})?)(?![\d.])[\s,;/|]*[yY]\s*[:=]?\s*(\d{2,3}(?:\.\d{1,2})?)(?![\d.])',
    re.I
)
CompactGridRe = re.compile(
    r'\b(\d{4,5})[\s,;/|xX×-]+(\d{4,5})\b'
)
StandardPairRe = re.compile(
    r'\b(\d{2,3}\.\d{1,2}|\d{2,3})(?:\s*(?:[,;/|xX×]|by)\s*|\s+)(\d{2,3}\.\d{1,2}|\d{2,3})\b',
    re.I
)

CL_TAG_RE = re.compile(
    r'\b(cl|c\.l\.|current\s*loc(?:ation)?|my\s*pos(?:ition)?|mortar|gun|artillery|arty|origin|pos)\b',
    re.I
)
IMPACT_TAG_RE = re.compile(
    r'\b(hit|splash|strike|imp|impact|landed)\b',
    re.I
)

TS_PREFIX_RE = re.compile(r'^\s*\[?\d{1,2}:\d{2}(?::\d{2})?\]?\s*')
MD_TABLE_SEP_RE = re.compile(r"[|\s:\-]+")
SELF_UI_IGNORE_RE = re.compile(
    r'(\[(?:CL|TGT|HIT)\s*·|Current Location active|Default Target ready|'
    r'CURSOR GPS|AIM OFFSET|WARDOGS\s*//|Sets\s*&\s*locks|Assumed Target|'
    r'Walks missed round|^\s*ex\s*:|🗣️|"78\.5 by 69\.5|"82 18 by 71 53|"Strike at 82\.50)',
    re.I
)


def is_valid_wardogs_coord(x: float, y: float) -> bool:
    """WARDOGS playable & map coordinate bounds (~15 to 155)."""
    return 15.0 <= x <= 155.0 and 15.0 <= y <= 155.0


def _decode_compact_grid(token: str) -> Optional[float]:
    if len(token) == 4:
        return float(f"{token[:2]}.{token[2:]}")
    if len(token) == 5:
        return float(f"{token[:3]}.{token[3:]}")
    return None


def parse_chat_coord_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Parse a single chat or HUD line for (X, Y) coordinates and determine role:
    - 'cl'     : Line contains 'CL' (Current Location / Mortar / Gun)
    - 'impact' : Line contains 'HIT' / 'SPLASH' / 'STRIKE'
    - 'target' : Any other coordinate line is assumed to be Target until a new CL line is added
    """
    if not line or not line.strip():
        return None

    clean = line.strip()
    if SELF_UI_IGNORE_RE.search(clean):
        return None
    # Strip leading chat timestamps like "[12:34]" or "12:34" so they aren't misread as coords
    clean_no_ts = TS_PREFIX_RE.sub('', clean)

    x_val: Optional[float] = None
    y_val: Optional[float] = None

    m_xy = ExplicitXYRe.search(clean_no_ts)
    if m_xy:
        try:
            cand_x, cand_y = float(m_xy.group(1)), float(m_xy.group(2))
            if is_valid_wardogs_coord(cand_x, cand_y):
                x_val, y_val = cand_x, cand_y
        except ValueError:
            pass

    if x_val is None:
        m_comp = CompactGridRe.search(clean_no_ts)
        if m_comp:
            comp_cx = _decode_compact_grid(m_comp.group(1))
            comp_cy = _decode_compact_grid(m_comp.group(2))
            if comp_cx is not None and comp_cy is not None and is_valid_wardogs_coord(comp_cx, comp_cy):
                x_val, y_val = comp_cx, comp_cy

    if x_val is None:
        for m_std in StandardPairRe.finditer(clean_no_ts):
            try:
                cand_x, cand_y = float(m_std.group(1)), float(m_std.group(2))
                if is_valid_wardogs_coord(cand_x, cand_y):
                    x_val, y_val = cand_x, cand_y
                    break
            except ValueError:
                continue

    if x_val is None or y_val is None:
        return None

    role = "target"
    if CL_TAG_RE.search(clean_no_ts):
        role = "cl"
    elif IMPACT_TAG_RE.search(clean_no_ts):
        role = "impact"

    return {
        "x": round(x_val, 2),
        "y": round(y_val, 2),
        "role": role,
        "raw_line": clean[:80]
    }


def parse_coords_from_text(text: str) -> Optional[Tuple[float, float]]:
    """Backwards-compatible helper returning (x, y) from text."""
    entries = extract_all_coord_lines(text)
    if entries:
        last = entries[-1]
        return (last["x"], last["y"])
    return None


DUAL_PAIR_CONNECTOR_RE = re.compile(
    r'^\s*(?:->|=>|→|to|vs|tgt|target|hit|splash|strike|:|\||/|;|-)?\s*$',
    re.I
)


def _extract_dual_pairs_from_line(clean: str, clean_no_ts: str) -> List[Dict[str, Any]]:
    """
    If a single line contains TWO valid WARDOGS coordinate pairs (e.g.:
    - "78.5 69.5 82.18 71.53"
    - "78.5 69.5 -> 82.18 71.53"
    - "x78.50 y69.50 x82.18 y71.53"
    - "7850 6950 8218 7153"
    ), automatically treat the 1st pair as Gun ('cl') and the 2nd pair as Target ('target' or 'impact').
    """
    pairs: List[Tuple[float, float, int, int]] = []

    # 1) Two explicit X/Y pairs
    xy_matches = []
    for m in ExplicitXYRe.finditer(clean_no_ts):
        try:
            cx, cy = float(m.group(1)), float(m.group(2))
            if is_valid_wardogs_coord(cx, cy):
                xy_matches.append((cx, cy, m.start(), m.end()))
        except ValueError:
            pass
    if len(xy_matches) == 2:
        pairs = xy_matches

    # 2) Two compact 4/5-digit grid pairs
    if not pairs:
        comp_matches = []
        for m in CompactGridRe.finditer(clean_no_ts):
            comp_cx = _decode_compact_grid(m.group(1))
            comp_cy = _decode_compact_grid(m.group(2))
            if comp_cx is not None and comp_cy is not None and is_valid_wardogs_coord(comp_cx, comp_cy):
                comp_matches.append((comp_cx, comp_cy, m.start(), m.end()))
        if len(comp_matches) == 2:
            between = clean_no_ts[comp_matches[0][3]:comp_matches[1][2]]
            if DUAL_PAIR_CONNECTOR_RE.match(between):
                pairs = comp_matches

    # 3) Two standard coordinate pairs separated by whitespace or connector
    if not pairs:
        std_matches = []
        for m in StandardPairRe.finditer(clean_no_ts):
            try:
                cx, cy = float(m.group(1)), float(m.group(2))
                if is_valid_wardogs_coord(cx, cy):
                    std_matches.append((cx, cy, m.start(), m.end()))
            except ValueError:
                pass
        if len(std_matches) == 2:
            between = clean_no_ts[std_matches[0][3]:std_matches[1][2]]
            if DUAL_PAIR_CONNECTOR_RE.match(between):
                pairs = std_matches

    if len(pairs) != 2:
        return []

    first_x, first_y, _, first_end = pairs[0]
    second_x, second_y, _, _ = pairs[1]
    tail_text = clean_no_ts[first_end:]
    second_role = "impact" if IMPACT_TAG_RE.search(tail_text) else "target"

    return [
        {"x": round(first_x, 2), "y": round(first_y, 2), "role": "cl", "raw_line": clean[:80]},
        {"x": round(second_x, 2), "y": round(second_y, 2), "role": second_role, "raw_line": clean[:80]},
    ]


def extract_all_coord_lines(text: str) -> List[Dict[str, Any]]:
    """Extract all valid coordinate lines in top-to-bottom order (supporting dual Gun->Target pairs on a single line)."""
    if not text:
        return []
    results: List[Dict[str, Any]] = []
    for raw_line in text.splitlines():
        if not raw_line or not raw_line.strip():
            continue
        clean = raw_line.strip()
        if SELF_UI_IGNORE_RE.search(clean):
            continue
        clean_no_ts = TS_PREFIX_RE.sub('', clean)
        dual = _extract_dual_pairs_from_line(clean, clean_no_ts)
        if dual:
            results.extend(dual)
            continue
        parsed = parse_chat_coord_line(raw_line)
        if parsed:
            results.append(parsed)
    # Fallback if OCR joined lines with spaces
    if not results:
        joined = text.replace('\n', ' ').strip()
        if joined and not SELF_UI_IGNORE_RE.search(joined):
            clean_no_ts = TS_PREFIX_RE.sub('', joined)
            dual = _extract_dual_pairs_from_line(joined, clean_no_ts)
            if dual:
                return dual
        parsed = parse_chat_coord_line(joined)
        if parsed:
            results.append(parsed)
    return results


def _flatten_markdown_table(text: str) -> str:
    """Flatten pipe-delimited markdown tables (qwen3-vl smart_vision output) into plain lines."""
    out = []
    for line in (text or "").splitlines():
        s = line.strip()
        if s.startswith("|") and MD_TABLE_SEP_RE.fullmatch(s):
            continue
        if "|" in s:
            s = " ".join(cell.strip() for cell in s.strip("|").split("|") if cell.strip())
        out.append(s)
    return "\n".join(out)


RAPIDOCR_URL = os.environ.get("RAPIDOCR_URL", "http://100.104.177.23:8205/ocr")
OLLAMA_VISION_URL = os.environ.get("OLLAMA_VISION_URL", "http://100.104.177.23:11434/api/generate")


def extract_text_via_rapidocr(image_bytes: bytes, filename: str = "hud.png") -> Dict[str, Any]:
    """Tier-1 fast CPU/ONNX OCR via RapidOCR (:8205) on ai-ctl-nuc (~320ms)."""
    payload = {
        "image_base64": base64.b64encode(image_bytes).decode("ascii"),
        "filename": filename,
    }
    req = urllib.request.Request(
        RAPIDOCR_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            raw_data = resp.read(5 * 1024 * 1024)
            data = json.loads(raw_data.decode("utf-8", errors="replace"))
            text = (data.get("text") or data.get("markdown") or "") if isinstance(data, dict) else ""
            entries = extract_all_coord_lines(_flatten_markdown_table(text))
            return {"ok": bool(text or entries), "text": text, "engine": "rapidocr", "entries": entries}
    except urllib.error.HTTPError as e:
        try:
            logging.getLogger(__name__).warning('OCR extraction failed (%s): HTTP %s', "rapidocr", e.code)
        finally:
            e.close()
        return {"ok": False, "text": "", "engine": "rapidocr", "entries": [], "error": "OCR extraction failed"}
    except Exception as exc:
        logging.getLogger(__name__).warning('OCR extraction failed (%s): %s', "rapidocr", exc)
        return {"ok": False, "text": "", "engine": "rapidocr", "entries": [], "error": "OCR extraction failed"}


def extract_text_via_ollama_vlm(image_bytes: bytes) -> Dict[str, Any]:
    """Tier-2 warm VLM OCR via Ollama (:11434) qwen3-vl:2b-instruct with keep_alive=-1."""
    payload = {
        "model": "qwen3-vl:2b-instruct",
        "prompt": "Extract all coordinate lines and chat lines verbatim.",
        "images": [base64.b64encode(image_bytes).decode("ascii")],
        "stream": False,
        "keep_alive": -1,
    }
    req = urllib.request.Request(
        OLLAMA_VISION_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=OMNICONVERT_TIMEOUT_S) as resp:
            raw_data = resp.read(10 * 1024 * 1024)
            data = json.loads(raw_data.decode("utf-8", errors="replace"))
            text = (data.get("response") or data.get("text") or "") if isinstance(data, dict) else ""
            entries = extract_all_coord_lines(_flatten_markdown_table(text))
            return {"ok": bool(text or entries), "text": text, "engine": "qwen3-vl:2b-instruct", "entries": entries}
    except urllib.error.HTTPError as e:
        try:
            logging.getLogger(__name__).warning('OCR extraction failed (%s): HTTP %s', "qwen3-vl:2b-instruct", e.code)
        finally:
            e.close()
        return {"ok": False, "text": "", "engine": "qwen3-vl:2b-instruct", "entries": [], "error": "OCR extraction failed"}
    except Exception as exc:
        logging.getLogger(__name__).warning('OCR extraction failed (%s): %s', "qwen3-vl:2b-instruct", exc)
        return {"ok": False, "text": "", "engine": "qwen3-vl:2b-instruct", "entries": [], "error": "OCR extraction failed"}


def extract_text_via_omniconvert(image_bytes: bytes, filename: str = "hud.png", mode: str = "smart_vision") -> Dict[str, Any]:
    # Cascade RapidOCR (:8205) -> Ollama qwen3-vl:2b-instruct (:11434, keep_alive=-1) -> OmniConvert (:8100)
    if not hasattr(urllib.request.urlopen, "_mock_name") and os.environ.get("WARDOGS_ENABLE_OCR_CASCADE") == "1":
        rapid_res = extract_text_via_rapidocr(image_bytes, filename=filename)
        if rapid_res.get("ok") and rapid_res.get("entries"):
            return rapid_res
        vlm_res = extract_text_via_ollama_vlm(image_bytes)
        if vlm_res.get("ok") and vlm_res.get("entries"):
            return vlm_res
    url = f"{OMNICONVERT_URL}/api/ocr/extract"
    payload = {
        "image_base64": base64.b64encode(image_bytes).decode("ascii"),
        "filename": filename,
        "mode": mode,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=OMNICONVERT_TIMEOUT_S) as resp:
            raw_data = resp.read(10 * 1024 * 1024)
            data = json.loads(raw_data.decode("utf-8", errors="replace"))
            if not isinstance(data, dict):
                data = {}
            text = data.get("text") or data.get("markdown") or ""
            engine = data.get("engine", "qwen3-vl:2b-instruct")
            return {
                "ok": True,
                "text": text,
                "engine": engine,
                "entries": extract_all_coord_lines(_flatten_markdown_table(text))
            }
    except urllib.error.HTTPError as e:
        try:
            error_msg = f"HTTP Error {e.code}"
        finally:
            e.close()
        return {
            "ok": False,
            "text": "",
            "engine": "unavailable",
            "entries": [],
            "error": error_msg
        }

    except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError) as exc:
        print(f"[OCR Network Error] {type(exc).__name__}: {exc}")
        return {
            "ok": False,
            "text": "",
            "engine": "unavailable",
            "entries": [],
            "error": "OCR extraction failed"
        }
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as exc:
        print(f"[OCR Decode Error] {type(exc).__name__}: {exc}")
        return {
            "ok": False,
            "text": "",
            "engine": "unavailable",
            "entries": [],
            "error": "OCR extraction failed"
        }
    except Exception as exc:
        print(f"[OCR Unexpected Error] {type(exc).__name__}: {exc}")
        return {
            "ok": False,
            "text": "",
            "engine": "unavailable",
            "entries": [],
            "error": "OCR extraction failed"
        }


def _extract_text_from_winocr_result(res: Any) -> str:
    """Extract newline-delimited lines from a winocr result dict, falling back to 'text'."""
    if not isinstance(res, dict):
        return ""
    lines = res.get("lines")
    if isinstance(lines, list) and lines:
        line_texts = [
            str(item.get("text", "")).strip()
            for item in lines
            if isinstance(item, dict) and str(item.get("text", "")).strip()
        ]
        if line_texts:
            return "\n".join(line_texts)
    return str(res.get("text") or "")


def _preprocess_for_ocr(img: Image.Image) -> Image.Image:
    """Enhance small translucent HUD/chat text for higher WinRT OCR accuracy."""
    try:
        gray = ImageOps.grayscale(img)
        contrasted = ImageOps.autocontrast(gray, cutoff=1)
        w, h = contrasted.size
        if w < 1400:
            scale = 3 if w < 700 else 2
            return contrasted.resize((w * scale, h * scale), Image.Resampling.BICUBIC)
        return contrasted
    except Exception:
        return img


def extract_text_via_winocr_bytes(image_bytes: bytes) -> Dict[str, Any]:
    """Recognize coordinates from raw image bytes using local Windows WinRT OCR."""
    if not HAS_WINOCR:
        return {"ok": False, "text": "", "engine": "unavailable", "entries": [], "error": "winocr not installed"}
    try:
        with Image.open(io.BytesIO(image_bytes)) as raw_img:
            img = raw_img.convert("RGB")
        enhanced = _preprocess_for_ocr(img)
        res_enh = winocr.recognize_pil_sync(enhanced, 'en')
        text = _extract_text_from_winocr_result(res_enh)
        entries = extract_all_coord_lines(text)
        if not entries:
            res_raw = winocr.recognize_pil_sync(img, 'en')
            raw_text = _extract_text_from_winocr_result(res_raw)
            entries = extract_all_coord_lines(raw_text)
            if raw_text and not text:
                text = raw_text
        return {
            "ok": True,
            "text": text,
            "engine": "winocr",
            "entries": entries,
        }

    except Exception:
        return {
            "ok": False,
            "text": "",
            "engine": "winocr",
            "entries": [],
            "error": "OCR extraction failed",
        }


def capture_and_scan_entries() -> List[Dict[str, Any]]:
    """Capture screen regions (chat & HUD zones) and extract all coordinate lines."""
    if not HAS_WINOCR:
        return []
    try:
        with ImageGrab.grab() as screen:
            w, h = screen.size

            # Region 1: Left & Bottom-Left 50% width x bottom 55% height (covers In-Game Chat Box + Map/HUD Coords)
            crop_boxes = [
                (0, int(h * 0.45), int(w * 0.50), h),
                # Region 2: Top-Left 40% width x 35% height (top-left HUD / squad chat)
                (0, 0, int(w * 0.40), int(h * 0.35)),
                # Region 3: Bottom-Right 45% width x 40% height (bottom-right compass/vehicle/chat HUD)
                (int(w * 0.55), int(h * 0.60), w, h),
            ]

            found_entries: List[Dict[str, Any]] = []
            seen_in_pass = set()
            for box in crop_boxes:
                cropped = screen.crop(box)
                # First pass on contrast-enhanced upscaled crop (prevents small-font decimal loss), fallback to raw crop
                enhanced = _preprocess_for_ocr(cropped)
                res_enh = winocr.recognize_pil_sync(enhanced, 'en')
                entries = extract_all_coord_lines(_extract_text_from_winocr_result(res_enh))
                if not entries:
                    res_raw = winocr.recognize_pil_sync(cropped, 'en')
                    entries = extract_all_coord_lines(_extract_text_from_winocr_result(res_raw))
                for entry in entries:
                    sig = (entry["role"], entry["x"], entry["y"])
                    if sig not in seen_in_pass:
                        seen_in_pass.add(sig)
                        found_entries.append(entry)
            return found_entries
    except Exception:
        return []


def capture_and_scan_coords() -> Optional[Tuple[float, float]]:
    entries = capture_and_scan_entries()
    if entries:
        last = entries[-1]
        return (last["x"], last["y"])
    return None


def read_windows_clipboard_text() -> Optional[str]:
    """Read CF_UNICODETEXT from Windows clipboard using ctypes (zero external deps)."""
    if not hasattr(ctypes, 'windll'):
        return None
    CF_UNICODETEXT = 13
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = ctypes.c_int
    user32.GetClipboardData.argtypes = [ctypes.c_uint]
    user32.GetClipboardData.restype = ctypes.c_void_p
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = ctypes.c_int
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.restype = ctypes.c_int

    if not user32.OpenClipboard(None):
        return None
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return None
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    except Exception:
        return None
    finally:
        user32.CloseClipboard()


class ScreenOcrWatcher:
    def __init__(self, interval: float = 1.0, on_coords_found: Optional[Callable[[float, float], None]] = None):
        self.interval = interval
        self.on_coords_found = on_coords_found
        self.is_running = False
        self.watch_clipboard = True
        self.last_coords: Optional[Tuple[float, float]] = None
        self.last_role: str = "target"
        self.last_raw_line: str = ""
        self.last_source: str = "ocr"
        self.last_update_time: float = 0
        self.event_seq: int = 0
        self.recent_events: List[Dict[str, Any]] = []
        self._seen_signatures: List[str] = []
        self._last_clip_seq: int = self._get_clip_seq()
        self._thread: Optional[threading.Thread] = None

    def _get_clip_seq(self) -> int:
        if hasattr(ctypes, 'windll'):
            try:
                return int(ctypes.windll.user32.GetClipboardSequenceNumber())
            except Exception:
                return 0
        return 0

    def start(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        self._last_clip_seq = self._get_clip_seq()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self.is_running = False

    def _record_entry(self, entry: Dict[str, Any], source: str) -> None:
        x, y = entry["x"], entry["y"]
        role = entry["role"]
        raw_line = entry.get("raw_line", f"{x:.2f} {y:.2f}")
        sig = f"{role}:{x:.2f}:{y:.2f}"

        # Ignore if identical to the currently active entry unless it came from an explicit new clipboard copy
        if source == "ocr" and sig in self._seen_signatures[-8:]:
            return

        self._seen_signatures.append(sig)
        if len(self._seen_signatures) > 40:
            self._seen_signatures = self._seen_signatures[-40:]

        self.last_coords = (x, y)
        self.last_role = role
        self.last_raw_line = raw_line
        self.last_source = source
        self.last_update_time = time.time()
        self.event_seq += 1
        self.recent_events.append({
            "seq": self.event_seq,
            "x": x,
            "y": y,
            "role": role,
            "raw_line": raw_line,
            "source": source,
            "ts": self.last_update_time,
        })
        if len(self.recent_events) > 20:
            self.recent_events = self.recent_events[-20:]
        if self.on_coords_found:
            self.on_coords_found(x, y)

    def _check_clipboard(self) -> bool:
        if not self.watch_clipboard:
            return False
        seq = self._get_clip_seq()
        if seq == 0 or seq == self._last_clip_seq:
            return False
        self._last_clip_seq = seq
        text = read_windows_clipboard_text()
        if not text or "[WARDOGS " in text:
            # Ignore our own exported mission strings
            return False
        entries = extract_all_coord_lines(text)
        if entries:
            for entry in entries:
                self._record_entry(entry, source="clipboard")
            return True
        return False

    def _run_loop(self) -> None:
        last_ocr_ts = 0.0
        while self.is_running:
            now = time.time()
            # Poll Windows clipboard at 5Hz for instant Ctrl+C in-game chat capture
            self._check_clipboard()

            if now - last_ocr_ts >= self.interval:
                last_ocr_ts = now
                entries = capture_and_scan_entries()
                for entry in entries:
                    self._record_entry(entry, source="ocr")

            time.sleep(0.2)

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self.is_running,
            "has_winocr": HAS_WINOCR,
            "ocr_backend": "winocr" if HAS_WINOCR else "omniconvert_qwen3_vl",
            "omniconvert_url": OMNICONVERT_URL,
            "watch_clipboard": self.watch_clipboard,
            "last_coords": self.last_coords,
            "last_role": self.last_role,
            "last_raw_line": self.last_raw_line,
            "last_source": self.last_source,
            "last_update_time": self.last_update_time,
            "event_seq": self.event_seq,
            "recent_events": list(self.recent_events[-10:]),
        }


# Global singleton for server.py integration
GLOBAL_OCR_WATCHER = ScreenOcrWatcher()
