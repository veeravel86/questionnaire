import unittest
import re
import json


def _extract_json(s: str) -> dict:
    """Copy of the _extract_json function from app.py for testing"""
    s = s.strip()
    s = re.sub(r"^```(?:json)?\\s*|```$", "", s, flags=re.IGNORECASE|re.MULTILINE).strip()
    if "{" in s and "}" in s:
        s = s[s.find("{"): s.rfind("}")+1]
    try:
        return json.loads(s)
    except Exception:
        return {"score": None, "reasoning": s}


class TestExtractJson(unittest.TestCase):
    
    def test_valid_json(self):
        """Test extracting valid JSON"""
        input_str = '{"score": 8, "reasoning": "Good answer"}'
        result = _extract_json(input_str)
        self.assertEqual(result["score"], 8)
        self.assertEqual(result["reasoning"], "Good answer")
    
    def test_json_with_code_fences(self):
        """Test extracting JSON wrapped in markdown code fences"""
        input_str = '```json\n{"score": 7, "reasoning": "Decent work"}\n```'
        result = _extract_json(input_str)
        self.assertEqual(result["score"], 7)
        self.assertEqual(result["reasoning"], "Decent work")
    
    def test_invalid_json(self):
        """Test handling of invalid JSON returns fallback format"""
        input_str = "This is not valid JSON at all"
        result = _extract_json(input_str)
        self.assertIsNone(result["score"])
        self.assertEqual(result["reasoning"], "This is not valid JSON at all")
    
    def test_partial_json_extraction(self):
        """Test extracting JSON from text with extra content"""
        input_str = 'Here is the evaluation: {"score": 9, "reasoning": "Excellent"} and some extra text'
        result = _extract_json(input_str)
        self.assertEqual(result["score"], 9)
        self.assertEqual(result["reasoning"], "Excellent")


if __name__ == '__main__':
    unittest.main()