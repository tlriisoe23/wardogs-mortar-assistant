from unittest.mock import patch, MagicMock
import urllib.request
import urllib.error
import json
import os

from ocr_sniff import extract_text_via_rapidocr, extract_text_via_ollama_vlm, extract_text_via_omniconvert  # noqa: E501


def test_extract_text_via_rapidocr_success():
    sample_ocr_text = "CL X: 78.50 Y: 69.50"
    mock_response_data = {
        "text": sample_ocr_text,
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(
        mock_response_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:  # noqa: E501
        fake_png = b"\x89PNG\r\n\x1a\nfakeimagebytes"
        result = extract_text_via_rapidocr(fake_png, filename="hud.png")

        assert mock_urlopen.called
        assert result["ok"] is True
        assert result["engine"] == "rapidocr"
        assert result["text"] == sample_ocr_text


def test_extract_text_via_rapidocr_http_error():
    class DummyHTTPError(urllib.error.HTTPError):
        def __init__(self):
            super().__init__("http://fake", 500, "Internal Error", {}, None)

        def close(self):
            self.closed = True

    err = DummyHTTPError()
    with patch("urllib.request.urlopen", side_effect=err):
        fake_png = b"\x89PNG\r\n\x1a\nfakeimagebytes"
        result = extract_text_via_rapidocr(fake_png)
        assert not result["ok"]
        assert result["error"] == "OCR extraction failed"
        assert getattr(err, 'closed', False) is True


def test_extract_text_via_rapidocr_exception():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):  # noqa: E501
        fake_png = b"\x89PNG\r\n\x1a\nfakeimagebytes"
        result = extract_text_via_rapidocr(fake_png)
        assert not result["ok"]
        assert result["error"] == "OCR extraction failed"


def test_extract_text_via_ollama_vlm_success():
    sample_ocr_text = "CL X: 78.50 Y: 69.50"
    mock_response_data = {
        "response": sample_ocr_text,
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(
        mock_response_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:  # noqa: E501
        fake_png = b"\x89PNG\r\n\x1a\nfakeimagebytes"
        result = extract_text_via_ollama_vlm(fake_png)

        assert mock_urlopen.called
        assert result["ok"] is True
        assert result["engine"] == "qwen3-vl:2b-instruct"
        assert result["text"] == sample_ocr_text


def test_extract_text_via_ollama_vlm_http_error():
    class DummyHTTPError(urllib.error.HTTPError):
        def __init__(self):
            super().__init__("http://fake", 500, "Internal Error", {}, None)

        def close(self):
            self.closed = True

    err = DummyHTTPError()
    with patch("urllib.request.urlopen", side_effect=err):
        fake_png = b"\x89PNG\r\n\x1a\nfakeimagebytes"
        result = extract_text_via_ollama_vlm(fake_png)
        assert not result["ok"]
        assert result["error"] == "OCR extraction failed"
        assert getattr(err, 'closed', False) is True


def test_extract_text_via_ollama_vlm_exception():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):  # noqa: E501
        fake_png = b"\x89PNG\r\n\x1a\nfakeimagebytes"
        result = extract_text_via_ollama_vlm(fake_png)
        assert not result["ok"]
        assert result["error"] == "OCR extraction failed"


def test_extract_text_via_omniconvert_falls_back_to_rapidocr_and_ollama():
    with patch.dict(os.environ, {"WARDOGS_ENABLE_OCR_CASCADE": "1"}):
        with patch("ocr_sniff.extract_text_via_rapidocr") as mock_rapidocr:
            mock_rapidocr.return_value = {"ok": True, "entries": [{"x": 10}]}
            result = extract_text_via_omniconvert(b"dummy")
            assert result["ok"]
            assert mock_rapidocr.called

        with patch("ocr_sniff.extract_text_via_rapidocr") as mock_rapidocr:
            mock_rapidocr.return_value = {"ok": False}
            with patch("ocr_sniff.extract_text_via_ollama_vlm") as mock_ollama:
                mock_ollama.return_value = {"ok": True, "entries": [{"x": 10}]}
                result = extract_text_via_omniconvert(b"dummy")
                assert result["ok"]
                assert mock_ollama.called

        with patch("ocr_sniff.extract_text_via_rapidocr") as mock_rapidocr:
            mock_rapidocr.return_value = {"ok": False}
            with patch("ocr_sniff.extract_text_via_ollama_vlm") as mock_ollama:
                mock_ollama.return_value = {"ok": False}
                with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("failed")) as mock_urlopen:  # noqa: E501
                    result = extract_text_via_omniconvert(b"dummy")
                    assert not result["ok"]
                    assert mock_urlopen.called
