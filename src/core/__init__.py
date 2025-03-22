"""
Core functionality for DiffScope.

This package contains the core modules for DiffScope's functionality,
including Git commit analysis, function detection, and change analysis.
"""

from .git_analyzer import analyze_github_commit_metadata
from .commit_analyzer import analyze_commit_with_functions
from .function_detector import (
    create_modified_functions,
    detect_renamed_functions
)

__all__ = [
    'analyze_github_commit_metadata',
    'analyze_commit_with_functions',
    'create_modified_functions',
    'detect_renamed_functions'
] 