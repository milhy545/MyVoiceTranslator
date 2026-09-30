import unittest
from unittest.mock import patch, MagicMock
from interview_shield.stt import WhisperTranscriber

class TestWhisperTranscriber(unittest.TestCase):
    @patch('interview_shield.stt.WhisperModel')
    def test_close_cleans_up_model(self, mock_model_cls):
        mock_model = MagicMock()
        mock_model_cls.return_value = mock_model
        
        transcriber = WhisperTranscriber(model_name="tiny.en", requested_device="cpu", compute_type="int8")
        self.assertIsNotNone(transcriber.model)
        
        transcriber.close()
        
        self.assertIsNone(transcriber.model)

if __name__ == '__main__':
    unittest.main()
