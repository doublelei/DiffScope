"""
Tests for function_detector module.

This module tests the detection of modified functions using diffs.
"""

import pytest
from src.core.function_detector import (
    detect_modified_functions,
    analyze_file_diff,
    _find_matching_function,
    _determine_change_type
)
from src.utils.diff_utils import parse_unified_diff
from src.models import FunctionChangeType

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
    
    def test_detect_modified_functions(self):
        """Test detection of modified, added, deleted and renamed functions."""
        # Parse the diff
        file_diffs = parse_unified_diff(CODE_DIFF)
        assert len(file_diffs) == 1
        
        # Detect modified functions
        modified_functions = detect_modified_functions(
            ORIGINAL_CODE, NEW_CODE, file_diffs[0], "python", "sample.py"
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
    
    def test_analyze_file_diff_new_file(self):
        """Test analyzing a completely new file."""
        # Create a simple diff for a new file
        new_file_diff = """diff --git a/new_file.py b/new_file.py
new file mode 100644
index 000000..123abc
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,4 @@
+def new_function():
+    print("Hello")
+    return 42
+
"""
        file_diffs = parse_unified_diff(new_file_diff)
        assert len(file_diffs) == 1
        assert file_diffs[0].is_new_file
        
        # Analyze the file diff
        new_content = "def new_function():\n    print(\"Hello\")\n    return 42\n"
        modified_functions = analyze_file_diff(
            file_diffs[0], "", new_content, "python", "new_file.py"
        )
        
        # Should detect 1 added function
        assert len(modified_functions) == 1
        assert modified_functions[0].name == "new_function"
        assert modified_functions[0].change_type == FunctionChangeType.ADDED
    
    def test_analyze_file_diff_deleted_file(self):
        """Test analyzing a completely deleted file."""
        # Create a simple diff for a deleted file
        deleted_file_diff = """diff --git a/deleted_file.py b/deleted_file.py
deleted file mode 100644
index 123abc..000000
--- a/deleted_file.py
+++ /dev/null
@@ -1,4 +0,0
-def old_function():
-    print("Goodbye")
-    return 0
-
"""
        file_diffs = parse_unified_diff(deleted_file_diff)
        assert len(file_diffs) == 1
        assert file_diffs[0].is_deleted_file
        
        # Analyze the file diff
        original_content = "def old_function():\n    print(\"Goodbye\")\n    return 0\n"
        modified_functions = analyze_file_diff(
            file_diffs[0], original_content, "", "python", "deleted_file.py"
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
        file_diffs = parse_unified_diff(diff)
        modified_functions = detect_modified_functions(
            orig, new, file_diffs[0], "python", "sample.py"
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
        file_diffs = parse_unified_diff(diff)
        modified_functions = detect_modified_functions(
            orig, new, file_diffs[0], "python", "sample.py"
        )
        
        assert len(modified_functions) == 1
        assert modified_functions[0].change_type == FunctionChangeType.BODY_CHANGED 