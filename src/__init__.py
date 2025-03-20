from .core.git_analyzer import analyze_github_commit
from .models import ModifiedFile, ModifiedFunction, CommitAnalysisResult

__all__ = ['analyze_commit', 'ModifiedFile', 'ModifiedFunction', 'CommitAnalysisResult']

def analyze_commit(commit_url: str) -> CommitAnalysisResult:
    """
    Analyze a Git commit and extract file-level changes.
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
    """
    # For now, we only support GitHub commits
    if "github.com" in commit_url:
        return analyze_github_commit(commit_url)
    else:
        raise ValueError(f"Unsupported Git provider. Currently only GitHub URLs are supported.")
