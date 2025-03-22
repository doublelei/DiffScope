"""
DiffScope: Function-level git commit analysis.

This package provides tools for analyzing git commits
at the function level, identifying exactly which functions
were modified, added, or deleted in each commit.
"""

__version__ = "0.1.0"
__author__ = "DiffScope Team"

from .core.commit_analyzer import analyze_commit_with_functions
from .models import (
    ModifiedFile,
    ModifiedFunction,
    CommitAnalysisResult,
    FunctionChangeType
)

# Export the main API functions
__all__ = [
    'analyze_commit',  # Main function (with function-level analysis)
    'analyze_github_commit',  # Phase 1 function (file-level only)
    'analyze_commit_with_functions',  # Full function-level analysis
    'ModifiedFile',
    'ModifiedFunction',
    'CommitAnalysisResult',
    'FunctionChangeType'
]

def analyze_commit(commit_url: str) -> CommitAnalysisResult:
    """
    Analyze a Git commit and extract both file-level and function-level changes.
    This is the main entry point for the library.
    
    Args:
        commit_url: URL to a Git commit (currently only GitHub is supported)
        
    Returns:
        CommitAnalysisResult object containing file and function level changes
    
    Example:
        >>> from diffscope import analyze_commit
        >>> result = analyze_commit("https://github.com/owner/repo/commit/abc123")
        >>> for file in result.modified_files:
        >>>     print(f"File: {file.filename}, Changes: {file.changes}")
        >>> for func in result.modified_functions:
        >>>     print(f"Function: {func.name}, Change: {func.change_type}")
    """
    # For now, we only support GitHub commits
    if "github.com" in commit_url:
        return analyze_commit_with_functions(commit_url)
    else:
        raise ValueError(f"Unsupported Git provider. Currently only GitHub URLs are supported.")
