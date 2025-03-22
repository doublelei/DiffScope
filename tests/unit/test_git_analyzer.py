import pytest
from src.core.git_analyzer import detect_file_language, convert_github_files_to_modified_files, analyze_github_commit_metadata
from src.models import ModifiedFile, CommitAnalysisResult

class TestGitAnalyzer:
    """Tests for the Git analyzer module."""
    
    def test_detect_file_language(self):
        """Test file language detection based on extensions."""
        # Common programming languages
        assert detect_file_language("main.py") == "Python"
        assert detect_file_language("app.js") == "JavaScript"
        assert detect_file_language("Component.jsx") == "JavaScript"
        assert detect_file_language("interface.ts") == "TypeScript"
        assert detect_file_language("styles.tsx") == "TypeScript"
        assert detect_file_language("Program.java") == "Java"
        assert detect_file_language("utils.c") == "C"
        assert detect_file_language("header.h") == "C"
        assert detect_file_language("library.cpp") == "C++"
        
        # Case insensitivity
        assert detect_file_language("script.JS") == "JavaScript"
        assert detect_file_language("MODULE.PY") == "Python"
        
        # Unknown extensions
        assert detect_file_language("readme.txt") is None
        assert detect_file_language("Makefile") is None
        assert detect_file_language("file-without-extension") is None
    
    def test_convert_github_files_to_modified_files(self):
        """Test conversion of GitHub API file data to ModifiedFile objects."""
        # Sample GitHub API file data
        github_files = [
            {
                "filename": "README.md",
                "status": "modified",
                "additions": 10,
                "deletions": 5,
                "changes": 15,
                "patch": "@@ -1,5 +1,10 @@\n Some content"
            },
            {
                "filename": "src/main.py",
                "status": "added",
                "additions": 20,
                "deletions": 0,
                "changes": 20,
                "patch": "@@ -0,0 +1,20 @@\n New content"
            },
            {
                "filename": "src/old.js",
                "status": "removed",
                "additions": 0,
                "deletions": 15,
                "changes": 15,
                "patch": None  # Removed files might not have a patch
            }
        ]
        
        # Convert to ModifiedFile objects
        modified_files = convert_github_files_to_modified_files(github_files)
        
        # Verify conversion
        assert len(modified_files) == 3
        
        # Check first file
        assert modified_files[0].filename == "README.md"
        assert modified_files[0].status == "modified"
        assert modified_files[0].additions == 10
        assert modified_files[0].deletions == 5
        assert modified_files[0].changes == 15
        assert modified_files[0].patch == "@@ -1,5 +1,10 @@\n Some content"
        assert modified_files[0].language is None  # .md is not a recognized programming language
        
        # Check second file
        assert modified_files[1].filename == "src/main.py"
        assert modified_files[1].status == "added"
        assert modified_files[1].additions == 20
        assert modified_files[1].deletions == 0
        assert modified_files[1].changes == 20
        assert modified_files[1].language == "Python"
        
        # Check third file
        assert modified_files[2].filename == "src/old.js"
        assert modified_files[2].status == "removed"
        assert modified_files[2].additions == 0
        assert modified_files[2].deletions == 15
        assert modified_files[2].language == "JavaScript"
    
    @pytest.mark.live_api
    def test_analyze_github_commit(self):
        """Test analyzing a GitHub commit.
        
        Note: This test hits the live GitHub API.
        """
        # Use a well-known commit URL
        commit_url = "https://github.com/python/cpython/commit/d783d7b51d31db568de6b3438f4e805acff663da"
        
        # Analyze the commit
        result = analyze_github_commit_metadata(commit_url)
        
        # Verify result structure
        assert isinstance(result, CommitAnalysisResult)
        assert result.commit_sha == "d783d7b51d31db568de6b3438f4e805acff663da"
        assert result.repository_url == "https://github.com/python/cpython"
        assert result.owner == "python"
        assert result.repo == "cpython"
        assert len(result.modified_files) > 0
        
        # Verify first modified file
        first_file = result.modified_files[0]
        assert isinstance(first_file, ModifiedFile)
        assert first_file.filename is not None
        assert first_file.status is not None 