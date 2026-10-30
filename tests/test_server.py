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


def test_ptt_config_endpoint(live_test_server):
    # Get initial state
    req_init = urllib.request.Request(f"{live_test_server}/api/ptt/status")
    with urllib.request.urlopen(req_init, timeout=5) as resp:
        init_data = json.loads(resp.read().decode("utf-8"))
        orig_vk = init_data.get("vk", 0)

    try:
        req = urllib.request.Request(
            f"{live_test_server}/api/ptt/config?enabled=on&vk=0x42"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["enabled"] is True
            assert data["vk"] == 0x42
    finally:
        req_restore = urllib.request.Request(
            f"{live_test_server}/api/ptt/config?enabled=off&vk={orig_vk}"
        )
        with urllib.request.urlopen(req_restore, timeout=5) as resp:
            pass


def test_ptt_bind_endpoint(live_test_server):
    req = urllib.request.Request(f"{live_test_server}/api/ptt/bind")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "enabled" in data


def test_ocr_status_endpoint(live_test_server):
    req = urllib.request.Request(f"{live_test_server}/api/ocr/status")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "running" in data


def test_ocr_toggle_endpoint(live_test_server):
    try:
        req = urllib.request.Request(
            f"{live_test_server}/api/ocr/toggle?state=on"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert "running" in data
    finally:
        req_restore = urllib.request.Request(
            f"{live_test_server}/api/ocr/toggle?state=off"
        )
        with urllib.request.urlopen(req_restore, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["running"] is False


def test_targets_endpoint(live_test_server):
    req = urllib.request.Request(f"{live_test_server}/api/targets")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        assert resp.getheader('Content-Type') == 'application/json'


def test_tts_missing_text(live_test_server):
    req = urllib.request.Request(f"{live_test_server}/api/tts")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=5)
    e = exc_info.value
    assert e.code == 400
    data = json.loads(e.read().decode("utf-8"))
    assert "error" in data
    e.close()


def test_ocr_extract_image_payload_too_large(live_test_server):
    req = urllib.request.Request(
        f"{live_test_server}/api/ocr/extract-image",
        data=b"a" * (10 * 1024 * 1024 + 1),
        headers={"Content-Length": str(10 * 1024 * 1024 + 1)}
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        pytest.fail("Expected HTTPError or URLError")
    except urllib.error.HTTPError as e:
        assert e.code == 413
        e.close()
    except urllib.error.URLError as e:
        if not isinstance(e.reason, (ConnectionResetError, BrokenPipeError)):
            import pytest
            pytest.fail(
                f"Expected ConnectionResetError or BrokenPipeError, "
                f"got: {e.reason}"
            )
        pass


def test_ocr_extract_image_invalid_json(live_test_server):
    req = urllib.request.Request(
        f"{live_test_server}/api/ocr/extract-image",
        data=b"invalid json",
        headers={"Content-Length": "12"}
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=5)
    e = exc_info.value
    assert e.code == 400
    e.close()


def test_desktop_hud_post_various_actions(live_test_server):
    actions = [
        "elev_down", "toggle_arc", "toggle_click_through",
        "lock_target", "reset_target"
    ]
    for action in actions:
        payload = {"action": action, "step_mils": 5, "grid": "TEST_GRID"}
        req = urllib.request.Request(
            f"{live_test_server}/api/desktop-hud",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["last_action"] == action
