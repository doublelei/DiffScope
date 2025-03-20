"""
Function detection and change analysis module.

This module integrates diff parsing with function detection to identify
changed functions in source code and analyze the nature of those changes.
"""

from typing import List, Dict, Optional, Set, Tuple, Any
import logging
import difflib
from ..utils.diff_utils import (
    parse_unified_diff,
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
    
    if file_diff.is_new_file:
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
    
    if file_diff.is_deleted_file:
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