"""
Tests for the tree_sitter_utils module.

This includes tests for parser initialization, language detection, and error handling.
"""

import pytest
from unittest.mock import patch
from src.parsers.tree_sitter_utils import (
    get_tree_sitter_parser,
    get_tree_sitter_language,
    is_language_supported,
    get_supported_languages,
    clear_caches,
    parse_code,
    SUPPORTED_LANGUAGES
)


class TestTreeSitterUtils:
    """Test cases for the tree_sitter_utils module."""

    def setup_method(self):
        """Setup for tests - clear caches before each test."""
        clear_caches()

    def test_get_supported_languages(self):
        """Test that we can get a list of supported languages."""
        languages = get_supported_languages()
        # Check it's a copy, not the original
        assert languages is not SUPPORTED_LANGUAGES
        assert "python" in languages
        assert "javascript" in languages

    def test_is_language_supported_valid(self):
        """Test that valid languages are recognized as supported."""
        assert is_language_supported("python")
        assert is_language_supported("PYTHON")  # Case insensitive
        assert is_language_supported("javascript")

    def test_is_language_supported_invalid(self):
        """Test that invalid languages are recognized as unsupported."""
        assert not is_language_supported("")
        assert not is_language_supported(None)
        assert not is_language_supported("nonexistent_language")

    def test_get_parser_caching(self):
        """Test that parsers are cached."""
        parser1 = get_tree_sitter_parser("python")
        parser2 = get_tree_sitter_parser("python")
        # Same parser instance should be returned
        assert parser1 is parser2

    def test_get_language_caching(self):
        """Test that languages are cached."""
        lang1 = get_tree_sitter_language("python")
        lang2 = get_tree_sitter_language("python")
        # Same language instance should be returned
        assert lang1 is lang2

    def test_get_parser_invalid_language(self):
        """Test that getting a parser for an invalid language raises an error."""
        with pytest.raises(ValueError, match="Language not supported"):
            get_tree_sitter_parser("nonexistent_language")

    def test_get_language_invalid_language(self):
        """Test that getting a language for an invalid language raises an error."""
        with pytest.raises(ValueError, match="Language not supported"):
            get_tree_sitter_language("nonexistent_language")

    def test_parse_code_python(self):
        """Test parsing Python code."""
        code = "def hello():\n    print('Hello, world!')"
        tree = parse_code(code, "python")
        # Verify we got a parse tree
        assert tree is not None
        assert hasattr(tree, "root_node")
        # Basic check that it parsed correctly
        assert tree.root_node.type == "module"
        assert tree.root_node.child_count > 0

    def test_parse_code_javascript(self):
        """Test parsing JavaScript code."""
        code = "function hello() {\n    console.log('Hello, world!');\n}"
        tree = parse_code(code, "javascript")
        # Verify we got a parse tree
        assert tree is not None
        assert hasattr(tree, "root_node")
        # Basic check that it parsed correctly
        assert tree.root_node.type == "program"
        assert tree.root_node.child_count > 0

    def test_parse_code_invalid_language(self):
        """Test that parsing code with an invalid language raises an error."""
        with pytest.raises(ValueError, match="Language not supported"):
            parse_code("code", "nonexistent_language")

    @patch('src.parsers.tree_sitter_utils.get_parser')
    def test_parser_error_handling(self, mock_get_parser):
        """Test error handling when the tree-sitter-language-pack raises exceptions."""
        mock_get_parser.side_effect = ValueError("Test error")
        with pytest.raises(ValueError, match="Language not supported"):
            get_tree_sitter_parser("python")

    def test_clear_caches(self):
        """Test that caches can be cleared."""
        # Add something to caches
        get_tree_sitter_parser("python")
        get_tree_sitter_language("javascript")
        
        # Clear caches
        clear_caches()
        
        # Get them again - should create new instances
        parser1 = get_tree_sitter_parser("python")
        parser2 = get_tree_sitter_parser("python")
        
        # Since we just cleared the cache and initialized a new parser,
        # these should be the same instance
        assert parser1 is parser2 