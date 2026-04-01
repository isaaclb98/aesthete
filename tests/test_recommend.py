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

    def test_group_by_media_type_missing_media_type_key(self):
        recs = [
            {"name": "Parasite", "reason": "...", "confidence": "high"},
        ]
        result = group_by_media_type(recs)
        self.assertIn("unknown", result)
        self.assertEqual(result["unknown"][0]["rank"], 1)


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


class TestMainUnit(unittest.TestCase):
    """Unit tests for main() error paths — no API calls needed."""

    def _make_likes_file(self, content):
        f = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt")
        f.write(content)
        f.flush()
        return f.name

    def _cleanup(self, path):
        os.unlink(path)

    @patch("recommend.call_openai")
    def test_main_dislikes_file_missing_proceeds(self, mock_call_openai):
        mock_call_openai.return_value = '{"recommendations": [{"name": "X", "media_type": "film", "reason": "y", "confidence": "high"}]}'
        likes_path = self._make_likes_file("The Godfather\n")
        try:
            from recommend import main
            with patch("sys.argv", ["recommend.py", "--likes", likes_path, "--dislikes", "/nonexistent/file.txt"]):
                with patch("sys.exit") as mock_exit:
                    main()
                    mock_exit.assert_not_called()
            # Verify call_openai was invoked (dislikes missing file was skipped)
            mock_call_openai.assert_called_once()
        finally:
            self._cleanup(likes_path)

    @patch("recommend.call_openai")
    def test_main_api_error_exits_1(self, mock_call_openai):
        mock_call_openai.side_effect = RuntimeError("API error")
        likes_path = self._make_likes_file("The Godfather\n")
        try:
            from recommend import main
            with patch("sys.argv", ["recommend.py", "--likes", likes_path]):
                with patch("sys.exit") as mock_exit:
                    main()
                    mock_exit.assert_called_with(1)
        finally:
            self._cleanup(likes_path)

    @patch("recommend.call_openai")
    def test_main_json_parse_error_exits_1(self, mock_call_openai):
        mock_call_openai.return_value = "not json at all"
        likes_path = self._make_likes_file("The Godfather\n")
        try:
            from recommend import main
            with patch("sys.argv", ["recommend.py", "--likes", likes_path]):
                with patch("sys.exit") as mock_exit:
                    main()
                    mock_exit.assert_called_with(1)
        finally:
            self._cleanup(likes_path)

    @patch("recommend.call_openai")
    def test_main_empty_recommendations_raises(self, mock_call_openai):
        mock_call_openai.return_value = '{"recommendations": []}'
        likes_path = self._make_likes_file("The Godfather\n")
        try:
            from recommend import main
            with patch("sys.argv", ["recommend.py", "--likes", likes_path]):
                with self.assertRaises(ValueError) as ctx:
                    main()
                self.assertIn("no recommendations", str(ctx.exception))
        finally:
            self._cleanup(likes_path)


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
