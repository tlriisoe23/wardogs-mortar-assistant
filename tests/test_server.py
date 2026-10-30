import json
import urllib.request
import urllib.error
import threading
import pytest
from server import Handler, ThreadedHTTPServer, get_vk_name, GLOBAL_PTT_WATCHER

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
        assert data["service"] == "wardogs-mortar-assistant"
        assert isinstance(data["port"], int)
        assert isinstance(data["weapons"], list)
        assert isinstance(data["maps"], list)
        assert data["tauri_v2_ready"] is True

def test_desktop_hud_get_endpoint(live_test_server):
    req = urllib.request.Request(f"{live_test_server}/api/desktop-hud")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["ok"] is True
        assert data["tauri_v2_ready"] is True
        assert "identifier" in data
        assert isinstance(data["identifier"], str)
        assert "zero_background_polling" in data
        assert type(data["zero_background_polling"]) is bool
        assert "always_on_top" in data
        assert type(data["always_on_top"]) is bool
        assert "click_through" in data
        assert type(data["click_through"]) is bool
        assert "arc_mode" in data
        assert isinstance(data["arc_mode"], str)
        assert "elevation_mils_offset" in data
        assert isinstance(data["elevation_mils_offset"], (int, float)) and type(data["elevation_mils_offset"]) is not bool
        assert "locked_grid" in data
        assert "last_action" in data
        assert "last_action_ts" in data
        assert data["last_action_ts"] is None or (isinstance(data["last_action_ts"], (int, float)) and type(data["last_action_ts"]) is not bool)
        assert "hotkeys" in data
        assert isinstance(data["hotkeys"], dict)

def test_targets_endpoint(live_test_server):
    req = urllib.request.Request(f"{live_test_server}/api/targets")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert isinstance(data, list)
        assert len(data) > 0, "Expected at least one target to run schema checks"
        assert isinstance(data[0], dict)
        assert "id" in data[0]
        assert "map" in data[0]
        assert "name" in data[0]

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
