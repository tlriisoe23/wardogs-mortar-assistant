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
    import os, time
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
        new_data = [{"id": "test_modified", "map": "test", "name": "test", "category": "chokepoint", "x": 0, "y": 0, "notes": "", "voice_triggers": []}]
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
