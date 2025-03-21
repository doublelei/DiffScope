"""
Function detection and change analysis module.

This module integrates diff parsing with function detection to identify
changed functions in source code and analyze the nature of those changes.
"""

from typing import List, Dict, Optional, Set, Tuple, Any, Union
import logging
import difflib
from ..utils.diff_utils import (
    parse_diff,
    get_changed_line_numbers,
    map_original_to_new_line,
    map_new_to_original_line,
    extract_function_diff,
    FileDiff
)
from ..parsers.function_parser import (
    parse_functions,
    get_function_at_line,
    extract_function_content
)
from ..models import ModifiedFunction, FunctionChangeType

# Set up logging
logger = logging.getLogger(__name__)


def extract_functions_from_content(file_content: str, language: str, file_path: str = None) -> List[Dict]:
    """
    Extract function information from file content.
    
    Args:
        file_content: Content of the file
        language: Programming language of the file
        file_path: Optional path to the file for reference
        
    Returns:
        List of function information dictionaries
    """
    if not file_content:
        return []
        
    return parse_functions(file_content, language)


def create_modified_functions(
    original_content: Optional[str],
    new_content: Optional[str],
    language: str,
    file_path: str,
    patch_or_file_diff: Optional[Union[str, FileDiff]] = None
) -> List[ModifiedFunction]:
    """
    Identify functions that were modified between two versions of a file.
    
    Args:
        original_content: Content of the original file
        new_content: Content of the new file
        language: Programming language
        file_path: Path to the file
        patch_or_file_diff: Optional unified diff patch (string) or FileDiff object
        
    Returns:
        List of ModifiedFunction objects
    """
    # Handle special cases for new or deleted files
    if not original_content and new_content:
        # New file - all functions are added
        new_functions = parse_functions(new_content, language)
        return [
            ModifiedFunction(
                name=func['name'],
                file=file_path,
                type=func['node_type'],
                change_type=FunctionChangeType.ADDED,
                original_start=None,
                original_end=None,
                new_start=func['start_line'],
                new_end=func['end_line'],
                changes=func['end_line'] - func['start_line'] + 1,
                diff=None  # No diff for new files
            )
            for func in new_functions
        ]
    
    if original_content and not new_content:
        # Deleted file - all functions are deleted
        orig_functions = parse_functions(original_content, language)
        return [
            ModifiedFunction(
                name=func['name'],
                file=file_path,
                type=func['node_type'],
                change_type=FunctionChangeType.DELETED,
                original_start=func['start_line'],
                original_end=func['end_line'],
                new_start=None,
                new_end=None,
                changes=func['end_line'] - func['start_line'] + 1,
                diff=None  # No diff for deleted files
            )
            for func in orig_functions
        ]
    
    # Handle the patch or FileDiff argument
    file_diff = None
    
    if isinstance(patch_or_file_diff, FileDiff):
        # Already have a FileDiff object
        file_diff = patch_or_file_diff
    elif isinstance(patch_or_file_diff, str):
        # Parse the patch string to get FileDiff objects
        file_diffs = parse_diff(patch_or_file_diff)
        if file_diffs:
            file_diff = file_diffs[0]
    
    # If no patch/file_diff is provided but we have both contents, generate a diff
    if not file_diff and original_content and new_content:
        # Generate a unified diff
        diff_lines = list(difflib.unified_diff(
            original_content.splitlines(),
            new_content.splitlines(),
            fromfile='original',
            tofile='modified',
            lineterm=''
        ))
        patch = '\n'.join(diff_lines)
        file_diffs = parse_diff(patch)
        if file_diffs:
            file_diff = file_diffs[0]
    
    if file_diff:
        # Analyze the file diff
        return analyze_file_diff(file_diff, original_content, new_content, language, file_path)
    
    # If we get here, we couldn't analyze the changes
    logger.warning(f"Could not analyze changes for {file_path}")
    return []


# Keeping the original function for backward compatibility
def detect_modified_functions(
    original_content: str,
    new_content: str,
    file_diff: FileDiff,
    language: str,
    file_path: str
) -> List[ModifiedFunction]:
    """
    Detect and analyze functions that were modified between versions.
    
    Args:
        original_content: Content of the original file
        new_content: Content of the new file
        file_diff: Parsed file diff
        language: Programming language
        file_path: Path to the file
        
    Returns:
        List of ModifiedFunction objects
    """
    # Parse functions in both versions
    original_functions = parse_functions(original_content, language)
    new_functions = parse_functions(new_content, language)
    
    # Get changed line numbers from diff
    orig_changed_lines, new_changed_lines = get_changed_line_numbers(file_diff)
    
    # Track detected functions
    modified_functions = []
    
    # First, find functions with changes in the new version
    for func in new_functions:
        func_start = func['start_line']
        func_end = func['end_line']
        
        # Check if any changed lines overlap with this function
        has_changes = any(func_start <= line <= func_end for line in new_changed_lines)
        
        if has_changes:
            # Find the corresponding function in the original version (if it exists)
            original_func = _find_matching_function(func, original_functions)
            
            # Determine change type and analyze
            if original_func:
                # Modified function
                func_diff = extract_function_diff(file_diff, func_start, func_end)
                change_type = _determine_change_type(original_func, func, original_content, new_content)
                
                modified_func = ModifiedFunction(
                    name=func['name'],
                    file=file_path,
                    type=func['node_type'],
                    change_type=change_type,
                    original_start=original_func['start_line'],
                    original_end=original_func['end_line'],
                    new_start=func_start,
                    new_end=func_end,
                    changes=_count_changes(func_diff),
                    diff=func_diff
                )
                modified_functions.append(modified_func)
            else:
                # New function (could also be a renamed function, but we'll detect that later)
                modified_func = ModifiedFunction(
                    name=func['name'],
                    file=file_path,
                    type=func['node_type'],
                    change_type=FunctionChangeType.ADDED,
                    original_start=None,
                    original_end=None,
                    new_start=func_start,
                    new_end=func_end,
                    changes=func_end - func_start + 1,  # All lines are additions
                    diff=extract_function_diff(file_diff, func_start, func_end)
                )
                modified_functions.append(modified_func)
    
    # Find deleted functions (functions in original that don't match any new function)
    for orig_func in original_functions:
        # Skip if already matched
        if any(mf.original_start == orig_func['start_line'] for mf in modified_functions if mf.original_start is not None):
            continue
        
        # Check if this function includes any changed lines
        has_changes = any(orig_func['start_line'] <= line <= orig_func['end_line'] for line in orig_changed_lines)
        
        if has_changes:
            # Try to find if it was renamed (check for similar functions in new version)
            renamed_to = _find_renamed_function(orig_func, original_content, new_functions, new_content)
            
            if renamed_to:
                # This function was renamed - update the ADDED function to RENAMED
                for i, mf in enumerate(modified_functions):
                    if (mf.change_type == FunctionChangeType.ADDED and 
                        mf.new_start == renamed_to['start_line']):
                        # Update to a renamed function
                        modified_functions[i] = ModifiedFunction(
                            name=renamed_to['name'],
                            file=file_path,
                            type=renamed_to['node_type'],
                            change_type=FunctionChangeType.RENAMED,
                            original_name=orig_func['name'],
                            original_start=orig_func['start_line'],
                            original_end=orig_func['end_line'],
                            new_start=renamed_to['start_line'],
                            new_end=renamed_to['end_line'],
                            changes=modified_functions[i].changes,
                            diff=modified_functions[i].diff
                        )
                        break
            else:
                # This function was deleted
                modified_func = ModifiedFunction(
                    name=orig_func['name'],
                    file=file_path,
                    type=orig_func['node_type'],
                    change_type=FunctionChangeType.DELETED,
                    original_start=orig_func['start_line'],
                    original_end=orig_func['end_line'],
                    new_start=None,
                    new_end=None,
                    changes=orig_func['end_line'] - orig_func['start_line'] + 1,  # All lines are removals
                    diff=None
                )
                modified_functions.append(modified_func)
    
    return modified_functions


def analyze_function_changes(
    before_func: Dict, 
    after_func: Dict,
    before_content: str, 
    after_content: str,
    patch_or_file_diff: Union[str, FileDiff, None] = None
) -> Dict:
    """
    Analyze what aspects of a function changed between versions.
    
    Args:
        before_func: Function information before changes
        after_func: Function information after changes
        before_content: File content before changes
        after_content: File content after changes
        patch_or_file_diff: Unified diff of the file (string) or FileDiff object
        
    Returns:
        Dictionary with change information
    """
    change_type = _determine_change_type(before_func, after_func, before_content, after_content)
    
    # Extract function contents
    before_func_content = extract_function_content(before_content, before_func)
    after_func_content = extract_function_content(after_content, after_func)
    
    # Handle the diff
    func_diff = None
    
    if isinstance(patch_or_file_diff, FileDiff):
        # Already have a FileDiff object
        file_diff = patch_or_file_diff
        if after_func:
            func_diff = extract_function_diff(
                file_diff, 
                after_func['start_line'], 
                after_func['end_line']
            )
    elif isinstance(patch_or_file_diff, str):
        # Parse the patch string to get FileDiff objects
        file_diffs = parse_diff(patch_or_file_diff)
        if file_diffs and after_func:
            func_diff = extract_function_diff(
                file_diffs[0], 
                after_func['start_line'], 
                after_func['end_line']
            )
    elif patch_or_file_diff is None and before_content and after_content:
        # Generate a diff if none provided
        diff_lines = list(difflib.unified_diff(
            before_content.splitlines(),
            after_content.splitlines(),
            fromfile='original',
            tofile='modified',
            lineterm=''
        ))
        patch = '\n'.join(diff_lines)
        file_diffs = parse_diff(patch)
        if file_diffs and after_func:
            func_diff = extract_function_diff(
                file_diffs[0], 
                after_func['start_line'], 
                after_func['end_line']
            )
    
    # Count changes
    changes = _count_changes(func_diff) if func_diff else 0
    
    return {
        'change_type': change_type,
        'before_content': before_func_content,
        'after_content': after_func_content,
        'diff': func_diff,
        'changes': changes
    }


def detect_renamed_functions(modified_functions: List[ModifiedFunction]) -> None:
    """
    Identify renamed functions by comparing added and deleted functions.
    Modifies the provided list in-place to update change types.
    
    Args:
        modified_functions: List of ModifiedFunction objects
    """
    # Collect added and deleted functions
    added_functions = [f for f in modified_functions if f.change_type == FunctionChangeType.ADDED]
    deleted_functions = [f for f in modified_functions if f.change_type == FunctionChangeType.DELETED]
    
    # Skip if either list is empty
    if not added_functions or not deleted_functions:
        return
    
    # Track which functions have been processed
    processed_added = set()
    processed_deleted = set()
    
    # Find potential renamed pairs
    for added_idx, added_func in enumerate(added_functions):
        for deleted_idx, deleted_func in enumerate(deleted_functions):
            # Skip already processed functions
            if deleted_idx in processed_deleted:
                continue
                
            # Check if these are a potential rename pair (same file, similar content, etc.)
            if added_func.file == deleted_func.file:
                # For now, simple implementation: mark the first pair of added/deleted 
                # functions from the same file as a rename
                # In a real implementation, calculate similarity between content
                
                # Update the added function to be a renamed function
                for i, mf in enumerate(modified_functions):
                    if (mf is added_func):
                        modified_functions[i] = ModifiedFunction(
                            name=added_func.name,
                            file=added_func.file,
                            type=added_func.type,
                            change_type=FunctionChangeType.RENAMED,
                            original_name=deleted_func.name,
                            original_start=deleted_func.original_start,
                            original_end=deleted_func.original_end,
                            new_start=added_func.new_start,
                            new_end=added_func.new_end,
                            changes=added_func.changes,
                            diff=added_func.diff
                        )
                        processed_added.add(added_idx)
                        processed_deleted.add(deleted_idx)
                        
                        # Remove the deleted function as it's now accounted for
                        modified_functions.remove(deleted_func)
                        break
                
                if added_idx in processed_added:
                    # We've processed this added function, move to the next one
                    break


def calculate_function_similarity(content1: str, content2: str) -> float:
    """
    Calculate similarity between two function contents.
    
    Args:
        content1: First function content
        content2: Second function content
        
    Returns:
        Similarity score between 0 and 1
    """
    if not content1 or not content2:
        return 0.0
    
    # Normalize whitespace
    content1 = ' '.join(content1.split())
    content2 = ' '.join(content2.split())
    
    # Use difflib to calculate similarity
    return difflib.SequenceMatcher(None, content1, content2).ratio()


def _find_matching_function(func: Dict, candidates: List[Dict]) -> Optional[Dict]:
    """
    Find matching function in a list of candidate functions.
    
    Args:
        func: Function to find a match for
        candidates: List of candidate functions
        
    Returns:
        Matching function dict or None if no match found
    """
    # First try exact name match
    for candidate in candidates:
        if candidate['name'] == func['name']:
            return candidate
    
    # No match found
    return None


def _find_renamed_function(
    orig_func: Dict,
    orig_content: str,
    new_funcs: List[Dict],
    new_content: str,
    similarity_threshold: float = 0.7
) -> Optional[Dict]:
    """
    Find a potential renamed version of a function based on content similarity.
    
    Args:
        orig_func: Original function
        orig_content: Original file content
        new_funcs: List of functions in the new version
        new_content: New file content
        similarity_threshold: Threshold for considering functions similar (0.0 to 1.0)
        
    Returns:
        Dict of renamed function or None if no match
    """
    # Extract original function content
    orig_func_content = extract_function_content(orig_content, orig_func)
    
    if not orig_func_content:
        return None
    
    best_match = None
    best_similarity = 0.0
    
    for new_func in new_funcs:
        # Skip functions with the same name (these would be modifications, not renames)
        if new_func['name'] == orig_func['name']:
            continue
        
        # Extract new function content
        new_func_content = extract_function_content(new_content, new_func)
        
        if not new_func_content:
            continue
        
        # Calculate similarity using difflib's SequenceMatcher
        similarity = difflib.SequenceMatcher(None, orig_func_content, new_func_content).ratio()
        
        if similarity > best_similarity and similarity >= similarity_threshold:
            best_similarity = similarity
            best_match = new_func
    
    return best_match


def _determine_change_type(
    orig_func: Dict,
    new_func: Dict,
    orig_content: str,
    new_content: str
) -> FunctionChangeType:
    """
    Determine the type of change for a modified function.
    
    Args:
        orig_func: Original function
        new_func: New function
        orig_content: Original file content
        new_content: New file content
        
    Returns:
        FunctionChangeType enum value
    """
    # Extract function signatures (first line of each function)
    orig_lines = orig_content.splitlines()
    new_lines = new_content.splitlines()
    
    if orig_func['start_line'] <= len(orig_lines) and new_func['start_line'] <= len(new_lines):
        orig_signature = orig_lines[orig_func['start_line'] - 1]
        new_signature = new_lines[new_func['start_line'] - 1]
        
        if orig_signature != new_signature:
            return FunctionChangeType.SIGNATURE_CHANGED
    
    # Check if only docstring changed
    orig_func_content = extract_function_content(orig_content, orig_func)
    new_func_content = extract_function_content(new_content, new_func)
    
    if orig_func_content and new_func_content:
        # Remove the first line (signature) from both
        orig_body = '\n'.join(orig_func_content.splitlines()[1:])
        new_body = '\n'.join(new_func_content.splitlines()[1:])
        
        # Check if only docstring changed (assumes docstring is right after signature)
        if _is_only_docstring_changed(orig_body, new_body):
            return FunctionChangeType.DOCSTRING_CHANGED
    
    # Default to body changed
    return FunctionChangeType.BODY_CHANGED


def _is_only_docstring_changed(orig_body: str, new_body: str) -> bool:
    """
    Check if only the docstring changed between two function bodies.
    
    Args:
        orig_body: Original function body
        new_body: New function body
        
    Returns:
        True if only docstring changed, False otherwise
    """
    # Find docstring in both versions
    orig_docstring = _extract_docstring(orig_body)
    new_docstring = _extract_docstring(new_body)
    
    if orig_docstring != new_docstring:
        # Docstrings are different
        
        # Remove docstrings and compare the rest
        orig_without_docstring = orig_body.replace(orig_docstring, "", 1).strip() if orig_docstring else orig_body
        new_without_docstring = new_body.replace(new_docstring, "", 1).strip() if new_docstring else new_body
        
        # If the rest is the same, only docstring changed
        return orig_without_docstring == new_without_docstring
    
    return False


def _extract_docstring(code: str) -> Optional[str]:
    """
    Extract the docstring from a code block.
    
    Args:
        code: Code block to extract docstring from
        
    Returns:
        Docstring or None if no docstring found
    """
    # This is a simple implementation that works for most Python docstrings
    # A more robust implementation would use the ast module
    code = code.strip()
    
    # Check for triple-quoted docstring patterns
    for pattern in ['"""', "'''"]:
        if code.startswith(pattern):
            end = code.find(pattern, len(pattern))
            if end != -1:
                return code[:end + len(pattern)]
    
    return None


def _count_changes(diff: Optional[str]) -> int:
    """
    Count the number of changed lines in a diff.
    
    Args:
        diff: Function-specific diff
        
    Returns:
        Number of changed lines (additions + deletions)
    """
    if not diff:
        return 0
    
    additions = 0
    deletions = 0
    
    for line in diff.splitlines():
        if line.startswith('+') and not line.startswith('+++'):
            additions += 1
        elif line.startswith('-') and not line.startswith('---'):
            deletions += 1
    
    return additions + deletions


def analyze_file_diff(
    file_diff: FileDiff,
    original_content: str,
    new_content: str,
    language: str,
    file_path: str
) -> List[ModifiedFunction]:
    """
    Analyze a file diff to identify function-level changes.
    
    Args:
        file_diff: Parsed file diff
        original_content: Content of the original file
        new_content: Content of the new file
        language: Programming language
        file_path: Path to the file
        
    Returns:
        List of ModifiedFunction objects
    """
    if file_diff.is_binary:
        logger.info(f"Skipping binary file: {file_path}")
        return []
    
    if file_diff.is_new:
        # All functions are new
        new_functions = parse_functions(new_content, language)
        return [
            ModifiedFunction(
                name=func['name'],
                file=file_path,
                type=func['node_type'],
                change_type=FunctionChangeType.ADDED,
                original_start=None,
                original_end=None,
                new_start=func['start_line'],
                new_end=func['end_line'],
                changes=func['end_line'] - func['start_line'] + 1,
                diff=None  # No diff for new files
            )
            for func in new_functions
        ]
    
    if file_diff.is_deleted:
        # All functions are deleted
        orig_functions = parse_functions(original_content, language)
        return [
            ModifiedFunction(
                name=func['name'],
                file=file_path,
                type=func['node_type'],
                change_type=FunctionChangeType.DELETED,
                original_start=func['start_line'],
                original_end=func['end_line'],
                new_start=None,
                new_end=None,
                changes=func['end_line'] - func['start_line'] + 1,
                diff=None  # No diff for deleted files
            )
            for func in orig_functions
        ]
    
    # Normal case - detect modified functions
    return detect_modified_functions(
        original_content, new_content, file_diff, language, file_path
    ) 