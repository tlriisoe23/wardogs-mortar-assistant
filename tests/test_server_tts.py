import sys
import asyncio
from unittest.mock import patch
from server import generate_neural_tts

def test_generate_neural_tts_fallback(capsys):
    # Mocking missing modules to force fallbacks
    with patch.dict(sys.modules, {'edge_tts': None, 'gtts': None}):
        result = asyncio.run(generate_neural_tts("Hello", "en-US-ChristopherNeural"))

        assert result is not None
        assert isinstance(result, bytes)
        assert result.startswith(b"RIFF")
        assert b"WAVE" in result

        captured = capsys.readouterr()
        assert "[TTS Warning] edge_tts failed" in captured.out
        assert "[TTS Warning] gTTS failed" in captured.out
