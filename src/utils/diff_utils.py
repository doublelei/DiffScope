"""
Diff parsing utilities for DiffScope.

This module provides functions for parsing unified diff format
and mapping changes to line numbers in files.
"""

import re
from typing import Dict, List, Tuple, Optional, Set, NamedTuple
import logging
import difflib

# Set up logging
logger = logging.getLogger(__name__)

# Define data structures for diff information
class HunkHeader(NamedTuple):
    """Represents a hunk header in a diff."""
    original_start: int
    original_count: int
    new_start: int
    new_count: int


class FileDiff(NamedTuple):
    """Represents a diff for a single file."""
    old_file: str  # Renamed from original_file for consistency with tests
    new_file: str
    hunks: List[Tuple[HunkHeader, List[str]]]
    original_changes: Dict[int, str]  # line_number -> content
    new_changes: Dict[int, str]  # line_number -> content
    is_new: bool = False
    is_deleted: bool = False
    is_binary: bool = False
    is_rename: bool = False


# Regular expressions for parsing diff components
RE_HUNK_HEADER = re.compile(
    r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?:\s(.*))?$'
)
RE_FILE_HEADER_A = re.compile(r'^--- (?:a/)?(.*?)(?:\s.*)?$')
RE_FILE_HEADER_B = re.compile(r'^\+\+\+ (?:b/)?(.*?)(?:\s.*)?$')
RE_NEW_FILE = re.compile(r'^new file mode \d+$')
RE_DELETED_FILE = re.compile(r'^deleted file mode \d+$')
RE_RENAME = re.compile(r'^rename (from|to) (.*)$')
RE_BINARY = re.compile(r'^Binary files (.*) and (.*) differ$')


def parse_diff(diff_content: str) -> List[FileDiff]:
    """
    Parse a unified diff string and return a list of FileDiff objects.
    
    Args:
        diff_content: The content of the diff.
        
    Returns:
        A list of FileDiff objects, one for each file in the diff.
    """
    if not diff_content:
        return []
    
    lines = diff_content.split('\n')
    file_diffs = []
    
    i = 0
    # Track rename information between diff blocks
    pending_rename = None
    
    while i < len(lines):
        # Check if this is a rename section without file content
        if i + 3 < len(lines) and lines[i].startswith('diff --git') and lines[i+1].startswith('similarity index'):
            if lines[i+2].startswith('rename from') and lines[i+3].startswith('rename to'):
                # This is a rename block, extract the file paths
                from_file = lines[i+2][12:].strip()
                to_file = lines[i+3][10:].strip()
                pending_rename = (f"a/{from_file}", f"b/{to_file}")
                
                # Skip this block and continue to the next diff
                i += 4
                while i < len(lines) and not lines[i].startswith('diff --git'):
                    i += 1
                continue
        
        # Parse the next file diff
        file_diff = _parse_file_diff(lines, i)
        if file_diff:
            # Check if this is the content for a pending rename
            if pending_rename and file_diff.old_file == pending_rename[0] and file_diff.new_file == pending_rename[1]:
                # Update the file diff to mark it as a rename
                file_diff = FileDiff(
                    old_file=file_diff.old_file,
                    new_file=file_diff.new_file,
                    hunks=file_diff.hunks,
                    original_changes=file_diff.original_changes,
                    new_changes=file_diff.new_changes,
                    is_new=file_diff.is_new,
                    is_deleted=file_diff.is_deleted,
                    is_binary=file_diff.is_binary,
                    is_rename=True  # Mark as rename
                )
                pending_rename = None
            
            file_diffs.append(file_diff)
            
            # Skip to the start of the next file diff
            i += 1
            while i < len(lines) and not lines[i].startswith('diff --git'):
                i += 1
        else:
            i += 1
    
    return file_diffs


def _parse_file_diff(lines: List[str], start_idx: int) -> Optional[FileDiff]:
    """Parse a single file diff starting at the given index."""
    if start_idx >= len(lines) or not lines[start_idx].startswith('diff --git'):
        return None
    
    i = start_idx
    old_file = None
    new_file = None
    is_new = False
    is_deleted = False
    is_binary = False
    is_rename = False
    
    # Parse diff --git line to extract file names
    diff_git_match = re.match(r'diff --git (a/.*) (b/.*)', lines[i])
    if diff_git_match:
        old_file = diff_git_match.group(1)
        new_file = diff_git_match.group(2)
    
    # Skip the diff --git line
    i += 1
    
    # Parse file headers
    while i < len(lines):
        line = lines[i]
        if line.startswith('index ') or line.startswith('mode '):
            i += 1
            continue
        elif line.startswith('new file mode'):
            is_new = True
            i += 1
        elif line.startswith('deleted file mode'):
            is_deleted = True
            i += 1
        elif line.startswith('Binary files'):
            is_binary = True
            i += 1
        elif line.startswith('rename from'):
            is_rename = True
            old_path = line[12:].strip()
            i += 1
            if i < len(lines) and lines[i].startswith('rename to'):
                new_path = lines[i][10:].strip()
                old_file = f"a/{old_path}"
                new_file = f"b/{new_path}"
                i += 1
        elif line.startswith('--- '):
            # For deleted files, preserve the a/ prefix
            if line[4:] != '/dev/null':
                old_file = line[4:]
            i += 1
            break
        else:
            i += 1
    
    # Parse the +++ line
    if i < len(lines) and lines[i].startswith('+++ '):
        # For new files, preserve the b/ prefix
        if lines[i][4:] != '/dev/null':
            new_file = lines[i][4:]
        i += 1
    else:
        # If no +++ line, use the fallback values from diff --git
        if not new_file:
            logger.warning("Failed to parse +++ line, using fallback")
            if is_deleted:
                new_file = "b/" + old_file[2:]  # Use old path with b/ prefix
        i += 1
    
    # Skip binary files
    if is_binary:
        return FileDiff(
            old_file=old_file,
            new_file=new_file,
            hunks=[],
            original_changes={},
            new_changes={},
            is_new=is_new,
            is_deleted=is_deleted,
            is_binary=True,
            is_rename=is_rename
        )
    
    # Parse hunks
    hunks = []
    original_changes = {}
    new_changes = {}
    
    while i < len(lines) and lines[i].startswith('@@ '):
        hunk_result = _parse_hunk(lines, i)
        if not hunk_result:
            break
            
        hunk_header, hunk_lines, next_idx = hunk_result
        hunks.append((hunk_header, hunk_lines))
        
        # Process the lines in this hunk, respecting the header line numbers
        original_line_num = hunk_header.original_start
        new_line_num = hunk_header.new_start
        
        # For each line in the hunk content
        for line in hunk_lines:
            if line.startswith(' '):  # Context line
                # Exists in both original and new
                original_line_num += 1
                new_line_num += 1
            elif line.startswith('-'):  # Removed line
                # Exists only in original
                original_changes[original_line_num] = line[1:]
                original_line_num += 1
            elif line.startswith('+'):  # Added line
                # Exists only in new
                new_changes[new_line_num] = line[1:]
                new_line_num += 1
        
        i = next_idx
    
    # For deleted files, use b/original_path instead of /dev/null
    if is_deleted and '/dev/null' in (new_file or ''):
        path_parts = old_file.split('/')
        if len(path_parts) > 1:
            new_file = "b/" + path_parts[-1]  # Use old filename with b/ prefix
    
    return FileDiff(
        old_file=old_file,
        new_file=new_file,
        hunks=hunks,
        original_changes=original_changes,
        new_changes=new_changes,
        is_new=is_new,
        is_deleted=is_deleted,
        is_binary=is_binary,
        is_rename=is_rename
    )


def _parse_hunk(lines: List[str], start_idx: int) -> Optional[Tuple[HunkHeader, List[str], int]]:
    """
    Parse a single hunk from the diff.
    
    Args:
        lines: The lines of the diff.
        start_idx: The index of the hunk header line.
        
    Returns:
        A tuple of (hunk_header, hunk_lines, next_idx) if successful, 
        or None if the hunk could not be parsed.
    """
    if start_idx >= len(lines) or not lines[start_idx].startswith('@@ '):
        return None
    
    # Parse hunk header
    header_match = RE_HUNK_HEADER.match(lines[start_idx])
    if not header_match:
        logger.error(f"Failed to parse hunk header: {lines[start_idx]}")
        return None
    
    original_start = int(header_match.group(1))
    original_count = int(header_match.group(2) or 1)
    new_start = int(header_match.group(3))
    new_count = int(header_match.group(4) or 1)
    
    # Create hunk header object
    hunk_header = HunkHeader(
        original_start=original_start,
        original_count=original_count,
        new_start=new_start,
        new_count=new_count
    )
    
    # Parse hunk content
    hunk_lines = []
    i = start_idx + 1
    
    # Validate line counts
    remaining_orig_lines = original_count
    remaining_new_lines = new_count
    
    while i < len(lines):
        line = lines[i]
        # Check for end of hunk markers
        if line.startswith('@@ ') or line.startswith('diff --git'):
            break
            
        # Empty line (could be context or end of file)
        if not line:
            hunk_lines.append(' ')
            remaining_orig_lines -= 1
            remaining_new_lines -= 1
            i += 1
            continue
            
        # Line classification
        if line.startswith(' '):  # Context line
            hunk_lines.append(line)
            remaining_orig_lines -= 1
            remaining_new_lines -= 1
        elif line.startswith('-'):  # Removed line
            hunk_lines.append(line)
            remaining_orig_lines -= 1
        elif line.startswith('+'):  # Added line
            hunk_lines.append(line)
            remaining_new_lines -= 1
        else:  # Unexpected line format, treat as context
            hunk_lines.append(' ' + line)
            remaining_orig_lines -= 1
            remaining_new_lines -= 1
            
        i += 1
        
        # Stop when we've processed all lines in the hunk
        if remaining_orig_lines <= 0 and remaining_new_lines <= 0:
            break
    
    return hunk_header, hunk_lines, i


def get_changed_line_numbers(file_diff: FileDiff) -> Tuple[Set[int], Set[int]]:
    """
    Get the set of changed line numbers for a file diff.
    
    Args:
        file_diff: FileDiff object
        
    Returns:
        Tuple of (original changed lines, new changed lines)
    """
    # Use the dictionaries that already contain the changed lines
    return set(file_diff.original_changes.keys()), set(file_diff.new_changes.keys())


def get_hunk_at_line(file_diff: FileDiff, new_line: int) -> Optional[Tuple[HunkHeader, List[str]]]:
    """
    Find the hunk containing a specific line number in the new file.
    
    Args:
        file_diff: FileDiff object
        new_line: Line number in the new file
        
    Returns:
        Hunk tuple if found, None otherwise
    """
    for hunk in file_diff.hunks:
        header = hunk[0]
        new_start = header.new_start
        new_end = new_start + header.new_count - 1
        
        if new_start <= new_line <= new_end:
            return hunk
    
    return None


def map_original_to_new_line(file_diff: FileDiff, original_line: int) -> Optional[int]:
    """
    Map a line number from the original file to the new file.
    
    Args:
        file_diff: The file diff.
        original_line: Line number in the original file.
        
    Returns:
        The corresponding line number in the new file, or None if the line was deleted.
    """
    # Handle special cases
    if file_diff.is_deleted:
        return None  # Line doesn't exist in new file
    
    if file_diff.is_new and original_line > 0:
        return None  # Original line doesn't exist for new files
    
    # Check if the line was deleted (exactly matches a key in original_changes)
    if original_line in file_diff.original_changes:
        # Check all hunks to see if this line is mapped or deleted
        for header, content in file_diff.hunks:
            if header.original_start <= original_line < header.original_start + header.original_count:
                # Line is in this hunk
                # Calculate position within the hunk
                pos_in_hunk = original_line - header.original_start
                
                # Scan through content to find line mapping
                curr_orig = 0
                curr_new = 0
                
                for line in content:
                    if curr_orig == pos_in_hunk:
                        if line.startswith('-'):
                            # This line was deleted
                            return None
                        # Otherwise it's a context line that exists in both versions
                        return header.new_start + curr_new
                    
                    if line.startswith(' '):  # Context line
                        curr_orig += 1
                        curr_new += 1
                    elif line.startswith('-'):  # Deleted line
                        curr_orig += 1
                    elif line.startswith('+'):  # Added line
                        curr_new += 1
    
    # Check if the line is within any hunk
    for header, content in file_diff.hunks:
        if header.original_start <= original_line < header.original_start + header.original_count:
            # Line is in this hunk, compute its new position
            line_offset = 0
            orig_pos = 0
            new_pos = 0
            
            for line in content:
                if header.original_start + orig_pos == original_line:
                    if line.startswith('-'):
                        # Line was removed
                        return None
                    else:
                        # Line exists in new file
                        return header.new_start + new_pos
                
                if line.startswith(' '):  # Context line
                    orig_pos += 1
                    new_pos += 1
                elif line.startswith('-'):  # Removed line
                    orig_pos += 1
                elif line.startswith('+'):  # Added line
                    new_pos += 1
                    line_offset += 1
            
            # If we got here, the line wasn't explicitly handled above
            # Calculate based on additions/deletions before this line
            deletions_before = 0
            additions_before = 0
            
            orig_pos = 0
            for line in content:
                if header.original_start + orig_pos >= original_line:
                    break
                
                if line.startswith('-'):
                    deletions_before += 1
                    orig_pos += 1
                elif line.startswith('+'):
                    additions_before += 1
                elif line.startswith(' '):
                    orig_pos += 1
            
            return original_line + additions_before - deletions_before
    
    # If not in any hunk, calculate based on hunks before this line
    offset = 0
    for header, _ in file_diff.hunks:
        if header.original_start + header.original_count <= original_line:
            # This hunk is entirely before our line
            offset += header.new_count - header.original_count
    
    return original_line + offset


def map_new_to_original_line(file_diff: FileDiff, new_line: int) -> Optional[int]:
    """
    Map a line number from the new file to the original file.
    
    Args:
        file_diff: FileDiff object
        new_line: Line number in the new file
        
    Returns:
        Corresponding line number in the original file, or None if unmappable
    """
    # Handle special cases
    if file_diff.is_new:
        return None  # No original lines for new files
    
    # First check if this is an added line
    if new_line in file_diff.new_changes:
        return None  # Added lines don't map to original
    
    # Check if the line is within any hunk
    for header, content in file_diff.hunks:
        if header.new_start <= new_line < header.new_start + header.new_count:
            # Calculate position within the hunk
            hunk_pos = new_line - header.new_start
            
            # Count lines in the hunk up to the target position
            orig_count = 0
            new_count = 0
            
            for line in content:
                if new_count == hunk_pos:
                    if line.startswith(' '):  # Context line
                        return header.original_start + orig_count
                    elif line.startswith('+'):  # Added line
                        return None
                    # Should not reach here with a minus line
                
                if line.startswith(' '):  # Context line
                    orig_count += 1
                    new_count += 1
                elif line.startswith('-'):  # Removed line
                    orig_count += 1
                elif line.startswith('+'):  # Added line
                    new_count += 1
    
    # If the line is not in any hunk, calculate based on hunks before this line
    offset = 0
    for header, _ in file_diff.hunks:
        if header.new_start + header.new_count <= new_line:
            # This hunk is entirely before our line
            offset += header.original_count - header.new_count
    
    return new_line + offset


def generate_line_map(file_diff: FileDiff) -> Dict[int, Optional[int]]:
    """
    Generate a complete mapping of line numbers from new to original.
    
    Args:
        file_diff: FileDiff object
        
    Returns:
        Dictionary mapping new line numbers to original line numbers (None for added lines)
    """
    line_map = {}
    
    # Handle special cases
    if file_diff.is_new:
        # All lines in new files map to None
        max_line = max(file_diff.new_changes.keys(), default=0)
        for i in range(1, max_line + 1):
            line_map[i] = None
        return line_map
    
    if file_diff.is_deleted:
        return line_map  # No new lines to map
    
    # For each line in the new file, map it to the original
    # We need to determine the highest line number in the new file
    max_line = 0
    for header, _ in file_diff.hunks:
        max_line = max(max_line, header.new_start + header.new_count - 1)
    
    # Map each line
    for i in range(1, max_line + 1):
        line_map[i] = map_new_to_original_line(file_diff, i)
    
    return line_map


def extract_function_diff(file_diff: FileDiff, func_start: int, func_end: int) -> Optional[str]:
    """
    Extract a diff limited to a specific function range in the new file.
    
    Args:
        file_diff: The file diff.
        func_start: The function start line in the new file.
        func_end: The function end line in the new file.
        
    Returns:
        A string containing the diff limited to the function, or None if there are no changes.
    """
    if file_diff.is_binary:
        return None
    
    # Find hunks that overlap with the function
    relevant_hunks = []
    
    for header, content in file_diff.hunks:
        hunk_new_end = header.new_start + header.new_count - 1
        
        # Check if this hunk overlaps with the function range
        if (header.new_start <= func_end and hunk_new_end >= func_start):
            relevant_hunks.append((header, content))
    
    if not relevant_hunks:
        return None
    
    # Check if any changes actually affect the function
    has_changes = False
    
    # Helper function to check if a line is within the function bounds
    def is_in_function_range(line_num):
        return func_start <= line_num <= func_end
    
    # Check for changes in the function range
    for line_num in file_diff.new_changes:
        if is_in_function_range(line_num):
            has_changes = True
            break
    
    # Check if any original line that was removed maps to within the function
    for original_line_num in file_diff.original_changes:
        mapped_line = map_original_to_new_line(file_diff, original_line_num)
        if mapped_line is not None and is_in_function_range(mapped_line):
            has_changes = True
            break
    
    if not has_changes:
        return None
    
    # Generate the function-specific diff (without full diff headers)
    result = []
    
    # Add only the hunks
    for header, content in relevant_hunks:
        result.append(f"@@ -{header.original_start},{header.original_count} +{header.new_start},{header.new_count} @@")
        result.extend(content)
    
    return '\n'.join(result)


def parse_github_patch(patch: str, file_path: str) -> Optional[FileDiff]:
    """
    Parse a GitHub API patch directly, without needing to convert to full diff format.
    GitHub API patches start with @@ and don't include the diff headers.
    
    Args:
        patch: GitHub API patch (starts with @@)
        file_path: Path of the file being patched
        
    Returns:
        FileDiff object with the parsed patch details
    """
    if not patch or not patch.startswith('@@'):
        logger.warning(f"Not a valid GitHub API patch: {patch[:20]}...")
        return None
    
    # Set up file paths
    old_file = f"a/{file_path}"
    new_file = f"b/{file_path}"
    
    # Parse hunks
    hunks = []
    original_changes = {}
    new_changes = {}
    
    # Split the patch into lines
    lines = patch.split('\n')
    i = 0
    
    while i < len(lines):
        # Parse hunk header
        if not lines[i].startswith('@@'):
            i += 1
            continue
            
        header_match = RE_HUNK_HEADER.match(lines[i])
        if not header_match:
            logger.warning(f"Failed to parse hunk header: {lines[i]}")
            i += 1
            continue
        
        original_start = int(header_match.group(1))
        original_count = int(header_match.group(2) or 1)
        new_start = int(header_match.group(3))
        new_count = int(header_match.group(4) or 1)
        
        # Create hunk header
        hunk_header = HunkHeader(
            original_start=original_start,
            original_count=original_count,
            new_start=new_start,
            new_count=new_count
        )
        
        # Parse hunk content
        hunk_lines = []
        i += 1  # Move past the header
        
        # Keep track of line numbers for mapping
        original_line_num = original_start
        new_line_num = new_start
        
        # Continue until the next hunk header or end of patch
        while i < len(lines) and not lines[i].startswith('@@'):
            line = lines[i]
            hunk_lines.append(line)
            
            # Track changes based on line type
            if line.startswith(' '):  # Context line
                original_line_num += 1
                new_line_num += 1
            elif line.startswith('-'):  # Removed line
                original_changes[original_line_num] = line[1:]
                original_line_num += 1
            elif line.startswith('+'):  # Added line
                new_changes[new_line_num] = line[1:]
                new_line_num += 1
            elif line == '':  # Empty line (could be context)
                # Treat empty lines as context
                original_line_num += 1
                new_line_num += 1
            
            i += 1
        
        # Add the hunk to our list
        hunks.append((hunk_header, hunk_lines))
    
    # Return the FileDiff object
    return FileDiff(
        old_file=old_file,
        new_file=new_file,
        hunks=hunks,
        original_changes=original_changes,
        new_changes=new_changes,
        is_new=False,
        is_deleted=False,
        is_binary=False,
        is_rename=False
    )


def extract_function_diff_from_patch(patch: str, file_path: str, func_start: int, func_end: int) -> Optional[str]:
    """
    Extract a diff for a specific function directly from a GitHub API patch.
    
    Args:
        patch: GitHub API patch string
        file_path: Path of the file
        func_start: Function start line in the new file
        func_end: Function end line in the new file
        
    Returns:
        A function-specific diff string, or None if no changes in the function
    """
    if not patch or not patch.startswith('@@'):
        return None
    
    # Directly extract the relevant parts from the patch without creating a FileDiff
    lines = patch.split('\n')
    relevant_hunks = []
    has_changes = False
    
    i = 0
    while i < len(lines):
        if not lines[i].startswith('@@'):
            i += 1
            continue
            
        # Parse hunk header
        header_match = RE_HUNK_HEADER.match(lines[i])
        if not header_match:
            i += 1
            continue
            
        original_start = int(header_match.group(1))
        original_count = int(header_match.group(2) or 1)
        new_start = int(header_match.group(3))
        new_count = int(header_match.group(4) or 1)
        
        # Calculate hunk end
        new_end = new_start + new_count - 1
        
        # Check if this hunk overlaps with our function
        if new_start <= func_end and new_end >= func_start:
            # Find the end of this hunk
            hunk_start = i
            i += 1
            while i < len(lines) and not lines[i].startswith('@@'):
                # Check if any added/changed lines fall within our function
                line = lines[i]
                if line.startswith('+'):
                    # This is a simplified check - we're assuming line numbers 
                    # based on hunk position
                    # For a more accurate check, we'd need to track positions
                    current_line = new_start + (i - hunk_start - 1)
                    if func_start <= current_line <= func_end:
                        has_changes = True
                elif line.startswith('-'):
                    # For removed lines, we need more complex logic to map
                    # original line to new position, but this is a start
                    has_changes = True
                
                i += 1
                
            # If we have changes or if we can't be certain, include the hunk
            if has_changes:
                relevant_hunks.append((hunk_start, i))
            continue
        
        # Skip to the next hunk
        i += 1
        while i < len(lines) and not lines[i].startswith('@@'):
            i += 1
    
    # If we didn't find any relevant changes, return None
    if not relevant_hunks:
        return None
    
    # Extract only the relevant hunks
    result = []
    for start, end in relevant_hunks:
        result.extend(lines[start:end])
    
    return '\n'.join(result)


def extract_changed_lines(patch: str) -> Tuple[Set[int], Set[int]]:
    """
    Extract changed line numbers directly from a patch.
    Returns (original_changed_lines, new_changed_lines) for efficient function detection.
    
    This optimized function eliminates unnecessary processing and data structures.
    """
    # Sets are more efficient for line number lookups
    original_changed = set()
    new_changed = set()
    
    # Quick validation
    if not patch or not patch.startswith('@@'):
        return original_changed, new_changed
    
    lines = patch.split('\n')
    i = 0
    
    # Single pass through the patch
    while i < len(lines):
        # Skip non-header lines at this level
        if not lines[i].startswith('@@'):
            i += 1
            continue
            
        # Extract line numbers from header
        header_match = RE_HUNK_HEADER.match(lines[i])
        if not header_match:
            i += 1
            continue
        
        # Get starting line numbers
        orig_line = int(header_match.group(1))
        new_line = int(header_match.group(3))
        
        # Move past header
        i += 1
        
        # Process lines in this hunk
        while i < len(lines) and not lines[i].startswith('@@'):
            line = lines[i]
            
            # Fast character-based checking
            if not line:  # Empty line
                orig_line += 1
                new_line += 1
            elif line.startswith(' '):  # Context line
                orig_line += 1
                new_line += 1
            elif line.startswith('-'):  # Removed line
                original_changed.add(orig_line)
                orig_line += 1
            elif line.startswith('+'):  # Added line
                new_changed.add(new_line)
                new_line += 1
            
            i += 1
    
    return original_changed, new_changed


def create_simple_diff(content_old: str, content_new: str) -> str:
    """
    Create a simple line-by-line diff between two pieces of content.
    """
    if not content_old and content_new:
        # All additions
        return '\n'.join([f"+{line}" for line in content_new.splitlines()])
    
    if content_old and not content_new:
        # All deletions
        return '\n'.join([f"-{line}" for line in content_old.splitlines()])
    
    # Use difflib for line-by-line comparison
    diff_lines = []
    for line in difflib.unified_diff(
        content_old.splitlines(),
        content_new.splitlines(),
        n=0,  # No context
        lineterm=''
    ):
        # Skip headers
        if line.startswith('---') or line.startswith('+++') or line.startswith('@@'):
            continue
        diff_lines.append(line)
    
    return '\n'.join(diff_lines) 