import pytest
from ocr_sniff import (
    is_valid_wardogs_coord,
    _decode_compact_grid,
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

def test_screen_ocr_watcher_start_stop():
    watcher = ScreenOcrWatcher()
    assert not watcher.is_running

    # We won't test full start as it launches a background thread, but we can verify status.
    status = watcher.get_status()
    assert status["running"] is False
    assert status["watch_clipboard"] is True
