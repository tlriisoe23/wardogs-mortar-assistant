import os
import urllib.error
import builtins
from unittest.mock import patch, MagicMock
from ocr_sniff import extract_text_via_rapidocr, extract_text_via_ollama_vlm, extract_text_via_omniconvert

def test_extract_text_via_rapidocr_upstream_failure_closes_fp():
    mock_fp = MagicMock()
    mock_err = urllib.error.HTTPError(
        url="http://fake",
        code=503,
        msg="Service Unavailable",
        hdrs={},
        fp=mock_fp
    )

    with patch("urllib.request.urlopen", side_effect=mock_err):
        result = extract_text_via_rapidocr(b"dummy_bytes")
        assert result["ok"] is False
        assert result["engine"] == "rapidocr"
        assert result["entries"] == []
        mock_fp.close.assert_called_once()

def test_extract_text_via_ollama_vlm_upstream_failure_closes_fp():
    mock_fp = MagicMock()
    mock_err = urllib.error.HTTPError(
        url="http://fake",
        code=503,
        msg="Service Unavailable",
        hdrs={},
        fp=mock_fp
    )

    with patch("urllib.request.urlopen", side_effect=mock_err):
        result = extract_text_via_ollama_vlm(b"dummy_bytes")
        assert result["ok"] is False
        assert result["engine"] == "qwen3-vl:2b-instruct"
        assert result["entries"] == []
        mock_fp.close.assert_called_once()

def test_ocr_cascade_fallback_recovery():
    """
    Test that when WARDOGS_ENABLE_OCR_CASCADE=1 is set,
    if RapidOCR fails, it falls back to Ollama, and if Ollama fails, it falls back to OmniConvert.
    """
    mock_omniconvert_resp = MagicMock()
    mock_omniconvert_resp.read.return_value = b'{"text": "omniconvert fallback success", "engine": "omniconvert", "ok": true}'
    mock_omniconvert_resp.__enter__.return_value = mock_omniconvert_resp
    mock_omniconvert_resp.__exit__.return_value = None

    with patch("ocr_sniff.extract_text_via_rapidocr", return_value={"ok": False, "entries": []}) as mock_rapid:
        with patch("ocr_sniff.extract_text_via_ollama_vlm", return_value={"ok": False, "entries": []}) as mock_ollama:
            with patch("urllib.request.urlopen", return_value=mock_omniconvert_resp) as mock_urlopen:

                original_hasattr = builtins.hasattr
                def custom_hasattr(obj, attr):
                    # In ocr_sniff.py, we check `if not hasattr(urllib.request.urlopen, "_mock_name")`
                    if obj is mock_urlopen and attr == "_mock_name":
                        return False
                    return original_hasattr(obj, attr)

                with patch("builtins.hasattr", side_effect=custom_hasattr):
                    with patch.dict(os.environ, {"WARDOGS_ENABLE_OCR_CASCADE": "1"}):
                        result = extract_text_via_omniconvert(b"dummy_bytes")

                        assert mock_rapid.called
                        assert mock_ollama.called
                        assert mock_urlopen.called

                        assert result["ok"] is True
                        assert result["engine"] == "omniconvert"
                        assert result["text"] == "omniconvert fallback success"
