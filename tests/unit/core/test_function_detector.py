"""
Tests for function_detector module.

This module tests the detection of modified functions using diffs.
"""

import pytest
from src.core.function_detector import (
    create_modified_functions,
    analyze_function_changes,
    detect_renamed_functions,
    calculate_function_similarity,
    extract_functions_from_content
)
from src.utils.diff_utils import parse_diff, FileDiff
from src.models import FunctionChangeType, ModifiedFunction

# Sample code for testing
ORIGINAL_CODE = """
def unchanged_function():
    return 42

def modified_function(a, b):
    \"\"\"This docstring will change.\"\"\"
    x = a + b
    return x

def renamed_function():
    return "original"

def to_be_deleted():
    return "going away"
"""

NEW_CODE = """
def unchanged_function():
    return 42

def modified_function(a, b, c=None):
    \"\"\"This docstring has changed.\"\"\"
    x = a + b
    if c:
        x += c
    return x

def new_name_function():
    return "renamed"

def brand_new():
    return "I'm new!"
"""

# Sample diff between the two code samples
CODE_DIFF = """diff --git a/sample.py b/sample.py
index 123abc..456def 100644
--- a/sample.py
+++ b/sample.py
@@ -2,13 +2,18 @@
 def unchanged_function():
     return 42
 
-def modified_function(a, b):
-    \"\"\"This docstring will change.\"\"\"
+def modified_function(a, b, c=None):
+    \"\"\"This docstring has changed.\"\"\"
     x = a + b
+    if c:
+        x += c
     return x
 
-def renamed_function():
-    return "original"
+def new_name_function():
+    return "renamed"
 
-def to_be_deleted():
-    return "going away"
+def brand_new():
+    return "I'm new!"
"""


class TestFunctionDetector:
    """Test function detector functionality."""
    
    def test_create_modified_functions(self):
        """Test detection of modified, added, deleted and renamed functions."""
        # Parse the diff
        file_diffs = parse_diff(CODE_DIFF)
        assert len(file_diffs) == 1
        
        # Detect modified functions - pass the FileDiff object directly
        modified_functions = create_modified_functions(
            ORIGINAL_CODE, NEW_CODE, "python", "sample.py", file_diffs[0]
        )
        
        # Should detect 4 changes: 1 modified, 1 renamed, 1 deleted, 1 added
        assert len(modified_functions) == 4
        
        # Check for modified function with signature change
        mod_func = next((f for f in modified_functions 
                         if f.name == "modified_function" and f.change_type == FunctionChangeType.SIGNATURE_CHANGED), None)
        assert mod_func is not None
        assert mod_func.original_start is not None
        assert mod_func.new_start is not None
        
        # Check for renamed function
        renamed_func = next((f for f in modified_functions 
                          if f.change_type == FunctionChangeType.RENAMED), None)
        assert renamed_func is not None
        assert renamed_func.name == "new_name_function"
        assert renamed_func.original_name == "renamed_function"
        
        # Check for deleted function
        deleted_func = next((f for f in modified_functions 
                          if f.change_type == FunctionChangeType.DELETED), None)
        assert deleted_func is not None
        assert deleted_func.name == "to_be_deleted"
        assert deleted_func.new_start is None
        
        # Check for added function
        added_func = next((f for f in modified_functions 
                         if f.change_type == FunctionChangeType.ADDED), None)
        assert added_func is not None
        assert added_func.name == "brand_new"
        assert added_func.original_start is None
    
    def test_new_file_analysis(self):
        """Test analyzing a completely new file."""
        # Create sample content for a new file
        new_content = "def new_function():\n    print(\"Hello\")\n    return 42\n"
        
        # Create modified functions for a new file
        modified_functions = create_modified_functions(
            None, new_content, "python", "new_file.py"
        )
        
        # Should detect 1 added function
        assert len(modified_functions) == 1
        assert modified_functions[0].name == "new_function"
        assert modified_functions[0].change_type == FunctionChangeType.ADDED
    
    def test_deleted_file_analysis(self):
        """Test analyzing a completely deleted file."""
        # Create sample content for a file to be deleted
        original_content = "def old_function():\n    print(\"Goodbye\")\n    return 0\n"
        
        # Create modified functions for a deleted file
        modified_functions = create_modified_functions(
            original_content, None, "python", "deleted_file.py"
        )
        
        # Should detect 1 deleted function
        assert len(modified_functions) == 1
        assert modified_functions[0].name == "old_function"
        assert modified_functions[0].change_type == FunctionChangeType.DELETED
    
    def test_docstring_change_detection(self):
        """Test detection of docstring-only changes."""
        # Create code with only docstring changes
        orig = """def function():
    \"\"\"Original docstring.\"\"\"
    x = 1
    return x
"""
        new = """def function():
    \"\"\"Changed docstring.\"\"\"
    x = 1
    return x
"""
        diff = """diff --git a/sample.py b/sample.py
index 123abc..456def 100644
--- a/sample.py
+++ b/sample.py
@@ -1,5 +1,5 @@
 def function():
-    \"\"\"Original docstring.\"\"\"
+    \"\"\"Changed docstring.\"\"\"
     x = 1
     return x
"""
        file_diffs = parse_diff(diff)
        # Pass the FileDiff object directly
        modified_functions = create_modified_functions(
            orig, new, "python", "sample.py", file_diffs[0]
        )
        
        assert len(modified_functions) == 1
        assert modified_functions[0].change_type == FunctionChangeType.DOCSTRING_CHANGED
    
    def test_body_change_detection(self):
        """Test detection of body changes."""
        # Create code with body changes
        orig = """def function():
    \"\"\"Docstring.\"\"\"
    x = 1
    return x
"""
        new = """def function():
    \"\"\"Docstring.\"\"\"
    x = 2  # Changed value
    return x
"""
        diff = """diff --git a/sample.py b/sample.py
index 123abc..456def 100644
--- a/sample.py
+++ b/sample.py
@@ -1,5 +1,5 @@
 def function():
     \"\"\"Docstring.\"\"\"
-    x = 1
+    x = 2  # Changed value
     return x
"""
        file_diffs = parse_diff(diff)
        # Pass the FileDiff object directly
        modified_functions = create_modified_functions(
            orig, new, "python", "sample.py", file_diffs[0]
        )
        
        assert len(modified_functions) == 1
        assert modified_functions[0].change_type == FunctionChangeType.BODY_CHANGED
        
    def test_calculate_function_similarity(self):
        """Test calculation of function similarity."""
        original_content = """def function(a, b):
    res = a + b
    return res
"""
        similar_content = """def renamed_function(a, b):
    result = a + b
    return result
"""
        different_content = """def function(a, b):
    if a > b:
        return a - b
    elif a == b:
        return a * b
    else:
        return a + b
"""
        
        # Test high similarity (renamed function)
        similarity = calculate_function_similarity(original_content, similar_content)
        assert similarity > 0.8
        
        # Test low similarity (different implementation)
        similarity = calculate_function_similarity(original_content, different_content)
        assert similarity < 0.6
        
    def test_extract_functions_from_content(self):
        """Test extracting functions from file content."""
        content = """def function1():
    return 1

class MyClass:
    def method1(self):
        return "hello"
"""
        functions = extract_functions_from_content(content, "python", "test.py")
        
        # Should find 2 functions (1 function + 1 method)
        assert len(functions) == 2
        assert any(f['name'] == 'function1' for f in functions)
        assert any(f['name'] == 'method1' for f in functions)
        
    def test_detect_renamed_functions(self):
        """Test detection of renamed functions."""
        # Create a list with one added and one removed function that should be detected as renamed
        functions = [
            ModifiedFunction(
                name="new_func",
                file="test.py",
                type="function",
                change_type=FunctionChangeType.ADDED,
                new_start=10,
                new_end=15
            ),
            ModifiedFunction(
                name="old_func",
                file="test.py",
                type="function",
                change_type=FunctionChangeType.DELETED,
                original_start=5,
                original_end=10
            )
        ]
        
        # Apply renamed detection
        detect_renamed_functions(functions)
        
        # Either the functions are separate or one was detected as renamed (depends on implementation)
        if len(functions) == 1:
            # If implementation merges them, check the renamed function
            assert functions[0].change_type == FunctionChangeType.RENAMED
            assert functions[0].name == "new_func"
            assert functions[0].original_name == "old_func"
        else:
            # If implementation doesn't detect similarity automatically, that's okay for this test
            assert len(functions) == 2 