import pytest
import os
from src import analyze_commit
from src.models import CommitAnalysisResult, ModifiedFile
from github.GithubException import RateLimitExceededException

@pytest.mark.live_api
def test_analyze_commit_full_workflow(print_commit_result):
    """Test the full commit analysis workflow with a real GitHub commit."""
    # Skip test if no GitHub token and explicitly told to skip on rate limit
    if os.environ.get('SKIP_ON_NO_TOKEN', 'false').lower() == 'true' and not os.environ.get('GITHUB_TOKEN'):
        pytest.skip("Skipping test due to missing GITHUB_TOKEN")
        
    # Use a well-known commit URL
    commit_url = "https://github.com/python/cpython/commit/d783d7b51d31db568de6b3438f4e805acff663da"
    
    try:
        # Analyze the commit using the main library function
        result = analyze_commit(commit_url)
        
        # Print the detailed result for better visibility
        print_commit_result(result)
        
        # Verify the result structure
        assert isinstance(result, CommitAnalysisResult)
        assert result.commit_sha == "d783d7b51d31db568de6b3438f4e805acff663da"
        assert result.commit_author is not None
        assert result.commit_date is not None
        assert result.commit_message is not None
        assert result.repository_url == "https://github.com/python/cpython"
        
        # Verify file changes
        assert isinstance(result.modified_files, list)
        assert len(result.modified_files) > 0
        
        # Verify function changes (empty for now in Phase 1)
        assert isinstance(result.modified_functions, list)
        assert len(result.modified_functions) == 0  # Phase 1 doesn't populate this
        
        # Verify a few files
        for file in result.modified_files:
            assert isinstance(file, ModifiedFile)
            assert file.filename is not None
            assert file.status in ["added", "modified", "removed"]
            assert isinstance(file.additions, int)
            assert isinstance(file.deletions, int)
            assert isinstance(file.changes, int)
            
            # If file has a language, check it's a string
            if file.language is not None:
                assert isinstance(file.language, str)
    except RateLimitExceededException:
        pytest.skip("GitHub API rate limit exceeded. Set GITHUB_TOKEN environment variable.")

@pytest.mark.live_api
def test_analyze_commit_error_handling():
    """Test error handling for invalid commit URLs."""
    # Test with an invalid URL format
    with pytest.raises(ValueError, match="Unsupported Git provider. Currently only GitHub URLs are supported."):
        analyze_commit("https://example.com/not-github")
    
    # Test with a non-existent repository
    try:
        with pytest.raises(ValueError):
            analyze_commit("https://github.com/this-repo-does-not-exist-12345/fake-repo/commit/abcdef")
    except RateLimitExceededException:
        pytest.skip("GitHub API rate limit exceeded. Set GITHUB_TOKEN environment variable.") 