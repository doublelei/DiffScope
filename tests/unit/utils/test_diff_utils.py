"""
Tests for diff_utils module.

This module tests the parsing of unified diffs and line number mapping.
"""

import pytest
from src.utils.diff_utils import (
    parse_diff,
    get_changed_line_numbers,
    map_original_to_new_line,
    map_new_to_original_line,
    generate_line_map,
    extract_function_diff,
    FileDiff
)

# Sample diffs for testing
SIMPLE_DIFF = """diff --git a/sample.py b/sample.py
index 123abcd..456efgh 100644
--- a/sample.py
+++ b/sample.py
@@ -1,5 +1,6 @@
 def hello():
-    print("Hello World")
+    print("Hello")
+    print("World")
     return None
 
 def unchanged():
@@ -10,3 +11,5 @@ def unchanged():
 
 def another_func():
     pass
+
+def new_func():
+    return True
"""

COMPLEX_DIFF = """diff --git a/Lib/nturl2path.py b/Lib/nturl2path.py
index 7e13ae3128333d..7b5b82068e989f 100644
--- a/Lib/nturl2path.py
+++ b/Lib/nturl2path.py
@@ -14,7 +14,7 @@ def url2pathname(url):
     #   ///C:/foo/bar/spam.foo
     # become
     #   hhhh
-    import string, urllib.parse
+    import urllib.parse
     if url[:3] == '///':
         # URL has an empty authority section, so the path begins on the third
         # character.
@@ -25,19 +25,14 @@ def url2pathname(url):
     if url[:3] == '///':
         # Skip past extra slash before UNC drive in URL path.
         url = url[1:]
-    # Windows itself uses ":" even in URLs.
-    url = url.replace(':', '|')
-    if not '|' in url:
-        # No drive specifier, just convert slashes
-        # make sure not to convert quoted slashes :-)
-        return urllib.parse.unquote(url.replace('/', '\\'))
-    comp = url.split('|')
-    if len(comp) != 2 or comp[0][-1] not in string.ascii_letters:
-        error = 'Bad URL: ' + url
-        raise OSError(error)
-    drive = comp[0][-1]
-    tail = urllib.parse.unquote(comp[1].replace('/', '\\'))
-    return drive + ':' + tail
+    else:
+        if url[:1] == '/' and url[2:3] in (':', '|'):
+            # Skip past extra slash before DOS drive in URL path.
+            url = url[1:]
+        if url[1:2] == '|':
+            # Older URLs use a pipe after a drive letter
+            url = url[:1] + ':' + url[2:]
+    return urllib.parse.unquote(url.replace('/', '\\'))
 
 def pathname2url(p):
     '''OS-specific conversion from a file system path to a relative URL
"""

NEW_FILE_DIFF = """diff --git a/new_file.py b/new_file.py
new file mode 100644
index 0000000..123abcd
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,5 @@
+def hello():
+    print("Hello World")
+    return None
+
+# End of file
"""

DELETED_FILE_DIFF = """diff --git a/deleted.py b/deleted.py
deleted file mode 100644
index abcdef..000000
--- a/deleted.py
+++ /dev/null
@@ -1,5 +0,0 @@
-'''This file will be deleted.'''
-
-def some_function():
-    '''A function that will be deleted.'''
-    return 42
"""

RENAME_FILE_DIFF = """diff --git a/old_name.py b/new_name.py
similarity index 100%
rename from old_name.py
rename to new_name.py
diff --git a/old_name.py b/new_name.py
index 123abcd..123abcd 100644
--- a/old_name.py
+++ b/new_name.py
@@ -1,5 +1,5 @@
 def hello():
-    print("Hello World")
+    print("Hello Renamed World")
     return None
 
 # End of file
"""


class TestDiffUtils:
    """Test the diff_utils module functions."""
    
    def test_parse_simple_diff(self):
        """Test parsing a simple diff."""
        file_diffs = parse_diff(SIMPLE_DIFF)
        
        # Check basic parsing
        assert len(file_diffs) == 1
        assert file_diffs[0].old_file == "a/sample.py"
        assert file_diffs[0].new_file == "b/sample.py"
        assert not file_diffs[0].is_new
        assert not file_diffs[0].is_deleted
        
        # Check hunks
        assert len(file_diffs[0].hunks) == 2
        
        # Check first hunk
        hunk_header, hunk_lines = file_diffs[0].hunks[0]
        assert hunk_header.original_start == 1
        assert hunk_header.original_count == 5
        assert hunk_header.new_start == 1
        assert hunk_header.new_count == 6
        
        # Check changes in first hunk
        assert 2 in file_diffs[0].original_changes  # Line 2 was removed
        assert 2 in file_diffs[0].new_changes   # Line 2 was added
        assert 3 in file_diffs[0].new_changes   # Line 3 was added
        
        # Check second hunk
        hunk_header, hunk_lines = file_diffs[0].hunks[1]
        assert hunk_header.original_start == 10
        assert hunk_header.original_count == 3
        assert hunk_header.new_start == 11
        assert hunk_header.new_count == 5
        
        # Check additions in second hunk
        assert 14 in file_diffs[0].new_changes  # New blank line
        assert 15 in file_diffs[0].new_changes  # New function

    def test_parse_complex_diff(self):
        """Test parsing a complex diff with multiple changes."""
        result = parse_diff(COMPLEX_DIFF)
        assert len(result) == 1  # One file
        assert result[0].old_file == 'a/Lib/nturl2path.py'
        assert result[0].new_file == 'b/Lib/nturl2path.py'
        
        for line in [17] + list(range(28, 41)):
            assert line in result[0].original_changes
        assert list(result[0].original_changes.keys()) == [17] + list(range(28, 41))
        for line in [17] + list(range(28, 36)): 
            assert line in result[0].new_changes
        assert list(result[0].new_changes.keys()) == [17] + list(range(28, 36))
        

    def test_parse_new_file(self):
        """Test parsing a diff for a new file."""
        file_diffs = parse_diff(NEW_FILE_DIFF)
        
        assert len(file_diffs) == 1
        assert file_diffs[0].is_new
        assert file_diffs[0].old_file == "a/new_file.py"
        assert file_diffs[0].new_file == "b/new_file.py"
        
        # Check hunk
        hunk_header, hunk_lines = file_diffs[0].hunks[0]
        assert hunk_header.original_start == 0
        assert hunk_header.original_count == 0
        assert hunk_header.new_start == 1
        assert hunk_header.new_count == 5
        
        # All lines should be additions
        for i in range(1, 6):
            assert i in file_diffs[0].new_changes

    def test_parse_deleted_file(self):
        """Test parsing a diff for a deleted file."""
        result = parse_diff(DELETED_FILE_DIFF)
        assert len(result) == 1
        assert result[0].old_file == 'a/deleted.py'
        assert result[0].new_file == 'b/deleted.py'
        assert result[0].is_deleted
        
        # Verify the original content contains all deleted lines
        assert 1 in result[0].original_changes
        assert 3 in result[0].original_changes
        assert 4 in result[0].original_changes
        assert 5 in result[0].original_changes
        
        # New content should be empty for deleted files
        assert len(result[0].new_changes) == 0

    def test_parse_renamed_file(self):
        """Test parsing a diff for a renamed file."""
        file_diffs = parse_diff(RENAME_FILE_DIFF)
        
        # Should have one file diff - we should consolidate the rename and content change
        assert len(file_diffs) == 1
        assert file_diffs[0].old_file == "a/old_name.py"
        assert file_diffs[0].new_file == "b/new_name.py"
        assert file_diffs[0].is_rename  # Should be marked as a rename
        
        # Check hunk
        hunk_header, hunk_lines = file_diffs[0].hunks[0]
        assert 2 in file_diffs[0].original_changes  # Original line with "Hello World"
        assert 2 in file_diffs[0].new_changes       # Changed line with "Hello Renamed World"
        
        # Verify the specific content changes
        assert "print(\"Hello World\")" in file_diffs[0].original_changes[2]
        assert "print(\"Hello Renamed World\")" in file_diffs[0].new_changes[2]

    def test_get_changed_line_numbers(self):
        """Test getting changed line numbers from a diff."""
        file_diffs = parse_diff(SIMPLE_DIFF)
        diff = file_diffs[0]
        
        orig_lines, new_lines = get_changed_line_numbers(diff)
        
        # Check original file changed lines
        assert 2 in orig_lines  # Line 2 was changed
        
        # Check new file changed lines
        assert 2 in new_lines  # Line 2 was changed
        assert 3 in new_lines  # Line 3 was added
        assert 14 in new_lines  # New blank line
        assert 15 in new_lines  # New function

    def test_map_original_to_new_line(self):
        """Test mapping from original to new line numbers."""
        file_diff = parse_diff(COMPLEX_DIFF)[0]
        
        assert map_original_to_new_line(file_diff, 28) == None
        
        assert map_original_to_new_line(file_diff, 42) == 37
        
        assert map_original_to_new_line(file_diff, 17) == None
        

    def test_map_new_to_original_line(self):
        """Test mapping new to original line numbers."""
        file_diffs = parse_diff(SIMPLE_DIFF)
        diff = file_diffs[0]
        
        # Test mapping for unchanged lines
        assert map_new_to_original_line(diff, 1) == 1  # First line unchanged
        assert map_new_to_original_line(diff, 4) == 3  # Line after changes
        assert map_new_to_original_line(diff, 11) == 10  # Line after first hunk
        
        # Test mapping for added lines
        assert map_new_to_original_line(diff, 2) is None  # Line 2 was added
        assert map_new_to_original_line(diff, 3) is None  # Line 3 was added
        assert map_new_to_original_line(diff, 15) is None  # New function line

    def test_generate_line_map(self):
        """Test generating a complete line mapping."""
        file_diffs = parse_diff(SIMPLE_DIFF)
        diff = file_diffs[0]
        
        line_map = generate_line_map(diff)
        
        # Check specific mappings
        assert line_map.get(1) == 1  # First line unchanged
        assert line_map.get(2) is None  # Line 2 is new
        assert line_map.get(3) is None  # Line 3 is new
        assert line_map.get(4) == 3  # Maps to original line 3
        
        # Check that added lines map to None
        assert line_map.get(14) is None
        assert line_map.get(15) is None

    def test_extract_function_diff(self):
        """Test extracting a diff specific to a function."""
        file_diff = parse_diff(COMPLEX_DIFF)[0]
        
        # Extract diff for func1 (lines 8-11 in new file)
        func_diff = extract_function_diff(file_diff, 28, 31)
        assert func_diff is not None
        assert "-    return drive + ':' + tail" in func_diff
        assert "+    return urllib.parse.unquote(url.replace" in func_diff

        
        func_diff = extract_function_diff(file_diff, 12, 14)  # func2, no changes
        assert func_diff is None 