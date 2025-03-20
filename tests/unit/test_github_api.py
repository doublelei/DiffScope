import pytest
from src.utils.github_api import parse_github_url, get_commit_data, get_file_content

class TestGitHubAPI:
    """Tests for the GitHub API utility functions."""
    
    def test_parse_github_url_valid(self):
        """Test parsing a valid GitHub commit URL."""
        # Test standard GitHub URL
        owner, repo, commit_sha = parse_github_url(
            "https://github.com/python/cpython/commit/d783d7b51d31db568de6b3438f4e805acff663da"
        )
        assert owner == "python"
        assert repo == "cpython"
        assert commit_sha == "d783d7b51d31db568de6b3438f4e805acff663da"
        
        # Test HTTP URL (not HTTPS)
        owner, repo, commit_sha = parse_github_url(
            "http://github.com/python/cpython/commit/d783d7b51d31db568de6b3438f4e805acff663da"
        )
        assert owner == "python"
        assert repo == "cpython"
        assert commit_sha == "d783d7b51d31db568de6b3438f4e805acff663da"
    
    def test_parse_github_url_invalid(self):
        """Test parsing invalid GitHub URLs."""
        # Test completely invalid URL
        with pytest.raises(ValueError):
            parse_github_url("https://example.com/not-github")
        
        # Test malformed GitHub URL
        with pytest.raises(ValueError):
            parse_github_url("https://github.com/only-username")
        
        # Test missing commit SHA
        with pytest.raises(ValueError):
            parse_github_url("https://github.com/python/cpython/commits")
    
    @pytest.mark.live_api
    def test_get_commit_data(self):
        """Test retrieving commit data from GitHub API.
        
        Note: This test hits the live GitHub API.
        """
        # Use a well-known commit from the Python repository
        commit_data = get_commit_data(
            "python", "cpython", "d783d7b51d31db568de6b3438f4e805acff663da"
        )
        
        # Verify the basic structure of the response
        assert commit_data is not None
        assert 'sha' in commit_data
        assert 'commit' in commit_data
        assert 'files' in commit_data
        
        # Verify some commit details
        assert commit_data['sha'] == "d783d7b51d31db568de6b3438f4e805acff663da"
        assert 'message' in commit_data['commit']
    
    @pytest.mark.live_api
    def test_get_file_content(self):
        """Test retrieving file content from GitHub API.
        
        Note: This test hits the live GitHub API.
        """
        # Get content of README.md from Python repository at a specific commit
        content = get_file_content(
            "python", "cpython", "README.rst", "d783d7b51d31db568de6b3438f4e805acff663da"
        )
        
        # Verify content is retrieved
        assert content is not None
        assert "Python" in content
        
        # Test with a non-existent file
        content = get_file_content(
            "python", "cpython", "this-file-does-not-exist.txt", 
            "d783d7b51d31db568de6b3438f4e805acff663da"
        )
        assert content is None 