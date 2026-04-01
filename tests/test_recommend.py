import json
import os
import tempfile
import unittest
from collections import OrderedDict
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from recommend import (
    build_inference_prompt,
    build_recommendation_prompt,
    call_openai,
    generate_recommendations,
    group_by_media_type,
    infer_taste,
    parse_response,
    read_file,
)


class TestReadFile(unittest.TestCase):
    def test_read_file_typed_format(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("film: The Godfather\n")
            f.write("music: Blonde\n")
            f.write("game: Dark Souls\n")
            f.flush()
            path = f.name
        try:
            result = read_file(path)
            self.assertEqual(result, [
                ("film", "The Godfather"),
                ("music", "Blonde"),
                ("game", "Dark Souls"),
            ])
        finally:
            os.unlink(path)

    def test_read_file_bare_item_unknown_type(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("The Godfather\n")
            f.flush()
            path = f.name
        try:
            result = read_file(path)
            self.assertEqual(result, [("unknown", "The Godfather")])
        finally:
            os.unlink(path)

    def test_read_file_normal_strips_whitespace(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("  film: The Godfather  \n")
            f.write("album: Blonde\n")
            f.flush()
            path = f.name
        try:
            result = read_file(path)
            self.assertEqual(result, [
                ("film", "The Godfather"),
                ("album", "Blonde"),
            ])
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


class TestBuildInferencePrompt(unittest.TestCase):
    def test_inference_prompt_includes_typed_likes(self):
        likes = [("film", "The Godfather"), ("game", "Dark Souls")]
        system, user = build_inference_prompt(likes)
        self.assertIn("Favourites:", user)
        self.assertIn("film: The Godfather", user)
        self.assertIn("game: Dark Souls", user)


class TestBuildRecommendationPrompt(unittest.TestCase):
    def test_recommendation_prompt_includes_taste_analysis(self):
        taste = {
            "core_dimensions": ["institutional power under moral ambiguity"],
            "resonant_qualities": ["tonal restraint"],
            "negative_space": ["commercial spectacle"],
            "discovery_leverage": "look for directors who subvert genre expectations",
        }
        likes = [("film", "The Godfather")]
        system, user = build_recommendation_prompt(taste, likes)
        self.assertIn("institutional power under moral ambiguity", system)
        self.assertIn("film: The Godfather", system)
        self.assertIn("Generate recommendations", user)

    def test_recommendation_prompt_includes_proportions(self):
        taste = {
            "core_dimensions": [],
            "resonant_qualities": [],
            "negative_space": [],
            "discovery_leverage": ".",
        }
        likes = [("film", "The Godfather"), ("film", "Parasite"), ("music", "Blonde")]
        system, user = build_recommendation_prompt(taste, likes)
        self.assertIn("Input proportions:", system)
        self.assertIn("67% film", system)
        self.assertIn("33% music", system)


class TestParseResponse(unittest.TestCase):
    def test_parse_response_plain_json(self):
        raw = '{"proportional_recommendations": [], "cross_media_recommendations": []}'
        result = parse_response(raw)
        self.assertIn("proportional_recommendations", result)

    def test_parse_response_markdown_code_block(self):
        raw = '```json\n{"proportional_recommendations": [], "cross_media_recommendations": []}\n```'
        result = parse_response(raw)
        self.assertIn("proportional_recommendations", result)

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
        recs = [{"name": "Parasite", "reason": "...", "confidence": "high"}]
        result = group_by_media_type(recs)
        self.assertIn("unknown", result)
        self.assertEqual(result["unknown"][0]["rank"], 1)


class TestCallOpenAI(unittest.TestCase):
    @patch("openai.OpenAI")
    def test_call_openai_success(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"proportional_recommendations": [], "cross_media_recommendations": []}'
        mock_client.chat.completions.create.return_value = mock_response

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            result = call_openai("system prompt", "user prompt", "gpt-4o")

        self.assertIn("proportional_recommendations", result)
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


class TestInferTaste(unittest.TestCase):
    @patch("recommend.call_openai")
    def test_infer_taste_returns_parsed_analysis(self, mock_call_openai):
        mock_call_openai.return_value = json.dumps({
            "core_dimensions": ["institutional power"],
            "resonant_qualities": ["tonal restraint"],
            "negative_space": ["commercial spectacle"],
            "discovery_leverage": "look for directors who subvert genre",
        })

        result = infer_taste([("film", "The Godfather")])

        self.assertEqual(result["core_dimensions"], ["institutional power"])
        self.assertEqual(result["discovery_leverage"], "look for directors who subvert genre")
        mock_call_openai.assert_called_once()

    @patch("recommend.call_openai")
    def test_infer_taste_missing_required_field_raises(self, mock_call_openai):
        mock_call_openai.return_value = json.dumps({
            "core_dimensions": ["institutional power"],
            # missing resonant_qualities, negative_space, discovery_leverage
        })

        with self.assertRaises(ValueError) as ctx:
            infer_taste([("film", "The Godfather")])
        self.assertIn("missing required fields", str(ctx.exception))


class TestGenerateRecommendations(unittest.TestCase):
    @patch("recommend.call_openai")
    def test_generate_recommendations_returns_tuple(self, mock_call_openai):
        mock_call_openai.return_value = json.dumps({
            "proportional_recommendations": [
                {"name": "Parasite", "media_type": "film", "reason": "...", "confidence": "high"}
            ],
            "cross_media_recommendations": [
                {"name": "The Brothers K", "media_type": "book", "reason": "...", "confidence": "high"}
            ]
        })

        taste = {
            "core_dimensions": ["institutional power"],
            "resonant_qualities": [],
            "negative_space": [],
            "discovery_leverage": ".",
        }
        proportional, cross_media = generate_recommendations(taste, [("film", "The Godfather")])

        self.assertEqual(len(proportional), 1)
        self.assertEqual(proportional[0]["name"], "Parasite")
        self.assertEqual(len(cross_media), 1)
        self.assertEqual(cross_media[0]["name"], "The Brothers K")

    @patch("recommend.call_openai")
    def test_generate_recommendations_both_empty_raises(self, mock_call_openai):
        mock_call_openai.return_value = '{"proportional_recommendations": [], "cross_media_recommendations": []}'

        taste = {
            "core_dimensions": [],
            "resonant_qualities": [],
            "negative_space": [],
            "discovery_leverage": ".",
        }

        with self.assertRaises(ValueError) as ctx:
            generate_recommendations(taste, [("film", "The Godfather")])
        self.assertIn("no recommendations", str(ctx.exception))


class TestMainUnit(unittest.TestCase):
    """Unit tests for main() error paths."""

    def _make_likes_file(self, content):
        f = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt")
        f.write(content)
        f.flush()
        return f.name

    def _cleanup(self, path):
        os.unlink(path)

    @patch("recommend.generate_recommendations")
    @patch("recommend.infer_taste")
    def test_main_two_call_flow_succeeds(self, mock_infer, mock_generate):
        mock_infer.return_value = {
            "core_dimensions": ["institutional power"],
            "resonant_qualities": [],
            "negative_space": [],
            "discovery_leverage": ".",
        }
        mock_generate.return_value = (
            [{"name": "Parasite", "media_type": "film", "reason": "...", "confidence": "high"}],
            [{"name": "The Brothers K", "media_type": "book", "reason": "...", "confidence": "high"}],
        )

        likes_path = self._make_likes_file("film: The Godfather\n")
        try:
            from recommend import main
            with patch("sys.argv", ["recommend.py", "--likes", likes_path]):
                with patch("sys.exit") as mock_exit:
                    main()
                    mock_exit.assert_not_called()
            mock_infer.assert_called_once()
            mock_generate.assert_called_once()
        finally:
            self._cleanup(likes_path)

    @patch("recommend.infer_taste")
    def test_main_infer_taste_error_exits_1(self, mock_infer):
        mock_infer.side_effect = RuntimeError("API error")
        likes_path = self._make_likes_file("film: The Godfather\n")
        try:
            from recommend import main
            with patch("sys.argv", ["recommend.py", "--likes", likes_path]):
                with patch("sys.exit") as mock_exit:
                    main()
                    mock_exit.assert_called_with(1)
        finally:
            self._cleanup(likes_path)

    @patch("recommend.generate_recommendations")
    @patch("recommend.infer_taste")
    def test_main_generate_error_exits_1(self, mock_infer, mock_generate):
        mock_infer.return_value = {
            "core_dimensions": [],
            "resonant_qualities": [],
            "negative_space": [],
            "discovery_leverage": ".",
        }
        mock_generate.side_effect = RuntimeError("API error")
        likes_path = self._make_likes_file("film: The Godfather\n")
        try:
            from recommend import main
            with patch("sys.argv", ["recommend.py", "--likes", likes_path]):
                with patch("sys.exit") as mock_exit:
                    main()
                    mock_exit.assert_called_with(1)
        finally:
            self._cleanup(likes_path)


class TestMainIntegration(unittest.TestCase):
    """Integration tests — skipped if no API key is set."""

    def setUp(self):
        self.api_key = os.environ.get("OPENAI_API_KEY")

    @unittest.skipIf(not os.environ.get("OPENAI_API_KEY"), "No API key set")
    def test_full_run_typed_likes(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("film: The Godfather\nfilm: Parasite\nmusic: Blonde\n")
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


if __name__ == "__main__":
    unittest.main()
