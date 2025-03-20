import pytest
from src.models import ModifiedFile, ModifiedFunction, CommitAnalysisResult
from pydantic import ValidationError

class TestModels:
    """Tests for the DiffScope data models."""
    
    def test_modified_file_creation(self):
        """Test creating ModifiedFile objects."""
        # Test minimal creation
        file = ModifiedFile(filename="main.py")
        assert file.filename == "main.py"
        assert file.status is None
        assert file.additions == 0
        assert file.deletions == 0
        assert file.changes == 0
        assert file.patch is None
        assert file.language is None
        
        # Test full initialization
        file = ModifiedFile(
            filename="app.js",
            status="modified",
            additions=10,
            deletions=5,
            changes=15,
            patch="@@ -1,5 +1,10 @@\n Some content",
            language="JavaScript"
        )
        assert file.filename == "app.js"
        assert file.status == "modified"
        assert file.additions == 10
        assert file.deletions == 5
        assert file.changes == 15
        assert file.patch == "@@ -1,5 +1,10 @@\n Some content"
        assert file.language == "JavaScript"
    
    def test_modified_function_creation(self):
        """Test creating ModifiedFunction objects."""
        # Test minimal creation
        func = ModifiedFunction(function_name="test_func", file_path="test.py")
        assert func.function_name == "test_func"
        assert func.file_path == "test.py"
        assert func.language is None
        assert func.start_line is None
        assert func.end_line is None
        assert func.before_content is None
        assert func.after_content is None
        assert func.change_type is None
        assert func.diff is None
        
        # Test full initialization
        func = ModifiedFunction(
            function_name="calculate_total",
            file_path="utils.js",
            language="JavaScript",
            start_line=15,
            end_line=30,
            before_content="function calculateTotal(items) {\n  return items.reduce((sum, item) => sum + item.price, 0);\n}",
            after_content="function calculateTotal(items) {\n  return items.reduce((sum, item) => sum + item.price * item.quantity, 0);\n}",
            change_type="modified",
            diff="@@ -1,3 +1,3 @@\n function calculateTotal(items) {\n-  return items.reduce((sum, item) => sum + item.price, 0);\n+  return items.reduce((sum, item) => sum + item.price * item.quantity, 0);\n }"
        )
        assert func.function_name == "calculate_total"
        assert func.file_path == "utils.js"
        assert func.language == "JavaScript"
        assert func.start_line == 15
        assert func.end_line == 30
        assert "items.reduce" in func.before_content
        assert "item.price * item.quantity" in func.after_content
        assert func.change_type == "modified"
        assert "item.price * item.quantity" in func.diff
    
    def test_commit_analysis_result_creation(self):
        """Test creating CommitAnalysisResult objects."""
        # Test minimal creation
        result = CommitAnalysisResult(commit_sha="abc123")
        assert result.commit_sha == "abc123"
        assert result.commit_message is None
        assert result.commit_author is None
        assert result.commit_date is None
        assert result.repository_url is None
        assert result.modified_files == []
        assert result.modified_functions == []
        
        # Test with files and functions
        file1 = ModifiedFile(filename="main.py", status="modified")
        file2 = ModifiedFile(filename="utils.js", status="added")
        func1 = ModifiedFunction(function_name="test_func", file_path="main.py")
        
        result = CommitAnalysisResult(
            commit_sha="def456",
            commit_message="Fix bug in calculation",
            commit_author="John Doe",
            commit_date="2023-05-15T14:30:00Z",
            repository_url="https://github.com/username/repo",
            modified_files=[file1, file2],
            modified_functions=[func1]
        )
        
        assert result.commit_sha == "def456"
        assert result.commit_message == "Fix bug in calculation"
        assert result.commit_author == "John Doe"
        assert result.commit_date == "2023-05-15T14:30:00Z"
        assert result.repository_url == "https://github.com/username/repo"
        assert len(result.modified_files) == 2
        assert result.modified_files[0].filename == "main.py"
        assert result.modified_files[1].filename == "utils.js"
        assert len(result.modified_functions) == 1
        assert result.modified_functions[0].function_name == "test_func"
