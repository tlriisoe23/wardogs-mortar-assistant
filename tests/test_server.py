import io
import email.message
import unittest.mock
import base64
import json
import urllib.request
import urllib.error
import threading
import pytest
from server import Handler, ThreadedHTTPServer, get_vk_name


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


def test_get_vk_name():
    assert get_vk_name(0x04) == "Middle Mouse (MMB)"
    assert get_vk_name(0x42) == "B Key"
    assert get_vk_name(0x99) == "Key 0x99"


def test_health_endpoint(live_test_server):
    req = urllib.request.Request(f"{live_test_server}/api/health")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["ok"] is True
        assert data["status"] == "healthy"
        assert "service" in data
        assert "port" in data
        assert "weapons" in data
        assert "maps" in data
        assert "tauri_v2_ready" in data


def test_desktop_hud_get_endpoint(live_test_server):
    req = urllib.request.Request(f"{live_test_server}/api/desktop-hud")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["ok"] is True
        assert "tauri_v2_ready" in data


def test_ptt_status_endpoint(live_test_server):
    req = urllib.request.Request(f"{live_test_server}/api/ptt/status")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "enabled" in data
        assert "vk" in data


def test_desktop_hud_post_endpoint(live_test_server):
    payload = {"action": "elev_up", "step_mils": 10}
    req = urllib.request.Request(
        f"{live_test_server}/api/desktop-hud",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["last_action"] == "elev_up"


def test_desktop_hud_post_non_dict_payload(live_test_server):
    payload = [1, 2, 3]
    req = urllib.request.Request(
        f"{live_test_server}/api/desktop-hud",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "last_action" in data


def test_api_targets_endpoint(live_test_server):
    import os
    import time
    from server import DIRECTORY

    targets_file = os.path.join(DIRECTORY, 'data', 'targets.json')

    # Backup original content
    with open(targets_file, 'rb') as f:
        original_content = f.read()

    try:
        # First call
        req = urllib.request.Request(f"{live_test_server}/api/targets")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            data1 = json.loads(resp.read().decode("utf-8"))

        # Second call, should use cache and return identical output
        req = urllib.request.Request(f"{live_test_server}/api/targets")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            data2 = json.loads(resp.read().decode("utf-8"))

        assert data1 == data2

        # Modify targets.json and assert new data is returned
        new_data = [{"id": "test_modified",
                     "map": "test",
                     "name": "test",
                     "category": "chokepoint",
                     "x": 0,
                     "y": 0,
                     "notes": "",
                     "voice_triggers": []}]
        with open(targets_file, 'w') as f:
            json.dump(new_data, f)

        # Ensure we wait enough to let file writes settle or update mtime_ns
        time.sleep(0.1)

        req = urllib.request.Request(f"{live_test_server}/api/targets")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            data3 = json.loads(resp.read().decode("utf-8"))

        assert data3 == new_data

    finally:
        # Restore original content
        with open(targets_file, 'wb') as f:
            f.write(original_content)
        time.sleep(0.1)
        os.utime(targets_file, None)


def test_targets_invalidate(live_test_server):
    import urllib.request
    import json
    import os
    import time
    from server import DIRECTORY

    targets_file = os.path.join(DIRECTORY, 'data', 'targets.json')
    with open(targets_file, 'rb') as f:
        original_content = f.read()

    try:
        # Initial fetch to populate cache
        req = urllib.request.Request(f"{live_test_server}/api/targets")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            data1 = json.loads(resp.read().decode("utf-8"))

        # Write new data to invalidate cache
        new_data = [{"id": "cache_test",
                     "map": "test",
                     "name": "cache test",
                     "category": "test",
                     "x": 10,
                     "y": 20,
                     "notes": "",
                     "voice_triggers": []}]
        with open(targets_file, 'w') as f:
            json.dump(new_data, f)

        # Give OS a tiny moment
        time.sleep(0.05)

        req2 = urllib.request.Request(f"{live_test_server}/api/targets")
        with urllib.request.urlopen(req2, timeout=5) as resp:
            assert resp.status == 200
            data2 = json.loads(resp.read().decode("utf-8"))

        assert data1 != data2
        assert data2 == new_data

        # Post to HUD and check invalidation
        payload = {"action": "elev_up", "step_mils": 5}
        req_post = urllib.request.Request(
            f"{live_test_server}/api/desktop-hud",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req_post, timeout=5) as resp:
            assert resp.status == 200

        req_hud = urllib.request.Request(f"{live_test_server}/api/desktop-hud")
        with urllib.request.urlopen(req_hud, timeout=5) as resp:
            assert resp.status == 200
            data_hud = json.loads(resp.read().decode("utf-8"))
            assert data_hud["last_action"] == "elev_up"

    finally:
        with open(targets_file, 'wb') as f:
            f.write(original_content)
        time.sleep(0.05)
        os.utime(targets_file, None)


def _build_mock_handler(path, method="GET", body=b"", headers=None):
    handler = Handler.__new__(Handler)
    handler.rfile = io.BytesIO(body)
    handler.wfile = io.BytesIO()
    handler.path = path
    handler.command = method
    handler.request_version = "HTTP/1.1"
    handler.client_address = ("127.0.0.1", 0)
    handler.server = unittest.mock.MagicMock()
    handler.requestline = f"{method} {path} HTTP/1.1"

    msg = email.message.Message()
    if headers:
        for k, v in headers.items():
            msg[k] = str(v)
    handler.headers = msg

    # We can patch send_response, send_header, end_headers, send_error
    handler._responses = []

    def mock_send_response(code, message=None):
        handler._responses.append(
            {"code": code, "message": message, "headers": {}})

    def mock_send_header(keyword, value):
        if handler._responses:
            handler._responses[-1]["headers"][keyword] = value

    def mock_end_headers():
        pass

    def mock_send_error(code, message=None, explain=None):
        handler._responses.append(
            {"code": code, "message": message, "headers": {}})

    handler.send_response = mock_send_response
    handler.send_header = mock_send_header
    handler.end_headers = mock_end_headers
    handler.send_error = mock_send_error

    return handler


def test_api_ptt_config():
    from server import GLOBAL_PTT_WATCHER
    orig_enabled = GLOBAL_PTT_WATCHER.enabled
    orig_vk = GLOBAL_PTT_WATCHER.vk

    # ensure no real threads start
    with unittest.mock.patch.object(
            GLOBAL_PTT_WATCHER, "_thread", autospec=True):
        try:
            # Valid enable and vk
            h1 = _build_mock_handler("/api/ptt/config?enabled=true&vk=0x42")
            h1.do_GET()
            resp = json.loads(h1.wfile.getvalue().decode('utf-8'))
            assert resp["enabled"] is True
            assert resp["vk"] == 0x42

            # Make the invalid case deterministic by first setting known valid
            # state
            GLOBAL_PTT_WATCHER.enabled = True
            GLOBAL_PTT_WATCHER.vk = 0x42

            # Invalid enable flag (should just parse as string and false if not
            # recognized)
            h2 = _build_mock_handler("/api/ptt/config?enabled=invalid&vk=bad")
            h2.do_GET()
            resp2 = json.loads(h2.wfile.getvalue().decode('utf-8'))
            assert resp2["enabled"] is False
            assert resp2["vk"] == 0x42  # Unchanged
        finally:
            GLOBAL_PTT_WATCHER.enabled = orig_enabled
            GLOBAL_PTT_WATCHER.vk = orig_vk


def test_api_ptt_bind():
    with unittest.mock.patch(
            'server.GLOBAL_PTT_WATCHER.start_bind_capture') as mock_start:
        h = _build_mock_handler("/api/ptt/bind")
        h.do_GET()
        mock_start.assert_called_once_with(timeout_sec=6.0)


def test_api_ocr_extract_image():
    valid_payload = json.dumps({
        "image_base64": base64.b64encode(b"valid_image").decode("utf-8")
    }).encode("utf-8")

    ret_val = {"ok": True, "text": "target_hit", "lines": []}
    with unittest.mock.patch(
            'server.extract_text_via_omniconvert', return_value=ret_val):
        # 1. Success path
        h_success = _build_mock_handler(
            "/api/ocr/extract-image",
            method="POST",
            body=valid_payload,
            headers={
                "Content-Length": len(valid_payload)})
        h_success.do_POST()
        assert h_success._responses[0]["code"] == 200
        resp_success = json.loads(h_success.wfile.getvalue().decode("utf-8"))
        assert resp_success["ok"] is True
        assert resp_success["text"] == "target_hit"

        # 2. Invalid base64
        invalid_payload = json.dumps(
            {"image_base64": "not_base64!@#"}).encode("utf-8")
        h_invalid = _build_mock_handler(
            "/api/ocr/extract-image",
            method="POST",
            body=invalid_payload,
            headers={
                "Content-Length": len(invalid_payload)})
        h_invalid.do_POST()
        assert h_invalid._responses[0]["code"] == 400

        # 3. Missing base64 key
        missing_payload = json.dumps({}).encode("utf-8")
        h_missing = _build_mock_handler(
            "/api/ocr/extract-image",
            method="POST",
            body=missing_payload,
            headers={
                "Content-Length": len(missing_payload)})
        h_missing.do_POST()
        assert h_missing._responses[0]["code"] == 400

        # 4. Too large payload
        h_large = _build_mock_handler(
            "/api/ocr/extract-image",
            method="POST",
            body=b"{}",
            headers={
                "Content-Length": 11 * 1024 * 1024})
        h_large.do_POST()
        assert h_large._responses[0]["code"] == 413

        # 5. Invalid JSON
        h_json = _build_mock_handler(
            "/api/ocr/extract-image",
            method="POST",
            body=b"invalid",
            headers={
                "Content-Length": 7})
        h_json.do_POST()
        assert h_json._responses[0]["code"] == 400

        # 6. Not a dictionary JSON
        h_list = _build_mock_handler(
            "/api/ocr/extract-image",
            method="POST",
            body=b"[1, 2, 3]",
            headers={
                "Content-Length": 9})
        h_list.do_POST()
        assert h_list._responses[0]["code"] == 400


def test_do_HEAD():
    h = _build_mock_handler(
        "/api/health", method="HEAD")
    h.do_HEAD()
    # HEAD uses `self.do_GET()` internally in Handler, which sets _responses
    # logic (code 200)
    assert h._responses[0]["code"] == 200
    # wfile logic inside standard lib framework differs
    # we just need to verify do_HEAD completes and handles things smoothly
    assert len(h._responses) >= 1


def test_404_not_found():
    h = _build_mock_handler("/api/unknown_endpoint", method="POST")
    h.do_POST()
    assert b"Not found" in h.wfile.getvalue()
    assert h._responses[0]["code"] == 404
