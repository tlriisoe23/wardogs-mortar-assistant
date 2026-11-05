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
    # WinOCR joins lines with spaces in res['text'] but preserves line dicts in res['lines']  # noqa: E501
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
    # Must ignore Assistant's own UI labels and example lines so screen OCR never self-triggers  # noqa: E501
    assert parse_chat_coord_line(
        "🟢 [CL · OCR] (78.50, 69.50) — Gun Location Locked") is None
    assert parse_chat_coord_line(
        "🔴 [TGT] (82.18, 71.53) — Default Target ready") is None
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


def test_extract_all_coord_lines_supports_single_line_dual_gun_target_pairs():
    # Players frequently paste or type Gun + Target on a single line
    for sample in (
        "78.50 69.50 82.18 71.53",
        "78.50, 69.50 -> 82.18, 71.53",
        "x78.50 y69.50 x82.18 y71.53",
        "7850 6950 8218 7153",
    ):
        entries = extract_all_coord_lines(sample)
        assert len(
            entries) == 2, f"Expected 2 entries for {sample!r}, got {entries}"
        assert entries[0]["role"] == "cl"
        assert entries[0]["x"] == 78.50
        assert entries[0]["y"] == 69.50
        assert entries[1]["role"] == "target"
        assert entries[1]["x"] == 82.18
        assert entries[1]["y"] == 71.53


def test_flatten_markdown_table():
    md = "| CL X: | 78.50 | Y: | 69.50 |\n|---|---|---|---|\n| Target | 112.40 | 88.20 |"  # noqa: E501
    flat = _flatten_markdown_table(md)
    assert "CL X: 78.50 Y: 69.50" in flat
    assert "Target 112.40 88.20" in flat


def test_screen_ocr_watcher_start_stop_and_recent_events():
    watcher = ScreenOcrWatcher()
    assert not watcher.is_running

    watcher._record_entry({"x": 78.50, "y": 69.50, "role": "cl",
                          "raw_line": "78.50 69.50 CL"}, source="ocr")
    watcher._record_entry(
        {"x": 82.18, "y": 71.53, "role": "target", "raw_line": "82.18 71.53"}, source="ocr")  # noqa: E501

    status = watcher.get_status()
    assert status["running"] is False
    assert status["watch_clipboard"] is True
    assert status["event_seq"] == 2
    assert len(status["recent_events"]) == 2
    assert status["recent_events"][0]["role"] == "cl"
    assert status["recent_events"][0]["seq"] == 1
    assert status["recent_events"][1]["role"] == "target"
    assert status["recent_events"][1]["seq"] == 2


def test_screen_ocr_watcher_clipboard_handling():
    from ocr_sniff import ScreenOcrWatcher
    watcher = ScreenOcrWatcher(interval=10.0)
    watcher.watch_clipboard = True

    # Test identical signature dedup
    watcher._record_entry(
        {"x": 10.0, "y": 20.0, "role": "target", "raw_line": "1"}, "ocr")
    assert watcher.event_seq == 1
    # OCR duplicate should be ignored
    watcher._record_entry(
        {"x": 10.0, "y": 20.0, "role": "target", "raw_line": "2"}, "ocr")
    assert watcher.event_seq == 1

    # Clipboard duplicate should NOT be ignored
    watcher._record_entry(
        {"x": 10.0, "y": 20.0, "role": "target", "raw_line": "2"}, "clipboard")
    assert watcher.event_seq == 2

    import unittest.mock
    with unittest.mock.patch('ocr_sniff.read_windows_clipboard_text', return_value="CL X: 50.00 Y: 60.00"):  # noqa: E501
        with unittest.mock.patch.object(watcher, '_get_clip_seq', side_effect=[1, 2, 2]):  # noqa: E501
            watcher._last_clip_seq = 0

            # First check: get_clip_seq returns 1 (changed)
            assert watcher._check_clipboard() is True
            assert watcher.event_seq == 3
            assert watcher.last_role == "cl"

            # Second check: get_clip_seq returns 2 (changed)
            assert watcher._check_clipboard() is True
            assert watcher.event_seq == 4

            # Third check: get_clip_seq returns 2 (unchanged)
            assert watcher._check_clipboard() is False
            assert watcher.event_seq == 4

    # Test ignoring self-export
    with unittest.mock.patch('ocr_sniff.read_windows_clipboard_text', return_value="[WARDOGS EXPORT]"):  # noqa: E501
        with unittest.mock.patch.object(watcher, '_get_clip_seq', return_value=3):  # noqa: E501
            assert watcher._check_clipboard() is False


def test_capture_and_scan_coords():
    import unittest.mock
    from ocr_sniff import capture_and_scan_coords
    with unittest.mock.patch('ocr_sniff.capture_and_scan_entries', return_value=[{"x": 12.3, "y": 45.6, "role": "target"}]):  # noqa: E501
        res = capture_and_scan_coords()
        assert res == (12.3, 45.6)

    with unittest.mock.patch('ocr_sniff.capture_and_scan_entries', return_value=[]):  # noqa: E501
        res = capture_and_scan_coords()
        assert res is None


def test_read_windows_clipboard_text():
    import unittest.mock
    from ocr_sniff import read_windows_clipboard_text

    with unittest.mock.patch('ctypes.windll', create=True) as mock_windll:
        mock_windll.user32.OpenClipboard.return_value = 1
        mock_windll.user32.GetClipboardData.return_value = 12345
        mock_windll.kernel32.GlobalLock.return_value = 67890

        with unittest.mock.patch('ctypes.wstring_at', return_value="CL X: 10 Y: 20"):  # noqa: E501
            assert read_windows_clipboard_text() == "CL X: 10 Y: 20"

        mock_windll.user32.OpenClipboard.return_value = 0
        assert read_windows_clipboard_text() is None


def test_read_windows_clipboard_text_exceptions():
    import unittest.mock
    from ocr_sniff import read_windows_clipboard_text

    with unittest.mock.patch('ctypes.windll', create=True) as mock_windll:
        mock_windll.user32.OpenClipboard.return_value = 1
        mock_windll.user32.GetClipboardData.return_value = 0
        assert read_windows_clipboard_text() is None

        mock_windll.user32.GetClipboardData.return_value = 12345
        mock_windll.kernel32.GlobalLock.return_value = 0
        assert read_windows_clipboard_text() is None

        mock_windll.kernel32.GlobalLock.return_value = 67890
        with unittest.mock.patch('ctypes.wstring_at', side_effect=Exception("error")):  # noqa: E501
            assert read_windows_clipboard_text() is None


def test_extract_text_via_winocr_bytes():
    from ocr_sniff import extract_text_via_winocr_bytes
    import unittest.mock

    with unittest.mock.patch('ocr_sniff.HAS_WINOCR', False):
        res = extract_text_via_winocr_bytes(b"dummy")
        assert not res["ok"]
        assert res["engine"] == "unavailable"

    with unittest.mock.patch('ocr_sniff.HAS_WINOCR', True):
        with unittest.mock.patch('ocr_sniff.Image.open', side_effect=Exception("bad img")):  # noqa: E501
            res = extract_text_via_winocr_bytes(b"dummy")
            assert not res["ok"]

        mock_img = unittest.mock.MagicMock()
        mock_img.convert.return_value = mock_img

        with unittest.mock.patch('ocr_sniff.Image.open') as mock_open:
            mock_open.return_value.__enter__.return_value = mock_img
            with unittest.mock.patch('ocr_sniff._preprocess_for_ocr', return_value=mock_img):  # noqa: E501
                mock_winocr = unittest.mock.MagicMock()
                mock_winocr.recognize_pil_sync.return_value = {
                    "text": "[Squad] Alpha: 78.50 69.50 CL", "lines": [{"text": "[Squad] Alpha: 78.50 69.50 CL"}]}  # noqa: E501

                with unittest.mock.patch('ocr_sniff.winocr', mock_winocr, create=True):  # noqa: E501
                    # First run: entries found in enhanced image
                    res = extract_text_via_winocr_bytes(b"dummy")
                    assert res["ok"]
                    assert res["engine"] == "winocr"
                    assert len(res["entries"]) == 1

                    # Second run: no entries in enhanced, fall back to raw image  # noqa: E501
                    mock_winocr.recognize_pil_sync.side_effect = [{"text": "none", "lines": [{"text": "none"}]}, {  # noqa: E501
                        "text": "[Squad] Bravo: 82.18 71.53 Target", "lines": [{"text": "[Squad] Bravo: 82.18 71.53 Target"}]}]  # noqa: E501
                    res2 = extract_text_via_winocr_bytes(b"dummy")
                    assert res2["ok"]


def test_capture_and_scan_entries():
    from ocr_sniff import capture_and_scan_entries
    import unittest.mock

    with unittest.mock.patch('ocr_sniff.HAS_WINOCR', False):
        assert capture_and_scan_entries() == []

    mock_grab = unittest.mock.MagicMock()
    with unittest.mock.patch('ocr_sniff.HAS_WINOCR', True):
        with unittest.mock.patch('ocr_sniff.ImageGrab', mock_grab):
            mock_grab.grab.side_effect = Exception("grab error")
            assert capture_and_scan_entries() == []

            mock_img = unittest.mock.MagicMock()
            mock_grab.grab.side_effect = None
            mock_grab.grab.return_value = mock_img
            mock_img.size = (100, 100)
            mock_img.crop.return_value = mock_img

            with unittest.mock.patch('ocr_sniff._preprocess_for_ocr', return_value=mock_img):  # noqa: E501
                mock_winocr = unittest.mock.MagicMock()
                mock_winocr.recognize_pil_sync.return_value = {
                    "text": "CL X: 78.50 Y: 69.50", "lines": [{"text": "CL X: 78.50 Y: 69.50"}]}  # noqa: E501

                with unittest.mock.patch('ocr_sniff.winocr', mock_winocr, create=True):  # noqa: E501
                    res = capture_and_scan_entries()
                    assert len(res) > 0
                    assert res[0]["x"] == 78.50


def test_screen_ocr_watcher_start_stop():
    from ocr_sniff import ScreenOcrWatcher
    watcher = ScreenOcrWatcher(interval=10.0)
    assert not watcher.is_running

    import unittest.mock
    with unittest.mock.patch('threading.Thread') as mock_thread_cls:
        mock_thread = unittest.mock.MagicMock()
        mock_thread_cls.return_value = mock_thread

        watcher.start()
        assert watcher.is_running
        assert mock_thread.start.called

        # Second start should be ignored
        mock_thread.start.reset_mock()
        watcher.start()
        assert not mock_thread.start.called

        watcher.stop()
        assert not watcher.is_running


def test_screen_ocr_watcher_run_loop_step():
    from ocr_sniff import ScreenOcrWatcher
    watcher = ScreenOcrWatcher(interval=0.1)
    watcher.is_running = True

    import unittest.mock
    with unittest.mock.patch.object(watcher, '_check_clipboard', return_value=False):  # noqa: E501
        with unittest.mock.patch('ocr_sniff.capture_and_scan_entries', return_value=[{"x": 10.0, "y": 20.0, "role": "target", "raw_line": "Target"}]):  # noqa: E501
            with unittest.mock.patch('time.sleep'):
                # Simulate one step of the loop by manually running the logic inside  # noqa: E501
                # (since the actual loop is infinite if is_running is True)

                # We need to trigger the interval logic, so mock time.time
                with unittest.mock.patch('time.time', return_value=100.0):  # noqa: E501
                    # We can't easily break the loop without modifying watcher.is_running  # noqa: E501
                    # Let's just mock time.sleep to set watcher.is_running = False  # noqa: E501
                    def fake_sleep(t):
                        watcher.is_running = False

                    with unittest.mock.patch('time.sleep', side_effect=fake_sleep):  # noqa: E501
                        watcher._run_loop()

                assert watcher.event_seq == 1
                assert watcher.recent_events[-1]["x"] == 10.0
