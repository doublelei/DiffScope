"""
Utility modules for DiffScope.

This package contains utility modules for working with GitHub API, 
parsing diffs, and other support functions.
"""

from .github_api import (
    parse_github_url,
    get_commit_data,
    get_file_content,
    get_file_content_before_after
)
from .diff_utils import (
    parse_diff,
    parse_github_patch,
    extract_function_diff,
    extract_function_diff_from_patch,
    get_changed_line_numbers,
    map_original_to_new_line,
    map_new_to_original_line
)

__all__ = [
    # GitHub API functions
    'parse_github_url',
    'get_commit_data',
    'get_file_content',
    'get_file_content_before_after',
    
    # Diff utilities
    'parse_diff',
    'parse_github_patch',
    'extract_function_diff',
    'extract_function_diff_from_patch',
    'get_changed_line_numbers',
    'map_original_to_new_line',
    'map_new_to_original_line'
] 