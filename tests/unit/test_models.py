"""
Tests for the models module.

This module tests the data structures defined in the models module.
"""

import pytest
from src.models import (
    FunctionChangeType,
    ModifiedFile,
    ModifiedFunction,
    CommitAnalysisResult
)


class TestModels:
    """Tests for the models module."""

    def test_modified_file_creation(self):
        """Test creating a ModifiedFile object."""
        file = ModifiedFile(
            filename="path/to/file.py",
            status= "modified",
            additions=10,
            deletions=5,
            changes=15,
            language="python"
        )
        
        assert file.filename == "path/to/file.py"
        assert file.status == "modified"
        assert file.additions == 10
        assert file.deletions == 5
        assert file.changes == 15
        assert file.language == "python"

    def test_modified_function_creation(self):
        """Test creating a ModifiedFunction object."""
        function = ModifiedFunction(
            name="test_function",
            file="path/to/file.py",
            type="function",
            change_type=FunctionChangeType.MODIFIED,
            new_start=10,
            new_end=20,
            changes=5,
            diff="@@ -1,5 +1,6 @@\n function content"
        )
        
        assert function.name == "test_function"
        assert function.file == "path/to/file.py"
        assert function.type == "function"
        assert function.change_type == FunctionChangeType.MODIFIED
        assert function.new_start == 10
        assert function.new_end == 20
        assert function.changes == 5
        assert function.diff == "@@ -1,5 +1,6 @@\n function content"

    def test_commit_analysis_result_creation(self):
        """Test creating a CommitAnalysisResult object."""
        file1 = ModifiedFile(
            filename="path/to/file1.py",
            status="modified",
            additions=10,
            deletions=5,
            changes=15
        )
        
        file2 = ModifiedFile(
            filename="path/to/file2.py",
            status="added",
            additions=20,
            deletions=0,
            changes=20
        )
        
        function1 = ModifiedFunction(
            name="test_function1",
            file="path/to/file1.py",
            type="function",
            change_type=FunctionChangeType.MODIFIED
        )
        
        result = CommitAnalysisResult(
            commit_sha="abc123",
            repository_url="https://github.com/example/repo",
            commit_author="Test User",
            commit_date="2023-08-15T12:00:00Z",
            commit_message="Test commit",
            modified_files=[file1, file2],
            modified_functions=[function1]
        )
        
        assert result.commit_sha == "abc123"
        assert result.repository_url == "https://github.com/example/repo"
        assert len(result.modified_files) == 2
        assert result.modified_files[0].filename == "path/to/file1.py"
        assert result.modified_files[1].filename == "path/to/file2.py"
        assert len(result.modified_functions) == 1
        assert result.modified_functions[0].name == "test_function1"

        
    def test_commit_analysis_result_empty_lists(self):
        """Test CommitAnalysisResult initializes empty lists."""
        result = CommitAnalysisResult(
            commit_sha="abc123",
            repository_url="https://github.com/example/repo"
        )
        
        assert result.modified_files == []
        assert result.modified_functions == []
        
    def test_file_with_patch(self):
        """Test creating a ModifiedFile with a patch."""
        file = ModifiedFile(
            filename="path/to/file.py",
            status="modified",
            additions=10,
            deletions=5,
            changes=15,
            patch="@@ -1,5 +1,10 @@\n content"
        )
        
        assert file.patch == "@@ -1,5 +1,10 @@\n content"
        
    def test_renamed_file(self):
        """Test creating a renamed file."""
        file = ModifiedFile(
            filename="path/to/new_file.py",
            status="renamed",
            additions=0,
            deletions=0,
            changes=0,
            previous_filename="path/to/old_file.py"
        )
        
        assert file.status == "renamed"
        assert file.previous_filename == "path/to/old_file.py"
        
    def test_renamed_function(self):
        """Test creating a renamed function."""
        function = ModifiedFunction(
            name="function_name",
            file="path/to/file.py",
            type="function",
            change_type=FunctionChangeType.RENAMED,
            original_name="old_function_name"
        )
        
        assert function.change_type == FunctionChangeType.RENAMED
        assert function.original_name == "old_function_name"
