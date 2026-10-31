import io
import json
import base64
import urllib.request
import urllib.error
import threading
from unittest.mock import patch, MagicMock
import pytest

from ocr_sniff import (
    extract_text_via_omniconvert,
    GLOBAL_OCR_WATCHER,
    ScreenOcrWatcher,
    OMNICONVERT_URL,
)
from server import Handler, ThreadedHTTPServer


def test_screen_ocr_watcher_status_fields():
    watcher = ScreenOcrWatcher()
    status = watcher.get_status()
    assert "omniconvert_url" in status
    assert status["omniconvert_url"] == OMNICONVERT_URL
    assert "ocr_backend" in status
    assert status["ocr_backend"] in ("winocr", "omniconvert_qwen3_vl")


def test_extract_text_via_omniconvert_success():
    sample_ocr_text = "CL X: 78.50 Y: 69.50\nTarget 112.40, 88.20\nHIT 112.35 88.15"
    mock_response_data = {
        "ok": True,
        "text": sample_ocr_text,
        "engine": "qwen3-vl:2b-instruct"
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_response_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        fake_png = b"\x89PNG\r\n\x1a\nfakeimagebytes"
        result = extract_text_via_omniconvert(fake_png, filename="hud.png", mode="smart_vision")

        assert mock_urlopen.called
        req = mock_urlopen.call_args[0][0]
        assert req.full_url.endswith("/api/ocr/extract")
        sent_payload = json.loads(req.data.decode("utf-8"))
        assert sent_payload["filename"] == "hud.png"
        assert sent_payload["mode"] == "smart_vision"
        assert sent_payload["image_base64"] == base64.b64encode(fake_png).decode("ascii")

        assert result["ok"] is True
        assert result["engine"] == "qwen3-vl:2b-instruct"
        assert result["text"] == sample_ocr_text
        assert len(result["entries"]) == 3

        cl_entry = result["entries"][0]
        assert cl_entry["role"] == "cl"
        assert cl_entry["x"] == 78.50
        assert cl_entry["y"] == 69.50

        target_entry = result["entries"][1]
        assert target_entry["role"] == "target"
        assert target_entry["x"] == 112.40
        assert target_entry["y"] == 88.20

        hit_entry = result["entries"][2]
        assert hit_entry["role"] == "impact"
        assert hit_entry["x"] == 112.35
        assert hit_entry["y"] == 88.15


def test_extract_text_via_omniconvert_upstream_failure():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        fake_png = b"dummy_bytes"
        result = extract_text_via_omniconvert(fake_png)

        assert result["ok"] is False
        assert result["engine"] == "unavailable"
        assert result["entries"] == []
        assert "OCR extraction failed" in result["error"]


def test_extract_text_via_omniconvert_http_error_fallback():
    class MockHTTPError(urllib.error.HTTPError):
        def __init__(self):
            self.code = 502
        def __str__(self):
            return "HTTP Error 502: Bad Gateway"
        def close(self):
            pass

    mock_err = MockHTTPError()
    mock_err.close = MagicMock()

    with patch("urllib.request.urlopen", side_effect=mock_err):
        fake_png = b"dummy_bytes"
        result = extract_text_via_omniconvert(fake_png)

        assert result["ok"] is False
        assert result["engine"] == "unavailable"
        assert result["entries"] == []
        assert "HTTP Error 502" in result["error"]
        mock_err.close.assert_called_once()


@pytest.fixture(scope="module")
def live_test_server():
    server = ThreadedHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    try:
        yield base_url
    finally:
        server.shutdown()
        server.server_close()


def test_post_extract_image_endpoint_success(live_test_server):
    sample_ocr_text = "CL X: 82.00 Y: 71.00\nTarget 120.00, 95.00"
    mock_res = {
        "ok": True,
        "engine": "qwen3-vl:2b-instruct",
        "text": sample_ocr_text,
        "entries": [
            {"x": 82.00, "y": 71.00, "role": "cl", "raw_line": "CL X: 82.00 Y: 71.00"},
            {"x": 120.00, "y": 95.00, "role": "target", "raw_line": "Target 120.00, 95.00"}
        ]
    }

    with patch("server.extract_text_via_omniconvert", return_value=mock_res):
        payload = {
            "image_base64": base64.b64encode(b"hud_screenshot").decode("ascii"),
            "filename": "hud.png",
            "mode": "smart_vision"
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{live_test_server}/api/ocr/extract-image",
            data=data,
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            body = json.loads(resp.read().decode("utf-8"))
            assert body["status"] == "ok"
            assert body["ok"] is True
            assert body["engine"] == "qwen3-vl:2b-instruct"
            assert len(body["entries"]) == 2
            assert GLOBAL_OCR_WATCHER.last_coords == (120.0, 95.0)
            assert GLOBAL_OCR_WATCHER.last_role == "target"


def test_post_extract_image_endpoint_validation_errors(live_test_server):
    # Missing image_base64
    req = urllib.request.Request(
        f"{live_test_server}/api/ocr/extract-image",
        data=json.dumps({"filename": "hud.png"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=5)
    try:
        assert exc_info.value.code == 400
    finally:
        exc_info.value.close()

    # Invalid base64
    req2 = urllib.request.Request(
        f"{live_test_server}/api/ocr/extract-image",
        data=json.dumps({"image_base64": "!!!not_base64!!!"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info2:
        urllib.request.urlopen(req2, timeout=5)
    try:
        assert exc_info2.value.code == 400
    finally:
        exc_info2.value.close()


def test_extract_text_via_omniconvert_parses_markdown_table_output():
    """qwen3-vl smart_vision returns pipe-delimited markdown tables; coords must still parse (AIS-283)."""
    table_text = "| CL X: | 78.50 | Y: | 69.50 |\n|---|---|---|---|\n| Model: | 20XW-003NUS | S/N: | PF3ABCD4 16GB RAM |"
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"ok": True, "text": table_text}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None
    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = extract_text_via_omniconvert(b"\x89PNG", filename="hud.png")
    assert result["text"] == table_text
    assert len(result["entries"]) == 1
    assert result["entries"][0]["role"] == "cl"
    assert result["entries"][0]["x"] == 78.50
    assert result["entries"][0]["y"] == 69.50


def test_post_extract_image_endpoint_fallback_to_winocr(live_test_server):
    failed_res = {
        "ok": False,
        "engine": "unavailable",
        "text": "",
        "entries": [],
        "error": "HTTP Error 502"
    }

    mock_winocr_res = {
        "ok": True,
        "engine": "winocr",
        "text": "Target 100.00, 200.00",
        "entries": [
            {"x": 100.00, "y": 200.00, "role": "target", "raw_line": "Target 100.00, 200.00"}
        ]
    }

    with patch("server.extract_text_via_omniconvert", return_value=failed_res), \
         patch("server.GLOBAL_OCR_WATCHER.get_status", return_value={"has_winocr": True}), \
         patch("server.extract_text_via_winocr_bytes", return_value=mock_winocr_res):

        payload = {
            "image_base64": base64.b64encode(b"hud_screenshot").decode("ascii"),
            "filename": "hud.png",
            "mode": "smart_vision"
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{live_test_server}/api/ocr/extract-image",
            data=data,
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            body = json.loads(resp.read().decode("utf-8"))
            assert body["status"] == "ok"
            assert body["ok"] is True
            assert body["engine"] == "winocr"
            assert len(body["entries"]) == 1
            assert body["entries"][0]["x"] == 100.00
