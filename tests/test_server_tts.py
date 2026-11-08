import sys
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from server import generate_neural_tts

def test_generate_neural_tts_fallback(caplog):
    # Mocking missing modules to force fallbacks
    with patch.dict(sys.modules, {'edge_tts': None, 'gtts': None}):
        result = asyncio.run(generate_neural_tts("Hello", "en-US-ChristopherNeural"))

        assert result is not None
        assert isinstance(result, bytes)
        assert result.startswith(b"RIFF")
        assert b"WAVE" in result

        assert "[TTS Warning] edge_tts failed" in caplog.text
        assert "[TTS Warning] gTTS failed" in caplog.text


def test_generate_neural_tts_upstream_timeout_recovery(caplog):
    async def hanging_stream():
        await asyncio.sleep(20.0)
        yield {"type": "audio", "data": b""}

    mock_communicate_class = MagicMock()
    mock_communicate = MagicMock()
    mock_communicate.stream = hanging_stream
    mock_communicate_class.return_value = mock_communicate

    def hanging_gtts(*args, **kwargs):
        async def slow():
            await asyncio.sleep(20.0)
        asyncio.run(slow())

    mock_edge_tts = MagicMock()
    mock_edge_tts.Communicate = mock_communicate_class

    mock_gtts = MagicMock()
    mock_gtts.gTTS = MagicMock(side_effect=hanging_gtts)

    with patch.dict(sys.modules, {'edge_tts': mock_edge_tts, 'gtts': mock_gtts}):
        # Mock wait_for so we don't actually wait for 12 seconds in unit tests
        # We need to correctly handle the coroutines being passed to wait_for so they are properly exhausted and closed.
        original_wait_for = asyncio.wait_for

        async def mock_wait_for(fut, timeout):
            try:
                # Ensure the original fut is closed if it's a coroutine to prevent "was never awaited" warnings
                if asyncio.iscoroutine(fut):
                    fut.close()
            except Exception:
                pass
            raise asyncio.TimeoutError("timeout")

        with patch('asyncio.wait_for', side_effect=mock_wait_for):
            result = asyncio.run(generate_neural_tts("Hello", "en-US-ChristopherNeural"))

            assert result is not None
            assert isinstance(result, bytes)
            assert result.startswith(b"RIFF")
            assert b"WAVE" in result

            assert "[TTS Timeout] edge-tts stream exceeded timeout" in caplog.text
            assert "[TTS Warning] gTTS failed" in caplog.text
