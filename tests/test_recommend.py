import json
import os
import tempfile
import unittest
from collections import OrderedDict
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from recommend import (
    build_prompt,
    call_openai,
    group_by_media_type,
    parse_response,
    read_file,
)


class TestReadFile(unittest.TestCase):
    def test_read_file_normal(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("The Godfather\n")
            f.write("  Dark Souls  \n")
            f.write("Blonde\n")
            f.flush()
            path = f.name
        try:
            result = read_file(path)
            self.assertEqual(result, ["The Godfather", "Dark Souls", "Blonde"])
        finally:
            os.unlink(path)

    def test_read_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            read_file("/nonexistent/path/to/file.txt")

    def test_read_file_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("\n\n   \n")
            f.flush()
            path = f.name
        try:
            result = read_file(path)
            self.assertEqual(result, [])
        finally:
            os.unlink(path)


class TestBuildPrompt(unittest.TestCase):
    def test_build_prompt_likes_only(self):
        system, user = build_prompt(["The Godfather", "Dark Souls"])
        self.assertIn("The Godfather, Dark Souls", system)
        self.assertIn("The Godfather, Dark Souls", user)
        # Dislikes should be "none" in the prompt
        self.assertIn("none", user.lower())

    def test_build_prompt_with_dislikes(self):
        system, user = build_prompt(
            ["The Godfather"],
            ["Fast & Furious"]
        )
        self.assertIn("The Godfather", system)
        self.assertIn("Fast & Furious", system)
        self.assertIn("The Godfather", user)
        self.assertIn("Fast & Furious", user)


class TestParseResponse(unittest.TestCase):
    def test_parse_response_plain_json(self):
        raw = '{"recommendations": [{"name": "Parasite", "media_type": "film"}]}'
        result = parse_response(raw)
        self.assertEqual(result["recommendations"][0]["name"], "Parasite")

    def test_parse_response_markdown_code_block(self):
        raw = '```json\n{"recommendations": [{"name": "Parasite", "media_type": "film"}]}\n```'
        result = parse_response(raw)
        self.assertEqual(result["recommendations"][0]["name"], "Parasite")

    def test_parse_response_invalid_json(self):
        raw = "this is not json"
        with self.assertRaises(ValueError) as ctx:
            parse_response(raw)
        self.assertIn("Failed to parse JSON", str(ctx.exception))


class TestGroupByMediaType(unittest.TestCase):
    def test_group_by_media_type_normal(self):
        recs = [
            {"name": "Parasite", "media_type": "film", "reason": "...", "confidence": "high"},
            {"name": "Oppenheimer", "media_type": "film", "reason": "...", "confidence": "medium"},
            {"name": "The Brothers K", "media_type": "book", "reason": "...", "confidence": "high"},
        ]
        result = group_by_media_type(recs)
        self.assertIsInstance(result, OrderedDict)
        self.assertEqual(len(result), 2)
        self.assertEqual(result["film"][0]["rank"], 1)
        self.assertEqual(result["film"][1]["rank"], 2)
        self.assertEqual(result["book"][0]["rank"], 1)

    def test_group_by_media_type_empty(self):
        result = group_by_media_type([])
        self.assertEqual(result, OrderedDict())


class TestCallOpenAI(unittest.TestCase):
    @patch("openai.OpenAI")
    def test_call_openai_success(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"recommendations": []}'
        mock_client.chat.completions.create.return_value = mock_response

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            result = call_openai("system prompt", "user prompt", "gpt-4o")

        self.assertEqual(result, '{"recommendations": []}')
        mock_client.chat.completions.create.assert_called_once()

    @patch("openai.OpenAI")
    def test_call_openai_api_error(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API error: bad request")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with self.assertRaises(Exception) as ctx:
                call_openai("system prompt", "user prompt", "gpt-4o")

        self.assertIn("API error", str(ctx.exception))

    def test_call_openai_missing_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                call_openai("system prompt", "user prompt")
        self.assertIn("OPENAI_API_KEY is not set", str(ctx.exception))


class TestMainIntegration(unittest.TestCase):
    """Integration tests — skipped if no API key is set."""

    def setUp(self):
        self.api_key = os.environ.get("OPENAI_API_KEY")

    @unittest.skipIf(not os.environ.get("OPENAI_API_KEY"), "No API key set")
    def test_full_run_likes_only(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("The Godfather\nBlonde\n")
            f.flush()
            likes_path = f.name

        try:
            from recommend import main
            with patch("sys.argv", ["recommend.py", "--likes", likes_path]):
                with patch("sys.exit") as mock_exit:
                    main()
                    mock_exit.assert_not_called()
        finally:
            os.unlink(likes_path)

    @unittest.skipIf(not os.environ.get("OPENAI_API_KEY"), "No API key set")
    def test_full_run_likes_dislikes(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("The Godfather\nBlonde\n")
            f.flush()
            likes_path = f.name

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("Fast & Furious\n")
            f.flush()
            dislikes_path = f.name

        try:
            from recommend import main
            with patch("sys.argv", ["recommend.py", "--likes", likes_path, "--dislikes", dislikes_path]):
                with patch("sys.exit") as mock_exit:
                    main()
                    mock_exit.assert_not_called()
        finally:
            os.unlink(likes_path)
            os.unlink(dislikes_path)


if __name__ == "__main__":
    unittest.main()
