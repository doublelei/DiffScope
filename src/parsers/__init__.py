"""
Parser modules for DiffScope.

This package contains modules for parsing code and detecting function boundaries
using Tree-sitter and other parsing techniques.
"""

from .function_parser import (
    parse_functions,
    get_function_at_line,
    extract_function_content
)
from .tree_sitter_utils import (
    get_tree_sitter_parser,
    get_tree_sitter_language,
    is_language_supported
)

__all__ = [
    'parse_functions',
    'get_function_at_line',
    'extract_function_content',
    'get_tree_sitter_parser',
    'get_tree_sitter_language',
    'is_language_supported'
]
