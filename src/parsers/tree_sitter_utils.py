"""
Tree-sitter integration utilities for parsing code and detecting languages.

This module provides functions to interact with the tree-sitter-language-pack 
for parsing and analyzing code in different programming languages.
"""

from typing import Dict, List, Optional, Any
from tree_sitter_language_pack import get_language, get_parser

# Cache for initialized parsers and languages
_parsers: Dict[str, Any] = {}
_languages: Dict[str, Any] = {}

# List of languages with verified function detection support
SUPPORTED_LANGUAGES = ['python', 'javascript']


def get_tree_sitter_parser(language: str) -> Any:
    """
    Get a tree-sitter parser for the specified language.
    
    Args:
        language: Language name (e.g. 'python', 'javascript')
        
    Returns:
        Tree-sitter parser
        
    Raises:
        ValueError: If the language is not supported
    """
    language = language.lower()
    if language not in _parsers:
        try:
            _parsers[language] = get_parser(language)
        except (ValueError, KeyError, LookupError) as e:
            raise ValueError(f"Language not supported: {language}") from e
    
    return _parsers[language]


def get_tree_sitter_language(language: str) -> Any:
    """
    Get a tree-sitter language for the specified language.
    
    Args:
        language: Language name (e.g. 'python', 'javascript')
        
    Returns:
        Tree-sitter language
        
    Raises:
        ValueError: If the language is not supported
    """
    language = language.lower()
    if language not in _languages:
        try:
            _languages[language] = get_language(language)
        except (ValueError, KeyError, LookupError) as e:
            raise ValueError(f"Language not supported: {language}") from e
    
    return _languages[language]


def is_language_supported(language: str) -> bool:
    """
    Check if a language is supported by tree-sitter and our function detection.
    
    Args:
        language: Language name
        
    Returns:
        True if language is supported, False otherwise
    """
    if not language:
        return False
        
    # First check our verified supported languages
    language = language.lower()
    if language in SUPPORTED_LANGUAGES:
        return True
        
    # Then try to get the parser to see if tree-sitter supports it
    # (even if we don't have function queries for it yet)
    try:
        get_language(language)
        return True
    except (ValueError, KeyError, LookupError, ModuleNotFoundError):
        return False


def get_supported_languages() -> List[str]:
    """
    Get a list of languages supported for function detection.
    
    Returns:
        List of supported language names
    """
    return SUPPORTED_LANGUAGES.copy()


def clear_caches() -> None:
    """
    Clear the parser and language caches.
    Useful for testing and managing memory.
    """
    _parsers.clear()
    _languages.clear()


def parse_code(code: str, language: str) -> Any:
    """
    Parse source code using a tree-sitter parser.
    
    Args:
        code: Source code to parse
        language: Programming language of the code
        
    Returns:
        Tree-sitter parse tree
        
    Raises:
        ValueError: If the language is not supported
    """
    parser = get_tree_sitter_parser(language)
    return parser.parse(bytes(code, 'utf8')) 