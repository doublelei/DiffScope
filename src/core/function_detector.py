"""
Function detection and change analysis module.

This module integrates diff parsing with function detection to identify
changed functions in source code and analyze the nature of those changes.
"""

from typing import List, Dict, Optional, Set, Tuple, Any, Union
import logging
import difflib
from ..utils.diff_utils import (
    parse_github_patch,
    get_changed_line_numbers,
    extract_function_diff,
    FileDiff,
)
from ..parsers.function_parser import (
    parse_functions,
    extract_function_content,
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


def _create_modified_function(
    func_info: Dict,
    file_path: str,
    change_type: FunctionChangeType,
    original_content: Optional[str] = None,
    new_content: Optional[str] = None,
    original_start: Optional[int] = None, 
    original_end: Optional[int] = None,
    new_start: Optional[int] = None,
    new_end: Optional[int] = None,
    original_name: Optional[str] = None,
    diff: Optional[str] = None
) -> ModifiedFunction:
    """
    Create a ModifiedFunction object from function info and related parameters.
    
    Args:
        func_info: Function information dictionary from parse_functions
        file_path: Path to the file containing the function
        change_type: Type of change (ADDED, MODIFIED, REMOVED, RENAMED)
        original_content: Content of the function in the original version
        new_content: Content of the function in the new version
        original_start: Start line in the original version
        original_end: End line in the original version
        new_start: Start line in the new version
        new_end: End line in the new version
        original_name: Original name for renamed functions
        diff: Function-specific diff
        
    Returns:
        ModifiedFunction object
    """
    # Use values from func_info if not explicitly provided
    if original_start is None and 'start_line' in func_info and change_type != FunctionChangeType.ADDED:
        original_start = func_info['start_line']
        
    if original_end is None and 'end_line' in func_info and change_type != FunctionChangeType.ADDED:
        original_end = func_info['end_line']
        
    if new_start is None and 'start_line' in func_info and change_type != FunctionChangeType.REMOVED:
        new_start = func_info['start_line']
        
    if new_end is None and 'end_line' in func_info and change_type != FunctionChangeType.REMOVED:
        new_end = func_info['end_line']
    
    # Calculate number of changes if not determined by a diff
    changes = 0
    if diff:
        changes = _count_changes(diff)
    elif change_type == FunctionChangeType.ADDED and new_start and new_end:
        changes = new_end - new_start + 1
    elif change_type == FunctionChangeType.REMOVED and original_start and original_end:
        changes = original_end - original_start + 1
    
    return ModifiedFunction(
        name=func_info['name'],
        file=file_path,
        type=func_info['node_type'],
        change_type=change_type,
        original_start=original_start,
        original_end=original_end,
        new_start=new_start,
        new_end=new_end,
        changes=changes,
        diff=diff,
        original_name=original_name,
        original_content=original_content,
        new_content=new_content
    )


def create_modified_functions(
    original_content: Optional[str],
    new_content: Optional[str],
    language: str,
    file_path: str,
    patch: Optional[str] = None,
    file_status: Optional[str] = None,
) -> List[ModifiedFunction]:
    """
    Identify functions that were modified between two versions of a file.
    
    Args:
        original_content: Content of the original file
        new_content: Content of the new file
        language: Programming language
        file_path: Path to the file
        patch: Optional patch from GitHub API (starts with @@)
        file_status: Status of the file
        
    Returns:
        List of ModifiedFunction objects
    """
    # Handle special cases for new or deleted files directly with the flags
    if file_status == "added":
        # New file - all functions are added
        new_functions = parse_functions(new_content, language)
        result = []
        for func in new_functions:
            # Extract the function content
            func_content = extract_function_content(new_content, func['start_line'], func['end_line'])
            # Create a diff for added function (all lines prefixed with +)
            func_diff = '\n'.join([f"+{line}" for line in func_content.splitlines()])
            
            # Create the ModifiedFunction using the helper
            modified_func = _create_modified_function(
                func_info=func,
                file_path=file_path,
                change_type=FunctionChangeType.ADDED,
                new_content=func_content,
                diff=func_diff
            )
            result.append(modified_func)
        return result
    
    if file_status == "removed":
        # Deleted file - all functions are deleted
        orig_functions = parse_functions(original_content, language)
        result = []
        for func in orig_functions:
            # Extract the function content
            func_content = extract_function_content(original_content, func['start_line'], func['end_line'])
            # Create a diff for deleted function (all lines prefixed with -)
            func_diff = '\n'.join([f"-{line}" for line in func_content.splitlines()])
            
            # Create the ModifiedFunction using the helper
            modified_func = _create_modified_function(
                func_info=func,
                file_path=file_path,
                change_type=FunctionChangeType.REMOVED,
                original_content=func_content,
                diff=func_diff
            )
            result.append(modified_func)
        return result
    
    # If we have the GitHub API patch, parse it directly
    if patch and patch.startswith('@@'):
        file_diff = parse_github_patch(patch, file_path)
        if file_diff:
            # Analyze the file diff
            return analyze_file_diff(file_diff, original_content, new_content, language, file_path)
    
    # If we don't have a patch but we have both contents, generate a diff
    elif original_content and new_content:
        # Generate a GitHub API style patch
        diff_lines = list(difflib.unified_diff(
            original_content.splitlines(),
            new_content.splitlines(),
            # No fromfile/tofile - we don't need these headers
            n=3,  # Context lines
            lineterm=''
        ))
        
        # Skip the first two lines (--- and +++ headers)
        if len(diff_lines) > 2:
            generated_patch = '\n'.join(diff_lines[2:])
            
            # Parse with our GitHub patch parser
            file_diff = parse_github_patch(generated_patch, file_path)
            if file_diff:
                return analyze_file_diff(file_diff, original_content, new_content, language, file_path)
    
    # If we get here, we couldn't analyze the changes
    logger.warning(f"Could not analyze changes for {file_path}")
    return []


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
            
            # Extract function content
            new_func_content = extract_function_content(new_content, func['start_line'], func['end_line'])
            
            if original_func:
                # Modified function
                original_func_content = extract_function_content(original_content, original_func['start_line'], original_func['end_line'])
                func_diff = extract_function_diff(file_diff, func_start, func_end)
                
                # Create ModifiedFunction using the helper
                modified_func = _create_modified_function(
                    func_info=func,
                    file_path=file_path,
                    change_type=FunctionChangeType.MODIFIED,
                    original_content=original_func_content,
                    new_content=new_func_content,
                    original_start=original_func['start_line'],
                    original_end=original_func['end_line'],
                    diff=func_diff
                )
                modified_functions.append(modified_func)
            else:
                # New function (could also be a renamed function, but we'll detect that later)
                # Create ModifiedFunction using the helper
                modified_func = _create_modified_function(
                    func_info=func,
                    file_path=file_path,
                    change_type=FunctionChangeType.ADDED,
                    new_content=new_func_content,
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
            # This function was deleted
            original_func_content = extract_function_content(original_content, orig_func['start_line'], orig_func['end_line'])
            
            # Create a diff for deleted function (all lines prefixed with -)
            func_diff = '\n'.join([f"-{line}" for line in original_func_content.splitlines()])
            
            # Create ModifiedFunction using the helper
            modified_func = _create_modified_function(
                func_info=orig_func,
                file_path=file_path,
                change_type=FunctionChangeType.REMOVED,
                original_content=original_func_content,
                diff=func_diff
            )
            modified_functions.append(modified_func)
    
    return modified_functions


def detect_renamed_functions(modified_functions: List[ModifiedFunction]) -> None:
    """
    Identify renamed functions by comparing added and deleted functions.
    Modifies the provided list in-place to update change types.
    
    Args:
        modified_functions: List of ModifiedFunction objects
    """
    # Collect added and deleted functions
    added_functions = [f for f in modified_functions if f.change_type == FunctionChangeType.ADDED]
    deleted_functions = [f for f in modified_functions if f.change_type == FunctionChangeType.REMOVED]
    
    # Skip if either list is empty
    if not added_functions or not deleted_functions:
        return
    
    # Track which functions have been processed
    processed_added = set()
    processed_deleted = set()
    
    # Store potential matches with their similarity scores
    potential_matches = []
    
    # Find potential renamed pairs
    for added_idx, added_func in enumerate(added_functions):
        for deleted_idx, deleted_func in enumerate(deleted_functions):
            # Skip already processed functions
            if added_idx in processed_added or deleted_idx in processed_deleted:
                continue
            
            # Calculate similarity between the function content
            # Only compare actual content, not diffs
            if added_func.new_content and deleted_func.original_content:
                similarity = calculate_function_similarity(added_func.new_content, deleted_func.original_content)
            else:
                # Skip if we don't have the content to compare
                logger.warning(f"Skipping similarity check for {added_func.name} and {deleted_func.name} - missing content")
                similarity = 0.0
            
            # If similarity is above threshold, consider it a potential match
            if similarity > 0.6:  # Configurable threshold
                potential_matches.append({
                    'added_idx': added_idx,
                    'deleted_idx': deleted_idx,
                    'added_func': added_func,
                    'deleted_func': deleted_func,
                    'similarity': similarity
                })
    
    # Sort matches by similarity score (highest first)
    potential_matches.sort(key=lambda x: x['similarity'], reverse=True)
    
    # Assign renames starting with the highest similarity matches
    for match in potential_matches:
        added_idx = match['added_idx']
        deleted_idx = match['deleted_idx']
        
        # Skip if either function has already been processed
        if added_idx in processed_added or deleted_idx in processed_deleted:
            continue
        
        added_func = match['added_func']
        deleted_func = match['deleted_func']
        
        # Update the added function to be a renamed function
        for i, mf in enumerate(modified_functions):
            if mf is added_func:
                # Favor same-file renames with a slight boost to similarity
                same_file_boost = 0.1 if added_func.file == deleted_func.file else 0
                actual_similarity = match['similarity'] + same_file_boost
                
                # Only consider it a rename if the similarity is high enough
                if actual_similarity >= 0.7:  # Configurable threshold
                    logger.info(f"Rename detected: {deleted_func.name} -> {added_func.name} " 
                              f"(similarity: {actual_similarity:.2f})")
                    
                    # Create renamed function using helper
                    modified_functions[i] = _create_modified_function(
                        func_info={'name': added_func.name, 'node_type': added_func.type},
                        file_path=added_func.file,
                        change_type=FunctionChangeType.RENAMED,
                        original_name=deleted_func.name,
                        original_start=deleted_func.original_start,
                        original_end=deleted_func.original_end,
                        new_start=added_func.new_start,
                        new_end=added_func.new_end,
                        original_content=deleted_func.original_content,
                        new_content=added_func.new_content,
                        diff=added_func.diff
                    )
                    processed_added.add(added_idx)
                    processed_deleted.add(deleted_idx)
                    
                    # Remove the deleted function as it's now accounted for
                    modified_functions.remove(deleted_func)
                break


def calculate_function_similarity(content1: Optional[str], content2: Optional[str]) -> float:
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
    
    try:
        # Split into lines
        lines1 = content1.splitlines()
        lines2 = content2.splitlines()
        
        # Join the lines
        cleaned1 = '\n'.join(lines1)
        cleaned2 = '\n'.join(lines2)
        
        # Normalize whitespace
        content1_norm = ' '.join(cleaned1.split())
        content2_norm = ' '.join(cleaned2.split())
        
        # If after cleanup we have empty strings, return 0
        if not content1_norm or not content2_norm:
            return 0.0
        
        # Use difflib to calculate sequence similarity
        sequence_similarity = difflib.SequenceMatcher(None, content1_norm, content2_norm).ratio()
        
        # Calculate token-level similarity (split by whitespace)
        tokens1 = set(content1_norm.split())
        tokens2 = set(content2_norm.split())
        
        # Jaccard similarity for tokens
        common_tokens = tokens1.intersection(tokens2)
        all_tokens = tokens1.union(tokens2)
        
        token_similarity = len(common_tokens) / len(all_tokens) if all_tokens else 0.0
        
        # Combined similarity (weighted average)
        return 0.7 * sequence_similarity + 0.3 * token_similarity
    except Exception as e:
        # Log the error but don't crash
        logger.warning(f"Error calculating function similarity: {str(e)}")
        return 0.0


def _find_matching_function(func: Dict, candidates: List[Dict]) -> Optional[Dict]:
    """
    Find matching function in a list of candidate functions.
    
    Args:
        func: Function to find a match for
        candidates: List of candidate functions
        
    Returns:
        Matching function dict or None if no match found
    """
    # Use next() with a default of None to find exact name match
    return next((candidate for candidate in candidates if candidate['name'] == func['name']), None)


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
    
    # Detect modified functions - our main analysis path for changed files
    modified_functions = detect_modified_functions(
        original_content, new_content, file_diff, language, file_path
    )
    
    # After we've detected all the modified functions, try to identify renamed functions
    detect_renamed_functions(modified_functions)
    
    return modified_functions