from unittest.mock import patch, MagicMock
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
    # WinOCR joins lines with spaces in res['text'] but preserves line dicts
    # in res['lines']
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
    # Must ignore Assistant's own UI labels and example lines so screen OCR
    # never self-triggers
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
        assert len(entries) == 2, f"Expected 2 entries for {
            sample!r}, got {entries}"
        assert entries[0]["role"] == "cl"
        assert entries[0]["x"] == 78.50
        assert entries[0]["y"] == 69.50
        assert entries[1]["role"] == "target"
        assert entries[1]["x"] == 82.18
        assert entries[1]["y"] == 71.53


def test_flatten_markdown_table():
    md = ("| CL X: | 78.50 | Y: | 69.50 |\n"
          "|---|---|---|---|\n"
          "| Target | 112.40 | 88.20 |")
    flat = _flatten_markdown_table(md)
    assert "CL X: 78.50 Y: 69.50" in flat
    assert "Target 112.40 88.20" in flat


def test_screen_ocr_watcher_start_stop_and_recent_events():
    watcher = ScreenOcrWatcher()
    assert not watcher.is_running

    watcher._record_entry({"x": 78.50,
                           "y": 69.50,
                           "role": "cl",
                           "raw_line": "78.50 69.50 CL"},
                          source="ocr")
    watcher._record_entry({"x": 82.18,
                           "y": 71.53,
                           "role": "target",
                           "raw_line": "82.18 71.53"},
                          source="ocr")

    status = watcher.get_status()
    assert status["running"] is False
    assert status["watch_clipboard"] is True
    assert status["event_seq"] == 2
    assert len(status["recent_events"]) == 2
    assert status["recent_events"][0]["role"] == "cl"
    assert status["recent_events"][0]["seq"] == 1
    assert status["recent_events"][1]["role"] == "target"
    assert status["recent_events"][1]["seq"] == 2


def test_capture_and_scan_entries_closes_image_on_error():
    with patch("ocr_sniff.ImageGrab.grab") as mock_grab:
        mock_img = MagicMock()
        mock_img.__enter__.return_value = mock_img
        # Simulate exception during processing to test cleanup
        mock_img.size = (1920, 1080)
        mock_img.crop.side_effect = Exception("crop failure")
        mock_grab.return_value = mock_img

        # Enable WINOCR temporarily for this test
        with patch("ocr_sniff.HAS_WINOCR", True):
            from ocr_sniff import capture_and_scan_entries
            result = capture_and_scan_entries()

        assert result == []
        mock_img.__exit__.assert_called_once()


def test_parse_timeout_env(monkeypatch, caplog):
    from ocr_sniff import _parse_timeout_env
    # Unset
    monkeypatch.delenv("TEST_TIMEOUT", raising=False)
    assert _parse_timeout_env("TEST_TIMEOUT", 45.0) == 45.0

    # Valid string
    monkeypatch.setenv("TEST_TIMEOUT", "30")
    assert _parse_timeout_env("TEST_TIMEOUT", 45.0) == 30.0

    # Non-finite values
    monkeypatch.setenv("TEST_TIMEOUT", "nan")
    assert _parse_timeout_env("TEST_TIMEOUT", 45.0) == 45.0
    monkeypatch.setenv("TEST_TIMEOUT", "inf")
    assert _parse_timeout_env("TEST_TIMEOUT", 45.0) == 45.0

    # Negative or Zero
    monkeypatch.setenv("TEST_TIMEOUT", "-5")
    assert _parse_timeout_env("TEST_TIMEOUT", 45.0) == 45.0
    monkeypatch.setenv("TEST_TIMEOUT", "0")
    assert _parse_timeout_env("TEST_TIMEOUT", 45.0) == 45.0

    # Clamp
    monkeypatch.setenv("TEST_TIMEOUT", "99999")
    assert _parse_timeout_env("TEST_TIMEOUT", 45.0, max_s=600.0) == 600.0

    # Invalid String
    monkeypatch.setenv("TEST_TIMEOUT", "abc")
    assert _parse_timeout_env("TEST_TIMEOUT", 45.0) == 45.0


@patch('builtins.hasattr', return_value=False)
def test_read_windows_clipboard_text_no_windll(mock_hasattr):
    from ocr_sniff import read_windows_clipboard_text
    assert read_windows_clipboard_text() is None


@patch('builtins.hasattr', return_value=True)
def test_read_windows_clipboard_text_success(mock_hasattr):
    with patch.dict('sys.modules', {'ctypes': MagicMock()}):
        import ctypes
        mock_windll = MagicMock()
        ctypes.windll = mock_windll
        mock_user32 = MagicMock()
        mock_kernel32 = MagicMock()
        mock_windll.user32 = mock_user32
        mock_windll.kernel32 = mock_kernel32

        mock_user32.OpenClipboard.return_value = 1
        mock_user32.GetClipboardData.return_value = 1234
        mock_kernel32.GlobalLock.return_value = 5678

        ctypes.wstring_at.return_value = "CL 78.50 69.50"
        import ocr_sniff
        with patch.object(ocr_sniff, 'ctypes', ctypes):
            res = ocr_sniff.read_windows_clipboard_text()
            assert res == "CL 78.50 69.50"
            mock_user32.CloseClipboard.assert_called_once()
            mock_kernel32.GlobalUnlock.assert_called_once_with(1234)


@patch('builtins.hasattr', return_value=True)
def test_read_windows_clipboard_text_open_fails(mock_hasattr):
    with patch.dict('sys.modules', {'ctypes': MagicMock()}):
        import ctypes
        mock_windll = MagicMock()
        ctypes.windll = mock_windll
        mock_user32 = MagicMock()
        mock_windll.user32 = mock_user32
        mock_user32.OpenClipboard.return_value = 0

        import ocr_sniff
        with patch.object(ocr_sniff, 'ctypes', ctypes):
            assert ocr_sniff.read_windows_clipboard_text() is None


@patch('builtins.hasattr', return_value=True)
def test_read_windows_clipboard_text_get_data_fails(mock_hasattr):
    with patch.dict('sys.modules', {'ctypes': MagicMock()}):
        import ctypes
        mock_windll = MagicMock()
        ctypes.windll = mock_windll
        mock_user32 = MagicMock()
        mock_windll.user32 = mock_user32
        mock_user32.OpenClipboard.return_value = 1
        mock_user32.GetClipboardData.return_value = 0

        import ocr_sniff
        with patch.object(ocr_sniff, 'ctypes', ctypes):
            assert ocr_sniff.read_windows_clipboard_text() is None
            mock_user32.CloseClipboard.assert_called_once()


@patch('builtins.hasattr', return_value=True)
def test_read_windows_clipboard_text_global_lock_fails(mock_hasattr):
    with patch.dict('sys.modules', {'ctypes': MagicMock()}):
        import ctypes
        mock_windll = MagicMock()
        ctypes.windll = mock_windll
        mock_user32 = MagicMock()
        mock_kernel32 = MagicMock()
        mock_windll.user32 = mock_user32
        mock_windll.kernel32 = mock_kernel32

        mock_user32.OpenClipboard.return_value = 1
        mock_user32.GetClipboardData.return_value = 1234
        mock_kernel32.GlobalLock.return_value = 0

        import ocr_sniff
        with patch.object(ocr_sniff, 'ctypes', ctypes):
            assert ocr_sniff.read_windows_clipboard_text() is None
            mock_user32.CloseClipboard.assert_called_once()


@patch('builtins.hasattr', return_value=True)
def test_read_windows_clipboard_text_exception(mock_hasattr):
    with patch.dict('sys.modules', {'ctypes': MagicMock()}):
        import ctypes
        mock_windll = MagicMock()
        ctypes.windll = mock_windll
        mock_user32 = MagicMock()
        mock_kernel32 = MagicMock()
        mock_windll.user32 = mock_user32
        mock_windll.kernel32 = mock_kernel32

        mock_user32.OpenClipboard.return_value = 1
        mock_user32.GetClipboardData.side_effect = Exception("boom")

        import ocr_sniff
        with patch.object(ocr_sniff, 'ctypes', ctypes):
            assert ocr_sniff.read_windows_clipboard_text() is None
            mock_user32.CloseClipboard.assert_called_once()


@patch('ocr_sniff.HAS_WINOCR', False)
def test_extract_text_via_winocr_bytes_unavailable():
    from ocr_sniff import extract_text_via_winocr_bytes
    res = extract_text_via_winocr_bytes(b"dummy")
    assert res == {
        "ok": False,
        "text": "",
        "engine": "unavailable",
        "entries": [],
        "error": "winocr not installed"}


@patch('ocr_sniff.HAS_WINOCR', True)
@patch('ocr_sniff.Image.open')
@patch('ocr_sniff._preprocess_for_ocr')
def test_extract_text_via_winocr_bytes_success_enhanced(
        mock_preprocess, mock_open):
    with patch.dict('sys.modules', {'winocr': MagicMock()}):
        import sys
        mock_winocr = sys.modules['winocr']

        mock_winocr.recognize_pil_sync.return_value = {
            "text": "CL 78.50 69.50",
            "lines": [{"text": "CL 78.50 69.50"}]
        }

        import ocr_sniff
        with patch.object(ocr_sniff, 'winocr', mock_winocr, create=True):
            mock_img = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_img
            mock_img.convert.return_value = mock_img
            mock_preprocess.return_value = mock_img

            res = ocr_sniff.extract_text_via_winocr_bytes(b"dummy")
            assert res["ok"] is True
            assert res["engine"] == "winocr"
            assert len(res["entries"]) == 1
            assert res["entries"][0]["role"] == "cl"


@patch('ocr_sniff.HAS_WINOCR', True)
@patch('ocr_sniff.Image.open')
@patch('ocr_sniff._preprocess_for_ocr')
def test_extract_text_via_winocr_bytes_fallback_to_raw(
        mock_preprocess, mock_open):
    with patch.dict('sys.modules', {'winocr': MagicMock()}):
        import sys
        mock_winocr = sys.modules['winocr']

        mock_winocr.recognize_pil_sync.side_effect = [
            {"text": "garbage", "lines": [{"text": "garbage"}]},
            {"text": "Target 112.40 88.20",
             "lines": [{"text": "Target 112.40 88.20"}]}
        ]
        import ocr_sniff
        with patch.object(ocr_sniff, 'winocr', mock_winocr, create=True):
            mock_img = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_img
            mock_img.convert.return_value = mock_img
            mock_preprocess.return_value = mock_img

            res = ocr_sniff.extract_text_via_winocr_bytes(b"dummy")
            assert res["ok"] is True
            assert res["engine"] == "winocr"
            assert len(res["entries"]) == 1
            assert res["entries"][0]["role"] == "target"


@patch('ocr_sniff.HAS_WINOCR', True)
@patch('ocr_sniff.Image.open')
def test_extract_text_via_winocr_bytes_exception(mock_open):
    from ocr_sniff import extract_text_via_winocr_bytes
    mock_open.side_effect = Exception("boom")

    res = extract_text_via_winocr_bytes(b"dummy")
    assert res["ok"] is False
    assert res["engine"] == "winocr"
    assert res["error"] == "OCR extraction failed"


def test_preprocess_for_ocr_resize():
    from ocr_sniff import _preprocess_for_ocr
    from PIL import Image
    # 600 width -> scale 3
    img = Image.new('RGB', (600, 400), color='white')
    enhanced = _preprocess_for_ocr(img)
    assert enhanced.size == (1800, 1200)


def test_preprocess_for_ocr_resize_2x():
    from ocr_sniff import _preprocess_for_ocr
    from PIL import Image
    # 800 width -> scale 2
    img = Image.new('RGB', (800, 400), color='white')
    enhanced = _preprocess_for_ocr(img)
    assert enhanced.size == (1600, 800)


def test_preprocess_for_ocr_no_resize():
    from ocr_sniff import _preprocess_for_ocr
    from PIL import Image
    # 1500 width -> no scale
    img = Image.new('RGB', (1500, 400), color='white')
    enhanced = _preprocess_for_ocr(img)
    assert enhanced.size == (1500, 400)


@patch('ocr_sniff.ImageOps.autocontrast')
def test_preprocess_for_ocr_exception(mock_autocontrast):
    from ocr_sniff import _preprocess_for_ocr
    from PIL import Image
    mock_autocontrast.side_effect = Exception("boom")
    img = Image.new('RGB', (800, 400), color='white')
    enhanced = _preprocess_for_ocr(img)
    assert enhanced == img


@patch('ocr_sniff.HAS_WINOCR', False)
def test_capture_and_scan_entries_no_winocr():
    from ocr_sniff import capture_and_scan_entries
    assert capture_and_scan_entries() == []


@patch('ocr_sniff.HAS_WINOCR', True)
@patch('ocr_sniff.ImageGrab.grab')
@patch('ocr_sniff._preprocess_for_ocr')
def test_capture_and_scan_entries_success(mock_preprocess, mock_grab):
    with patch.dict('sys.modules', {'winocr': MagicMock()}):
        import sys
        mock_winocr = sys.modules['winocr']

        # Two regions are going to be scanned in crop_boxes (3 boxes total)
        mock_winocr.recognize_pil_sync.side_effect = [
            {"text": "CL 78.50 69.50", "lines": [{"text": "CL 78.50 69.50"}]},
            {"text": "Target 112.40 88.20", "lines": [
                {"text": "Target 112.40 88.20"}]},
            {"text": "garbage",
             "lines": [{"text": "garbage"}]},
            # enhanced fails
            {"text": "CL 78.50 69.50",
             "lines": [{"text": "CL 78.50 69.50"}]},
            # raw succeeds but duplicate
        ]

        import ocr_sniff
        with patch.object(ocr_sniff, 'winocr', mock_winocr, create=True):
            mock_img = MagicMock()
            mock_grab.return_value.__enter__.return_value = mock_img
            mock_img.size = (1920, 1080)
            mock_img.crop.return_value = mock_img
            mock_preprocess.return_value = mock_img

            entries = ocr_sniff.capture_and_scan_entries()
            assert len(entries) == 2
            roles = [e["role"] for e in entries]
            assert "cl" in roles
            assert "target" in roles


@patch('ocr_sniff.HAS_WINOCR', True)
@patch('ocr_sniff.ImageGrab.grab')
@patch('ocr_sniff._preprocess_for_ocr')
def test_capture_and_scan_coords_success(mock_preprocess, mock_grab):
    with patch.dict('sys.modules', {'winocr': MagicMock()}):
        import sys
        mock_winocr = sys.modules['winocr']
        mock_winocr.recognize_pil_sync.return_value = {
            "text": "Target 112.40 88.20", "lines": [{"text": "Target 112.40 88.20"}]
        }

        import ocr_sniff
        with patch.object(ocr_sniff, 'winocr', mock_winocr, create=True):
            mock_img = MagicMock()
            mock_grab.return_value.__enter__.return_value = mock_img
            mock_img.size = (1920, 1080)
            mock_img.crop.return_value = mock_img
            mock_preprocess.return_value = mock_img

            coords = ocr_sniff.capture_and_scan_coords()
            assert coords == (112.40, 88.20)


@patch('ocr_sniff.HAS_WINOCR', True)
@patch('ocr_sniff.ImageGrab.grab')
@patch('ocr_sniff._preprocess_for_ocr')
def test_capture_and_scan_coords_none(mock_preprocess, mock_grab):
    with patch.dict('sys.modules', {'winocr': MagicMock()}):
        import sys
        mock_winocr = sys.modules['winocr']
        mock_winocr.recognize_pil_sync.return_value = {
            "text": "garbage", "lines": [{"text": "garbage"}]
        }

        import ocr_sniff
        with patch.object(ocr_sniff, 'winocr', mock_winocr, create=True):
            mock_img = MagicMock()
            mock_grab.return_value.__enter__.return_value = mock_img
            mock_img.size = (1920, 1080)
            mock_img.crop.return_value = mock_img
            mock_preprocess.return_value = mock_img

            coords = ocr_sniff.capture_and_scan_coords()
            assert coords is None


@patch('builtins.hasattr', return_value=True)
def test_screen_ocr_watcher_get_clip_seq_success(mock_hasattr):
    with patch.dict('sys.modules', {'ctypes': MagicMock()}):
        import ctypes
        mock_windll = MagicMock()
        ctypes.windll = mock_windll
        mock_user32 = MagicMock()
        mock_windll.user32 = mock_user32
        mock_user32.GetClipboardSequenceNumber.return_value = 42

        import ocr_sniff
        with patch.object(ocr_sniff, 'ctypes', ctypes):
            watcher = ocr_sniff.ScreenOcrWatcher()
            assert watcher._get_clip_seq() == 42


@patch('builtins.hasattr', return_value=True)
def test_screen_ocr_watcher_get_clip_seq_exception(mock_hasattr):
    with patch.dict('sys.modules', {'ctypes': MagicMock()}):
        import ctypes
        mock_windll = MagicMock()
        ctypes.windll = mock_windll
        mock_user32 = MagicMock()
        mock_windll.user32 = mock_user32
        mock_user32.GetClipboardSequenceNumber.side_effect = Exception("boom")

        import ocr_sniff
        with patch.object(ocr_sniff, 'ctypes', ctypes):
            watcher = ocr_sniff.ScreenOcrWatcher()
            assert watcher._get_clip_seq() == 0


@patch('builtins.hasattr', return_value=False)
def test_screen_ocr_watcher_get_clip_seq_no_windll(mock_hasattr):
    from ocr_sniff import ScreenOcrWatcher
    watcher = ScreenOcrWatcher()
    assert watcher._get_clip_seq() == 0


def test_screen_ocr_watcher_start_stop():
    from ocr_sniff import ScreenOcrWatcher
    watcher = ScreenOcrWatcher()
    watcher._get_clip_seq = MagicMock(return_value=10)

    with patch('threading.Thread') as mock_thread:
        mock_instance = MagicMock()
        mock_thread.return_value = mock_instance

        watcher.start()
        assert watcher.is_running
        assert watcher._last_clip_seq == 10
        mock_thread.assert_called_once_with(
            target=watcher._run_loop, daemon=True)
        mock_instance.start.assert_called_once()

        # calling again should do nothing
        watcher.start()
        mock_thread.assert_called_once()

        watcher.stop()
        assert not watcher.is_running


def test_screen_ocr_watcher_record_entry_truncates():
    from ocr_sniff import ScreenOcrWatcher
    watcher = ScreenOcrWatcher()

    for i in range(50):
        watcher._record_entry(
            {"x": i, "y": i, "role": "target"}, source="clip")

    assert len(watcher._seen_signatures) == 40
    assert len(watcher.recent_events) == 20
    assert watcher.recent_events[-1]["x"] == 49


def test_screen_ocr_watcher_record_entry_duplicate_ocr_ignored():
    from ocr_sniff import ScreenOcrWatcher
    watcher = ScreenOcrWatcher()

    # 1. OCR finds something
    watcher._record_entry({"x": 10, "y": 10, "role": "target"}, source="ocr")
    assert watcher.event_seq == 1

    # 2. OCR finds exact same thing, should ignore
    watcher._record_entry({"x": 10, "y": 10, "role": "target"}, source="ocr")
    assert watcher.event_seq == 1

    # 3. Clipboard finds exact same thing, should NOT ignore
    watcher._record_entry(
        {"x": 10, "y": 10, "role": "target"}, source="clipboard")
    assert watcher.event_seq == 2


def test_screen_ocr_watcher_check_clipboard():
    from ocr_sniff import ScreenOcrWatcher
    watcher = ScreenOcrWatcher()
    watcher._get_clip_seq = MagicMock(return_value=1)
    watcher._last_clip_seq = 1

    # 1. No change in sequence
    assert watcher._check_clipboard() is False

    # 2. Watch clipboard off
    watcher.watch_clipboard = False
    assert watcher._check_clipboard() is False
    watcher.watch_clipboard = True

    # 3. Text not found
    watcher._get_clip_seq.return_value = 2
    with patch('ocr_sniff.read_windows_clipboard_text', return_value=None):
        assert watcher._check_clipboard() is False

    # 4. Text has our own string
    watcher._get_clip_seq.return_value = 3
    with patch('ocr_sniff.read_windows_clipboard_text',
               return_value="[WARDOGS MISSION]"):
        assert watcher._check_clipboard() is False

    # 5. Success
    watcher._get_clip_seq.return_value = 4
    with patch('ocr_sniff.read_windows_clipboard_text', return_value="CL 78.50 69.50"):
        assert watcher._check_clipboard() is True
        assert watcher.event_seq == 1
        assert watcher.last_coords == (78.50, 69.50)


def test_screen_ocr_watcher_run_loop():
    from ocr_sniff import ScreenOcrWatcher
    watcher = ScreenOcrWatcher(interval=1.0)
    watcher.is_running = True
    watcher._check_clipboard = MagicMock()

    # mock time.time so it executes OCR once, then we stop it
    with patch('time.time', side_effect=[100.0, 100.0, 101.0, 101.0, 101.0]):
        with patch('time.sleep', side_effect=lambda x: setattr(watcher, 'is_running', False)):
            with patch('ocr_sniff.capture_and_scan_entries',
                       return_value=[{"x": 10, "y": 10, "role": "target"}]):
                watcher._run_loop()

    watcher._check_clipboard.assert_called()
    assert watcher.event_seq == 1
    assert watcher.last_coords == (10, 10)


def test_screen_ocr_watcher_record_entry_on_coords_found():
    from ocr_sniff import ScreenOcrWatcher
    mock_cb = MagicMock()
    watcher = ScreenOcrWatcher(on_coords_found=mock_cb)

    watcher._record_entry({"x": 10, "y": 20, "role": "target"}, source="ocr")
    mock_cb.assert_called_once_with(10, 20)


def test_screen_ocr_watcher_get_status():
    from ocr_sniff import ScreenOcrWatcher
    watcher = ScreenOcrWatcher()
    watcher.is_running = True
    watcher.last_coords = (10, 20)
    watcher.last_role = "target"
    watcher.last_raw_line = "Target 10 20"
    watcher.last_source = "ocr"
    watcher.last_update_time = 100.0
    watcher.event_seq = 1
    watcher.recent_events = [{"x": 10, "y": 20, "role": "target"}]

    with patch('ocr_sniff.HAS_WINOCR', True):
        status = watcher.get_status()
        assert status["running"] is True
        assert status["has_winocr"] is True
        assert status["ocr_backend"] == "winocr"
        assert status["last_coords"] == (10, 20)
        assert status["last_role"] == "target"
        assert status["last_raw_line"] == "Target 10 20"
        assert status["last_source"] == "ocr"
        assert status["last_update_time"] == 100.0
        assert status["event_seq"] == 1
        assert len(status["recent_events"]) == 1


def test_screen_ocr_watcher_check_clipboard_returns_false_if_no_entries():
    from ocr_sniff import ScreenOcrWatcher
    watcher = ScreenOcrWatcher()
    watcher._get_clip_seq = MagicMock(return_value=1)
    watcher._last_clip_seq = 0

    with patch('ocr_sniff.read_windows_clipboard_text', return_value="no coords here"):
        assert watcher._check_clipboard() is False


def test_parse_chat_coord_line_empty():
    from ocr_sniff import parse_chat_coord_line
    assert parse_chat_coord_line("") is None
    assert parse_chat_coord_line("   ") is None


def test_parse_chat_coord_line_invalid_xy():
    from ocr_sniff import parse_chat_coord_line
    # valid format but outside map bounds
    assert parse_chat_coord_line("X: 999.0 Y: 999.0") is None


def test_parse_chat_coord_line_invalid_compact():
    from ocr_sniff import parse_chat_coord_line
    # compact grid outside bounds
    assert parse_chat_coord_line("999 999") is None


def test_parse_chat_coord_line_invalid_standard():
    from ocr_sniff import parse_chat_coord_line
    # standard pair outside bounds
    assert parse_chat_coord_line("999.0 999.0") is None


def test_parse_chat_coord_line_value_error_explicit():
    from ocr_sniff import parse_chat_coord_line
    with patch('ocr_sniff.float') as mock_float:
        mock_float.side_effect = ValueError("boom")
        # It should fall back to checking other regexes
        assert parse_chat_coord_line("X: 10.0 Y: 10.0") is None


def test_parse_chat_coord_line_value_error_standard():
    from ocr_sniff import parse_chat_coord_line
    # We want ExplicitXYRe to fail so it goes to StandardPairRe,
    # But they both use float(), so float() failing tests both ValueError paths
    # However, to explicitly test StandardPairRe, we should give it a string
    # that does not match ExplicitXYRe, but matches StandardPairRe
    with patch('ocr_sniff.float') as mock_float:
        mock_float.side_effect = ValueError("boom")
        assert parse_chat_coord_line("10.0 10.0") is None


def test_extract_dual_pairs_from_line_value_error_explicit():
    from ocr_sniff import _extract_dual_pairs_from_line
    with patch('ocr_sniff.float') as mock_float:
        mock_float.side_effect = ValueError("boom")
        res = _extract_dual_pairs_from_line(
            "X: 10.0 Y: 10.0 X: 20.0 Y: 20.0",
            "X: 10.0 Y: 10.0 X: 20.0 Y: 20.0")
        assert res == []


def test_extract_dual_pairs_from_line_value_error_standard():
    from ocr_sniff import _extract_dual_pairs_from_line
    with patch('ocr_sniff.float') as mock_float:
        mock_float.side_effect = ValueError("boom")
        res = _extract_dual_pairs_from_line(
            "10.0 10.0 -> 20.0 20.0", "10.0 10.0 -> 20.0 20.0")
        assert res == []


def test_extract_all_coord_lines_empty_text():
    from ocr_sniff import extract_all_coord_lines
    assert extract_all_coord_lines("") == []


def test_extract_all_coord_lines_empty_lines():
    from ocr_sniff import extract_all_coord_lines
    assert extract_all_coord_lines("\n  \n") == []


def test_extract_all_coord_lines_ignore_self_ui():
    from ocr_sniff import extract_all_coord_lines
    assert extract_all_coord_lines(
        "🔴 [TGT] (82.18, 71.53) — Default Target ready\n") == []


def test_extract_all_coord_lines_fallback_joined():
    from ocr_sniff import extract_all_coord_lines
    # Joined text matching single pair
    res = extract_all_coord_lines("CL \n 78.50 \n 69.50")
    assert len(res) == 1
    assert res[0]["role"] == "cl"


def test_extract_all_coord_lines_fallback_joined_dual():
    from ocr_sniff import extract_all_coord_lines
    # Joined text matching dual pair
    res = extract_all_coord_lines("78.50 \n 69.50 \n 82.18 \n 71.53")
    assert len(res) == 2
    assert res[0]["role"] == "cl"
    assert res[1]["role"] == "target"


def test_extract_text_via_winocr_bytes_missing_winocr_imports():
    import sys
    # Simulate winocr not being installed
    if 'winocr' in sys.modules:
        del sys.modules['winocr']

    # reload ocr_sniff
    import importlib
    import ocr_sniff
    with patch.dict('sys.modules', {'winocr': None}):
        importlib.reload(ocr_sniff)
        assert ocr_sniff.HAS_WINOCR is False


def test_extract_text_from_winocr_result_not_dict():
    from ocr_sniff import _extract_text_from_winocr_result
    assert _extract_text_from_winocr_result(None) == ""
    assert _extract_text_from_winocr_result("string") == ""


def test_extract_text_from_winocr_result_empty_lines():
    from ocr_sniff import _extract_text_from_winocr_result
    assert _extract_text_from_winocr_result({"lines": []}) == ""
    assert _extract_text_from_winocr_result(
        {"lines": [{"text": ""}], "text": "fallback"}) == "fallback"


def test_extract_text_via_rapidocr_empty_text():
    from ocr_sniff import extract_text_via_rapidocr
    import json
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = extract_text_via_rapidocr(b"dummy")
        assert res["ok"] is False
        assert res["text"] == ""
        assert res["entries"] == []


def test_extract_text_via_rapidocr_with_markdown_key():
    from ocr_sniff import extract_text_via_rapidocr
    import json
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(
        {"markdown": "CL 78.50 69.50"}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = extract_text_via_rapidocr(b"dummy")
        assert res["ok"] is True
        assert res["text"] == "CL 78.50 69.50"
        assert len(res["entries"]) == 1


def test_extract_text_via_rapidocr_urllib_error():
    from ocr_sniff import extract_text_via_rapidocr
    import urllib.error
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
        res = extract_text_via_rapidocr(b"dummy")
        assert res["ok"] is False


def test_extract_text_via_rapidocr_timeout_error():
    from ocr_sniff import extract_text_via_rapidocr
    with patch("urllib.request.urlopen", side_effect=TimeoutError("timeout")):
        res = extract_text_via_rapidocr(b"dummy")
        assert res["ok"] is False


def test_extract_text_via_rapidocr_connection_error():
    from ocr_sniff import extract_text_via_rapidocr
    with patch("urllib.request.urlopen", side_effect=ConnectionError("timeout")):
        res = extract_text_via_rapidocr(b"dummy")
        assert res["ok"] is False


def test_extract_text_via_rapidocr_http_error():
    from ocr_sniff import extract_text_via_rapidocr
    import urllib.error
    mock_err = urllib.error.HTTPError(
        url="http://fake",
        code=500,
        msg="Internal Server Error",
        hdrs={},
        fp=MagicMock())
    with patch("urllib.request.urlopen", side_effect=mock_err):
        res = extract_text_via_rapidocr(b"dummy")
        assert res["ok"] is False
        mock_err.fp.close.assert_called_once()


def test_extract_text_via_rapidocr_exception():
    from ocr_sniff import extract_text_via_rapidocr
    with patch("urllib.request.urlopen", side_effect=Exception("boom")):
        res = extract_text_via_rapidocr(b"dummy")
        assert res["ok"] is False


def test_extract_text_via_ollama_vlm_empty_text():
    from ocr_sniff import extract_text_via_ollama_vlm
    import json
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = extract_text_via_ollama_vlm(b"dummy")
        assert res["ok"] is False
        assert res["text"] == ""
        assert res["entries"] == []


def test_extract_text_via_ollama_vlm_with_response_key():
    from ocr_sniff import extract_text_via_ollama_vlm
    import json
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(
        {"response": "CL 78.50 69.50"}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = extract_text_via_ollama_vlm(b"dummy")
        assert res["ok"] is True
        assert res["text"] == "CL 78.50 69.50"
        assert len(res["entries"]) == 1


def test_extract_text_via_ollama_vlm_urllib_error():
    from ocr_sniff import extract_text_via_ollama_vlm
    import urllib.error
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
        res = extract_text_via_ollama_vlm(b"dummy")
        assert res["ok"] is False


def test_extract_text_via_ollama_vlm_timeout_error():
    from ocr_sniff import extract_text_via_ollama_vlm
    with patch("urllib.request.urlopen", side_effect=TimeoutError("timeout")):
        res = extract_text_via_ollama_vlm(b"dummy")
        assert res["ok"] is False


def test_extract_text_via_ollama_vlm_connection_error():
    from ocr_sniff import extract_text_via_ollama_vlm
    with patch("urllib.request.urlopen", side_effect=ConnectionError("timeout")):
        res = extract_text_via_ollama_vlm(b"dummy")
        assert res["ok"] is False


def test_extract_text_via_ollama_vlm_http_error():
    from ocr_sniff import extract_text_via_ollama_vlm
    import urllib.error
    mock_err = urllib.error.HTTPError(
        url="http://fake",
        code=500,
        msg="Internal Server Error",
        hdrs={},
        fp=MagicMock())
    with patch("urllib.request.urlopen", side_effect=mock_err):
        res = extract_text_via_ollama_vlm(b"dummy")
        assert res["ok"] is False
        mock_err.fp.close.assert_called_once()


def test_extract_text_via_ollama_vlm_exception():
    from ocr_sniff import extract_text_via_ollama_vlm
    with patch("urllib.request.urlopen", side_effect=Exception("boom")):
        res = extract_text_via_ollama_vlm(b"dummy")
        assert res["ok"] is False


def test_extract_text_via_omniconvert_cascade():
    from ocr_sniff import extract_text_via_omniconvert
    with patch("os.environ.get", return_value="1"):
        with patch("ocr_sniff.extract_text_via_rapidocr",
                   return_value={"ok": True, "entries": [{"x": 10}]}) as mock_rapid:
            res = extract_text_via_omniconvert(b"dummy")
            assert res["ok"] is True
            mock_rapid.assert_called_once()


def test_extract_text_via_omniconvert_cascade_fallback_to_vlm():
    from ocr_sniff import extract_text_via_omniconvert
    with patch("os.environ.get", return_value="1"):
        with patch("ocr_sniff.extract_text_via_rapidocr", return_value={"ok": False}):
            with patch("ocr_sniff.extract_text_via_ollama_vlm",
                       return_value={"ok": True, "entries": [{"x": 10}]}) as mock_vlm:
                res = extract_text_via_omniconvert(b"dummy")
                assert res["ok"] is True
                mock_vlm.assert_called_once()


def test_extract_text_via_omniconvert_cascade_all_fail():
    from ocr_sniff import extract_text_via_omniconvert
    import json
    with patch("os.environ.get", return_value="1"):
        with patch("ocr_sniff.extract_text_via_rapidocr", return_value={"ok": False}):
            with patch("ocr_sniff.extract_text_via_ollama_vlm",
                       return_value={"ok": False}):
                mock_resp = MagicMock()
                mock_resp.read.return_value = json.dumps(
                    {"text": "CL 78.50 69.50"}).encode("utf-8")
                mock_resp.__enter__.return_value = mock_resp
                mock_resp.__exit__.return_value = None
                with patch("urllib.request.urlopen", return_value=mock_resp):
                    res = extract_text_via_omniconvert(b"dummy")
                    assert res["ok"] is True
                    assert res["text"] == "CL 78.50 69.50"


def test_extract_text_via_omniconvert_success():
    from ocr_sniff import extract_text_via_omniconvert
    import json
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(
        {"text": "CL 78.50 69.50"}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = extract_text_via_omniconvert(b"dummy")
        assert res["ok"] is True
        assert res["text"] == "CL 78.50 69.50"
        assert len(res["entries"]) == 1


def test_extract_text_via_omniconvert_success_not_dict():
    from ocr_sniff import extract_text_via_omniconvert
    import json
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps("not a dict").encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = extract_text_via_omniconvert(b"dummy")
        assert res["ok"] is True
        assert res["text"] == ""
        assert res["entries"] == []


def test_extract_text_via_omniconvert_http_error():
    from ocr_sniff import extract_text_via_omniconvert
    import urllib.error
    mock_err = urllib.error.HTTPError(
        url="http://fake",
        code=500,
        msg="Internal Server Error",
        hdrs={},
        fp=MagicMock())
    with patch("urllib.request.urlopen", side_effect=mock_err):
        res = extract_text_via_omniconvert(b"dummy")
        assert res["ok"] is False
        assert "HTTP Error 500" in res["error"]
        mock_err.fp.close.assert_called_once()


def test_extract_text_via_omniconvert_exception():
    from ocr_sniff import extract_text_via_omniconvert
    with patch("urllib.request.urlopen", side_effect=Exception("boom")):
        res = extract_text_via_omniconvert(b"dummy")
        assert res["ok"] is False


def test_extract_text_via_omniconvert_urllib_error():
    from ocr_sniff import extract_text_via_omniconvert
    import urllib.error
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
        res = extract_text_via_omniconvert(b"dummy")
        assert res["ok"] is False


def test_extract_text_via_omniconvert_decode_error():
    from ocr_sniff import extract_text_via_omniconvert
    import json
    with patch("urllib.request.urlopen",
               side_effect=json.JSONDecodeError("boom", "", 0)):
        res = extract_text_via_omniconvert(b"dummy")
        assert res["ok"] is False


@patch('ocr_sniff.HAS_WINOCR', True)
@patch('ocr_sniff.Image.open')
@patch('ocr_sniff._preprocess_for_ocr')
def test_extract_text_via_winocr_bytes_fallback_to_raw_and_text(
        mock_preprocess, mock_open):
    with patch.dict('sys.modules', {'winocr': MagicMock()}):
        import sys
        mock_winocr = sys.modules['winocr']

        mock_winocr.recognize_pil_sync.side_effect = [
            {"text": "", "lines": []},
            {"text": "Target 112.40 88.20",
             "lines": [{"text": "Target 112.40 88.20"}]}
        ]
        import ocr_sniff
        with patch.object(ocr_sniff, 'winocr', mock_winocr, create=True):
            mock_img = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_img
            mock_img.convert.return_value = mock_img
            mock_preprocess.return_value = mock_img

            res = ocr_sniff.extract_text_via_winocr_bytes(b"dummy")
            assert res["ok"] is True
            assert res["engine"] == "winocr"
            assert len(res["entries"]) == 1
            assert res["entries"][0]["role"] == "target"
            assert res["text"] == "Target 112.40 88.20"
            # add something that hits line 47 for mock of winocr.


def test_import_winocr_success():
    import importlib
    with patch.dict('sys.modules', {'winocr': MagicMock()}):
        import ocr_sniff
        importlib.reload(ocr_sniff)
        assert ocr_sniff.HAS_WINOCR is True
