import pytest
from ocr_sniff import (
    is_valid_wardogs_coord,
    _decode_compact_grid,
    _extract_text_from_winocr_result,
    parse_chat_coord_line,
    parse_coords_from_text,
    extract_all_coord_lines,
    _flatten_markdown_table,
    ScreenOcrWatcher
)

def test_is_valid_wardogs_coord():
    assert is_valid_wardogs_coord(15.0, 15.0)
    assert is_valid_wardogs_coord(155.0, 155.0)
    assert is_valid_wardogs_coord(85.0, 85.0)
    assert not is_valid_wardogs_coord(14.9, 85.0)
    assert not is_valid_wardogs_coord(85.0, 155.1)

def test_decode_compact_grid():
    assert _decode_compact_grid("1534") == 15.34
    assert _decode_compact_grid("12345") == 123.45
    assert _decode_compact_grid("123") is None

def test_extract_text_from_winocr_result_preserves_lines():
    # WinOCR joins lines with spaces in res['text'] but preserves line dicts in res['lines']
    res = {
        "text": "[Squad] Alpha: 78.50 69.50 CL [Squad] Bravo: 82.18 71.53",
        "lines": [
            {"text": "[Squad] Alpha: 78.50 69.50 CL"},
            {"text": "[Squad] Bravo: 82.18 71.53"},
        ],
    }
    text = _extract_text_from_winocr_result(res)
    assert text == "[Squad] Alpha: 78.50 69.50 CL\n[Squad] Bravo: 82.18 71.53"
    entries = extract_all_coord_lines(text)
    assert len(entries) == 2
    assert entries[0]["role"] == "cl"
    assert entries[0]["x"] == 78.50
    assert entries[0]["y"] == 69.50
    assert entries[1]["role"] == "target"
    assert entries[1]["x"] == 82.18
    assert entries[1]["y"] == 71.53

def test_parse_chat_coord_line():
    # Target coordinate
    res = parse_chat_coord_line("X: 78.50 Y: 69.50")
    assert res is not None
    assert res["x"] == 78.5
    assert res["y"] == 69.5
    assert res["role"] == "target"

    # Current Location
    res = parse_chat_coord_line("CL X: 78.50 Y: 69.50")
    assert res is not None
    assert res["role"] == "cl"

    # Impact
    res = parse_chat_coord_line("splash 123.45, 123.45")
    assert res is not None
    assert res["role"] == "impact"
    assert res["x"] == 123.45

    # Compact Grid (must be within map limits)
    res = parse_chat_coord_line("1534 1534")
    assert res is not None
    assert res["x"] == 15.34

    # Standard Pair
    res = parse_chat_coord_line("123.45 123.45")
    assert res is not None
    assert res["x"] == 123.45

def test_parse_chat_coord_line_ignores_self_ui_chrome():
    # Must ignore Assistant's own UI labels and example lines so screen OCR never self-triggers
    assert parse_chat_coord_line("🟢 [CL · OCR] (78.50, 69.50) — Gun Location Locked") is None
    assert parse_chat_coord_line("🔴 [TGT] (82.18, 71.53) — Default Target ready") is None
    assert parse_chat_coord_line("ex: 78.5 69.5 CL") is None
    assert parse_chat_coord_line("🎯 AIM OFFSET: (82.18, 71.53)") is None

def test_parse_coords_from_text():
    # Test valid text
    assert parse_coords_from_text("X: 78.50 Y: 69.50") == (78.5, 69.5)
    # Test text with no valid coords
    assert parse_coords_from_text("no valid coords") is None

def test_extract_all_coord_lines():
    text = "X: 78.50 Y: 69.50\nsplash 123.45, 123.45"
    lines = extract_all_coord_lines(text)
    assert len(lines) == 2
    assert lines[0]["x"] == 78.5
    assert lines[1]["x"] == 123.45

def test_flatten_markdown_table():
    md = "| CL X: | 78.50 | Y: | 69.50 |\n|---|---|---|---|\n| Target | 112.40 | 88.20 |"
    flat = _flatten_markdown_table(md)
    assert "CL X: 78.50 Y: 69.50" in flat
    assert "Target 112.40 88.20" in flat

def test_screen_ocr_watcher_start_stop_and_recent_events():
    watcher = ScreenOcrWatcher()
    assert not watcher.is_running

    watcher._record_entry({"x": 78.50, "y": 69.50, "role": "cl", "raw_line": "78.50 69.50 CL"}, source="ocr")
    watcher._record_entry({"x": 82.18, "y": 71.53, "role": "target", "raw_line": "82.18 71.53"}, source="ocr")

    status = watcher.get_status()
    assert status["running"] is False
    assert status["watch_clipboard"] is True
    assert status["event_seq"] == 2
    assert len(status["recent_events"]) == 2
    assert status["recent_events"][0]["role"] == "cl"
    assert status["recent_events"][0]["seq"] == 1
    assert status["recent_events"][1]["role"] == "target"
    assert status["recent_events"][1]["seq"] == 2
