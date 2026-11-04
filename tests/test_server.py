import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from unittest import mock

import pytest

from server import Handler, ThreadedHTTPServer, get_vk_name


@pytest.fixture(autouse=True)
def _no_side_effects(monkeypatch):
    """Globally mock all host integrations."""
    monkeypatch.setattr(
        'server.generate_neural_tts',
        mock.AsyncMock(return_value=b'RIFF_wav_dataWAVE'))

    mock_ptt = mock.MagicMock()
    mock_ptt.get_status.return_value = {
        'enabled': True, 'vk': 0x14, 'binding_mode': False
    }
    monkeypatch.setattr('server.GLOBAL_PTT_WATCHER', mock_ptt)

    mock_ocr = mock.MagicMock()
    mock_ocr.running = True
    mock_ocr.recent_events = []
    mock_ocr.get_status.return_value = {
        'running': True, 'recent_events': []
    }
    monkeypatch.setattr('server.GLOBAL_OCR_WATCHER', mock_ocr)

    monkeypatch.setattr('server.capture_and_scan_entries',
                        mock.MagicMock(
                            return_value=[{"x": 1, "y": 2,
                                           "role": "test",
                                           "raw_line": "test"}]))


@pytest.fixture(scope="module")
def live_test_server():
    httpd = ThreadedHTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    try:
        yield base_url
    finally:
        httpd.shutdown()
        httpd.server_close()


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
    from server import DIRECTORY

    targets_file = os.path.join(DIRECTORY, 'data', 'targets.json')

    with open(targets_file, 'rb') as f:
        original_content = f.read()

    try:
        req = urllib.request.Request(f"{live_test_server}/api/targets")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            data1 = json.loads(resp.read().decode("utf-8"))

        req = urllib.request.Request(f"{live_test_server}/api/targets")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            data2 = json.loads(resp.read().decode("utf-8"))

        assert data1 == data2

        new_data = [{"id": "test_modified", "map": "test", "name": "test",
                     "category": "chokepoint", "x": 0, "y": 0, "notes": "",
                     "voice_triggers": []}]
        with open(targets_file, 'w') as f:
            json.dump(new_data, f)

        req = urllib.request.Request(f"{live_test_server}/api/targets")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            data3 = json.loads(resp.read().decode("utf-8"))

        assert data3 == new_data

    finally:
        with open(targets_file, 'wb') as f:
            f.write(original_content)
        os.utime(targets_file, None)


def test_targets_invalidate(live_test_server):
    from server import DIRECTORY

    targets_file = os.path.join(DIRECTORY, 'data', 'targets.json')
    with open(targets_file, 'rb') as f:
        original_content = f.read()

    try:
        req = urllib.request.Request(f"{live_test_server}/api/targets")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            data1 = json.loads(resp.read().decode("utf-8"))

        new_data = [{"id": "cache_test", "map": "test", "name": "cache test",
                     "category": "test", "x": 10, "y": 20, "notes": "",
                     "voice_triggers": []}]
        with open(targets_file, 'w') as f:
            json.dump(new_data, f)

        req2 = urllib.request.Request(f"{live_test_server}/api/targets")
        with urllib.request.urlopen(req2, timeout=5) as resp:
            assert resp.status == 200
            data2 = json.loads(resp.read().decode("utf-8"))

        assert data1 != data2
        assert data2 == new_data

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
        os.utime(targets_file, None)


def test_ptt_config_endpoint(live_test_server):
    req = urllib.request.Request(
        f"{live_test_server}/api/ptt/config?enabled=true&vk=0x14")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["enabled"] is True
        assert data["vk"] == 0x14


def test_ptt_bind_endpoint(live_test_server, monkeypatch):
    ptt_watcher = mock.MagicMock()
    ptt_watcher.get_status.return_value = {
        'enabled': True, 'vk': 0x14, 'binding_mode': True}
    monkeypatch.setattr('server.GLOBAL_PTT_WATCHER', ptt_watcher)
    req = urllib.request.Request(f"{live_test_server}/api/ptt/bind")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["binding_mode"] is True


def test_desktop_hud_post_various_actions(live_test_server):
    actions = [
        ({"action": "elev_down", "step_mils": 5}, "elev_down"),
        ({"action": "toggle_arc"}, "toggle_arc"),
        ({"action": "toggle_click_through"}, "toggle_click_through"),
        ({"action": "lock_target", "grid": "1234"}, "lock_target"),
        ({"action": "reset_target"}, "reset_target")
    ]
    for payload, expected_action in actions:
        req = urllib.request.Request(
            f"{live_test_server}/api/desktop-hud",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["last_action"] == expected_action


def test_ocr_status_endpoint(live_test_server):
    req = urllib.request.Request(f"{live_test_server}/api/ocr/status")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "running" in data
        assert "recent_events" in data


def test_api_tts_endpoint_missing_text(live_test_server):
    try:
        req = urllib.request.Request(f"{live_test_server}/api/tts")
        with urllib.request.urlopen(req, timeout=5):
            pass
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        assert getattr(e, "code", None) == 400


def test_api_tts_endpoint_text_too_long(live_test_server):
    try:
        long_text = "a" * 1001
        req = urllib.request.Request(
            f"{live_test_server}/api/tts?text={long_text}")
        with urllib.request.urlopen(req, timeout=5):
            pass
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        assert getattr(e, "code", None) == 413


def test_api_tts_endpoint_success(live_test_server):
    text = urllib.parse.quote("Hello")
    req = urllib.request.Request(f"{live_test_server}/api/tts?text={text}")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        assert resp.headers.get('Content-Type') in ('audio/wav', 'audio/mpeg')
        data = resp.read()
        assert data.startswith(b'RIFF')
        assert b'WAVE' in data


def test_ocr_toggle_endpoint(live_test_server):
    req = urllib.request.Request(
        f"{live_test_server}/api/ocr/toggle?enabled=true")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "running" in data


def test_ocr_toggle_endpoint_various_states(live_test_server):
    states = ["on", "off", ""]
    for state in states:
        req = urllib.request.Request(
            f"{live_test_server}/api/ocr/toggle?state={state}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert "running" in data


def test_ocr_scan_once_endpoint(live_test_server):
    req = urllib.request.Request(f"{live_test_server}/api/ocr/scan_once")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "found" in data
        assert "coords" in data


def test_ocr_extract_image_endpoint_large_payload(live_test_server):
    try:
        req = urllib.request.Request(
            f"{live_test_server}/api/ocr/extract-image",
            data=b"a" * (11 * 1024 * 1024),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5):
            pass
    except (urllib.error.HTTPError, urllib.error.URLError):
        pass


def test_ocr_extract_image_endpoint_invalid_payloads(live_test_server):
    invalid_payloads = [
        (b"not json", 400),
        (b'["not a dict"]', 400),
        (json.dumps({"wrong_key": "data"}).encode('utf-8'), 400),
        (json.dumps({"image_base64": ""}).encode('utf-8'), 400),
    ]
    for data, expected_code in invalid_payloads:
        try:
            req = urllib.request.Request(
                f"{live_test_server}/api/ocr/extract-image",
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5):
                pass
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            assert getattr(e, "code", None) == expected_code


def test_ocr_extract_image_endpoint_valid(live_test_server, monkeypatch):
    import base64
    valid_payload = {
        "image_base64": base64.b64encode(b"fake_image_bytes").decode("utf-8"),
        "filename": "test.png",
        "mode": "test"
    }
    mock_extract = mock.MagicMock(return_value={"ok": True, "entries": [
                                  {"x": 1, "y": 2, "role": "test",
                                   "raw_line": "test"}]})
    monkeypatch.setattr('server.extract_text_via_omniconvert', mock_extract)
    req = urllib.request.Request(
        f"{live_test_server}/api/ocr/extract-image",
        data=json.dumps(valid_payload).encode('utf-8'),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["ok"] is True
        assert "entries" in data


def test_server_do_head(live_test_server):
    req = urllib.request.Request(
        f"{live_test_server}/api/health",
        method="HEAD")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        assert not resp.read()


def test_do_post_not_found(live_test_server):
    try:
        req = urllib.request.Request(
            f"{live_test_server}/api/missing",
            data=b"{}",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5):
            pass
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        assert getattr(e, "code", None) == 404


def test_api_tts_endpoint_timeout(live_test_server, monkeypatch):
    import asyncio
    monkeypatch.setattr(
        'server.generate_neural_tts',
        mock.AsyncMock(
            side_effect=asyncio.TimeoutError))
    text = urllib.parse.quote("Hello")
    req = urllib.request.Request(f"{live_test_server}/api/tts?text={text}")
    try:
        with urllib.request.urlopen(req, timeout=5):
            pass
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        assert getattr(e, "code", None) == 504


def test_api_tts_endpoint_exception(live_test_server, monkeypatch):
    monkeypatch.setattr(
        'server.generate_neural_tts', mock.AsyncMock(
            side_effect=Exception("Test TTS Error")))
    text = urllib.parse.quote("Hello")
    req = urllib.request.Request(f"{live_test_server}/api/tts?text={text}")
    try:
        with urllib.request.urlopen(req, timeout=5):
            pass
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        assert getattr(e, "code", None) == 500


def test_do_post_invalid_json(live_test_server):
    try:
        req = urllib.request.Request(
            f"{live_test_server}/api/desktop-hud",
            data=b"invalid json",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5):
            pass
    except (urllib.error.HTTPError, urllib.error.URLError):
        assert False, "Should fallback to empty dict, not raise HTTP error"


def test_do_post_desktop_hud_step_value_error(live_test_server):
    payload = {"action": "elev_up", "step_mils": "not an int"}
    req = urllib.request.Request(
        f"{live_test_server}/api/desktop-hud",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["last_action"] == "elev_up"


def test_server_do_get_internal_error(live_test_server, monkeypatch):
    monkeypatch.setattr('server.Handler._do_GET_inner',
                        mock.MagicMock(side_effect=Exception("Test Error")))
    req = urllib.request.Request(f"{live_test_server}/api/health")
    try:
        with urllib.request.urlopen(req, timeout=5):
            pass
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        assert getattr(e, "code", None) == 500


def test_server_do_post_internal_error(live_test_server, monkeypatch):
    monkeypatch.setattr('server.urllib.parse.urlparse',
                        mock.MagicMock(side_effect=Exception("Test Error")))
    req = urllib.request.Request(
        f"{live_test_server}/api/desktop-hud",
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5):
            pass
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        assert getattr(e, "code", None) == 500
