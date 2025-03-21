"""
Integration tests for commit analysis.

These tests verify the end-to-end functionality from
GitHub commit URL to function-level analysis results.
"""

import pytest
import os
from unittest import mock

from src import analyze_commit
from src.models import FileChangeType, FunctionChangeType, CommitAnalysisResult, ModifiedFile, ModifiedFunction

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
    def test_analyze_real_commit(self, print_commit_result):
        """Test analysis of a real GitHub commit (requires --run-live-api flag)."""
        # Use a known public commit URL for testing
        result = analyze_commit('https://github.com/python/cpython/commit/d783d7b51d31db568de6b3438f4e805acff663da')

        # Basic checks
        assert result.commit_sha
        assert result.commit_message
        assert len(result.modified_files) > 0
        
        # Check if we detected at least some function changes
        assert len(result.modified_functions) > 0
        
        # Verify we have different types of function changes
        change_types = set(func.change_type for func in result.modified_functions)
        assert len(change_types) > 0
        
        # Print summary using the fixture
        print_commit_result(result)

@pytest.mark.live_api
def test_analyze_commit_full_workflow(print_commit_result):
    """Test the full commit analysis workflow with a real GitHub commit."""
    # Use a well-known commit URL with Python code changes
    commit_url = "https://github.com/python/cpython/commit/d783d7b51d31db568de6b3438f4e805acff663da"
    
    try:
        # Analyze the commit using the main library function
        result = analyze_commit(commit_url)
        
        # Print the detailed result using the fixture
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
        
        # Verify function changes
        assert isinstance(result.modified_functions, list)
        # We should find some function changes in a Python codebase
        assert len(result.modified_functions) > 0
        
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