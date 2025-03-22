"""
Integration tests for commit analysis.

These tests verify the end-to-end functionality from
GitHub commit URL to function-level analysis results.
"""

import pytest
import os
import json
from unittest import mock
from typing import List, Optional

from src import analyze_commit
from src.models import FunctionChangeType, CommitAnalysisResult, ModifiedFile, ModifiedFunction


# Define RateLimitExceededException for handling GitHub API limits
class RateLimitExceededException(Exception):
    """Exception raised when GitHub API rate limit is exceeded."""
    pass


# Sample patch data for mocking
SAMPLE_PATCH = """@@ -1,5 +1,6 @@
 def unchanged_func():
     return 42
 
+# Added comment
 def changed_func(a):
-    return a + 1
+    return a + 2
"""

# Sample file content before/after for mocking
BEFORE_CONTENT = """def unchanged_func():
    return 42

def changed_func(a):
    return a + 1
"""

AFTER_CONTENT = """def unchanged_func():
    return 42

# Added comment
def changed_func(a):
    return a + 2
"""

# Default commit URL to use when none is specified
DEFAULT_COMMIT_URL = "https://github.com/python/cpython/commit/d783d7b51d31db568de6b3438f4e805acff663da"


def load_commit_urls_from_file(file_path: str) -> List[str]:
    """Load commit URLs from a file (either txt or json format)."""
    if not os.path.exists(file_path):
        raise ValueError(f"File not found: {file_path}")
    
    urls = []
    
    # Determine file type based on extension
    _, ext = os.path.splitext(file_path)
    
    if ext.lower() == '.json':
        # Load from JSON
        with open(file_path, 'r') as f:
            data = json.load(f)
            
            # Handle different possible JSON structures
            if isinstance(data, list):
                # List of URLs
                urls = data
            elif isinstance(data, dict) and 'urls' in data:
                # Dictionary with 'urls' key
                urls = data['urls']
            elif isinstance(data, dict):
                # Dictionary with commits as keys
                urls = list(data.keys())
    else:
        # Default to txt format (one URL per line)
        with open(file_path, 'r') as f:
            urls = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
    
    # Validate URLs
    valid_urls = []
    for url in urls:
        if url and 'github.com' in url and '/commit/' in url:
            valid_urls.append(url)
        else:
            print(f"Warning: Skipping invalid GitHub commit URL: {url}")
    
    if not valid_urls:
        raise ValueError(f"No valid GitHub commit URLs found in {file_path}")
    
    return valid_urls


def get_commit_urls(config) -> List[str]:
    """Get commit URLs from command-line options or use default."""
    # Check if a specific commit URL was provided
    single_url = config.getoption("--commit_url")
    if single_url:
        return [single_url]
    
    # Check if a file with commit URLs was provided
    file_path = config.getoption("--commit_file")
    if file_path:
        return load_commit_urls_from_file(file_path)
    
    # Use the default commit URL if no options were provided
    return [DEFAULT_COMMIT_URL]


def pytest_generate_tests(metafunc):
    """Generate tests dynamically based on command-line options."""
    # Only parametrize tests for multi-commit testing
    if "commit_url_param" in metafunc.fixturenames and metafunc.config.getoption("--commit_file"):
        commit_urls = get_commit_urls(metafunc.config)
        metafunc.parametrize("commit_url_param", commit_urls)


@pytest.fixture
def commit_url_param(request):
    """Fixture to get commit URL from command line or use default."""
    if request.config.getoption("--commit_url"):
        return request.config.getoption("--commit_url")
    
    # If no specific commit URL, use default
    return DEFAULT_COMMIT_URL


class TestCommitAnalysis:
    """Test the full commit analysis pipeline."""
    
    @pytest.fixture
    def mock_github_api(self):
        """Mock GitHub API to avoid actual network calls."""
        with mock.patch('src.utils.github_api.parse_github_url') as mock_parse:
            mock_parse.return_value = ('owner', 'repo', '123456')
            
            with mock.patch('src.utils.github_api.get_commit_data') as mock_commit:
                mock_commit.return_value = {
                    'commit': {
                        'message': 'Test commit',
                        'author': {'name': 'Test Author', 'date': '2023-01-01T00:00:00Z'}
                    },
                    'files': [
                        {
                            'filename': 'test.py',
                            'status': 'modified',
                            'additions': 2,
                            'deletions': 1,
                            'changes': 3,
                            'patch': SAMPLE_PATCH
                        }
                    ]
                }
                
                with mock.patch('src.utils.github_api.get_file_content_before_after') as mock_content:
                    mock_content.return_value = (BEFORE_CONTENT, AFTER_CONTENT)
                    
                    yield


@pytest.mark.live_api
def test_analyze_commit(print_commit_result, commit_url_param, request, save_results_path, save_failed_urls_path):
    """
    Test the full commit analysis workflow with a real GitHub commit.
    
    This test is run when a single commit URL is provided via --commit_url
    or when no special parameters are provided (uses DEFAULT_COMMIT_URL).
    """
    # Skip if we're running with a commit file (the parametrized test will handle it)
    if request.config.getoption("--commit_file"):
        pytest.skip("Skipping single commit test when using --commit_file")
    
    try:
        result = analyze_commit(commit_url_param)
        
        # Print the detailed result using the fixture
        print_commit_result(result, commit_url_param)
        
        # Save results if path is provided
        if save_results_path:
            from tests.conftest import save_commit_analysis_result
            save_commit_analysis_result(result, save_results_path, commit_url_param)
        
        # Basic checks
        assert result.commit_sha
        assert result.commit_message
        assert len(result.modified_files) > 0
        
        # Check if we detected at least some function changes
        assert len(result.modified_functions) > 0
        
        # Verify we have different types of function changes
        change_types = set(func.change_type for func in result.modified_functions)
        assert len(change_types) > 0
        
        # More thorough validation of the result structure
        assert isinstance(result, CommitAnalysisResult)
        assert result.commit_author is not None
        assert result.commit_date is not None
        assert result.repository_url is not None
        
        # Verify file changes
        assert isinstance(result.modified_files, list)
        
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
                
        # Verify some function changes
        for func in result.modified_functions:
            assert isinstance(func, ModifiedFunction)
            assert func.name is not None
            assert func.file is not None
            assert isinstance(func.change_type, FunctionChangeType)
            
    except Exception as e:
        if "API rate limit exceeded" in str(e):
            pytest.skip("GitHub API rate limit exceeded. Set GITHUB_TOKEN environment variable.")
        else:
            raise


@pytest.mark.live_api
def test_analyze_commit_parametrized(print_commit_result, commit_url_param, request, save_results_path, save_failed_urls_path):
    """
    Parametrized test for analyzing multiple commit URLs from a file.
    
    This test will run once for each URL provided in the commit file.
    """
    # Only run this test when --commit_file is provided
    if not request.config.getoption("--commit_file"):
        pytest.skip("Skipping parametrized tests when not using --commit_file")
    
    try:
        result = analyze_commit(commit_url_param)
        
        # Print the detailed result
        print_commit_result(result, commit_url_param)
        
        # Save results if path is provided
        if save_results_path:
            from tests.conftest import save_commit_analysis_result
            save_commit_analysis_result(result, save_results_path, commit_url_param)
        
        # Basic validations that should work with any commit
        assert isinstance(result, CommitAnalysisResult)
        assert result.commit_sha is not None
        assert result.repository_url is not None
        assert len(result.modified_files) > 0
            
    except Exception as e:
        if "API rate limit exceeded" in str(e):
            pytest.skip("GitHub API rate limit exceeded. Set GITHUB_TOKEN environment variable.")
        else:
            raise


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
    except Exception as e:
        if "API rate limit exceeded" in str(e):
            pytest.skip("GitHub API rate limit exceeded. Set GITHUB_TOKEN environment variable.")
        else:
            raise 