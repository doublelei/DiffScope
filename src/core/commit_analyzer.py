"""
Commit analysis integration module.

This module connects the GitHub API integration with function-level
change detection to provide a complete analysis of commits.
"""

from typing import List, Dict, Optional, Any
import logging

from ..utils.github_api import (
    parse_github_url,
    get_commit_data,
    get_commit_files,
    get_file_content_before_after
)
from ..core.git_analyzer import (
    analyze_github_commit,
    detect_file_language
)
from ..core.function_detector import (
    create_modified_functions,
    detect_renamed_functions
)
from ..models import CommitAnalysisResult, ModifiedFile, ModifiedFunction

# Set up logging
logger = logging.getLogger(__name__)


def analyze_commit_with_functions(commit_url: str) -> CommitAnalysisResult:
    """
    Analyze a commit with function-level change detection.
    
    Args:
        commit_url: URL to a GitHub commit
        
    Returns:
        CommitAnalysisResult with both file and function-level changes
    """
    # First get the basic file-level commit analysis
    commit_result = analyze_github_commit(commit_url)
    
    # Extract owner, repo, commit SHA for content retrieval
    owner, repo, commit_sha = parse_github_url(commit_url)

    # Track all modified functions across files
    all_modified_functions = []
    
    # Process each modified file to detect function changes
    for modified_file in commit_result.modified_files:
        # Skip binary files and non-supported languages
        if not should_analyze_file(modified_file):
            logger.info(f"Skipping file: {modified_file.filename} (binary or unsupported language)")
            continue
        
        # Get file content before and after changes
        before_content, after_content = get_file_content_before_after(
            owner, repo, commit_sha, modified_file.filename
        )
        
        # Skip if we couldn't get content
        if modified_file.status != 'removed' and not after_content:
            logger.warning(f"Couldn't retrieve content for: {modified_file.filename}")
            continue
        
        if modified_file.status != 'added' and not before_content:
            logger.warning(f"Couldn't retrieve original content for: {modified_file.filename}")
            continue
        
        # Detect function changes
        try:
            # Handle special cases based on file status
            if modified_file.status == 'added':
                # New file - all functions are new
                file_functions = create_modified_functions(
                    None, after_content, 
                    modified_file.language.lower(), 
                    modified_file.filename,
                    modified_file.patch
                )
            elif modified_file.status == 'removed':
                # Deleted file - all functions are deleted
                file_functions = create_modified_functions(
                    before_content, None, 
                    modified_file.language.lower(), 
                    modified_file.filename,
                    modified_file.patch
                )
            else:
                # Modified file - need to analyze changes
                file_functions = create_modified_functions(
                    before_content, after_content, 
                    modified_file.language.lower(), 
                    modified_file.filename,
                    modified_file.patch
                )
                
            # Add file functions to the overall list
            all_modified_functions.extend(file_functions)
            
        except Exception as e:
            logger.error(f"Error analyzing functions in {modified_file.filename}: {str(e)}")
            continue
    
    # Detect renamed functions across files
    detect_renamed_functions(all_modified_functions)
    
    # Update the commit result with function changes
    commit_result.modified_functions = all_modified_functions
    
    return commit_result


def should_analyze_file(modified_file: ModifiedFile) -> bool:
    """
    Determine if a file should be analyzed for function changes.
    
    Args:
        modified_file: The file to check
        
    Returns:
        True if the file should be analyzed, False otherwise
    """
    # Skip binary files - GitHub API doesn't provide patches for binary files
    # and when it does provide a patch for text files, it starts with @@ for hunk headers
    if not modified_file.patch:
        logger.debug(f"Skipping file without patch: {modified_file.filename}")
        return False
        
    # GitHub API patches always start with @@ for hunk headers for text files
    if not modified_file.patch.startswith('@@'):
        logger.debug(f"Skipping binary file (patch doesn't start with @@): {modified_file.filename}")
        return False
        
    # Check if we support this language
    if not modified_file.language:
        logger.debug(f"Skipping file with unknown language: {modified_file.filename}")
        return False
        
    # List of currently supported languages for function detection
    supported_languages = ['python', 'javascript', 'typescript', 'java', 'c', 'cpp', 'go']
    
    if modified_file.language.lower() not in supported_languages:
        logger.debug(f"Skipping file with unsupported language {modified_file.language}: {modified_file.filename}")
        return False
        
    return True 