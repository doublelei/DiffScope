from typing import Dict, List, Optional, Tuple, Any
import os

from ..utils.github_api import (
    parse_github_url,
    get_commit_data,
    get_commit_files,
    get_file_content_before_after
)
from ..models import ModifiedFile, ModifiedFunction, CommitAnalysisResult

def analyze_github_commit(commit_url: str) -> CommitAnalysisResult:
    """
    Analyze a GitHub commit and extract file-level changes.
    
    Args:
        commit_url: URL to a GitHub commit
        
    Returns:
        CommitAnalysisResult with file-level changes
    """
    # Parse GitHub URL to get owner, repo, and commit SHA
    owner, repo, commit_sha = parse_github_url(commit_url)
    
    # Get commit data
    commit_data = get_commit_data(owner, repo, commit_sha)
    
    # Extract basic commit information
    commit_message = commit_data.get('commit', {}).get('message', '')
    commit_author = commit_data.get('commit', {}).get('author', {}).get('name', '')
    commit_date = commit_data.get('commit', {}).get('author', {}).get('date', '')
    
    # Get files changed in the commit
    files_data = commit_data.get('files', [])
    
    # Convert GitHub API file data to ModifiedFile objects
    modified_files = convert_github_files_to_modified_files(files_data)
    
    # Create commit analysis result
    result = CommitAnalysisResult(
        commit_sha=commit_sha,
        commit_message=commit_message,
        commit_author=commit_author,
        commit_date=commit_date,
        repository_url=f"https://github.com/{owner}/{repo}",
        modified_files=modified_files,
        modified_functions=[]  # Will be populated in Phase 2
    )
    
    return result

def convert_github_files_to_modified_files(github_files: List[Dict[str, Any]]) -> List[ModifiedFile]:
    """
    Convert GitHub API file data to ModifiedFile objects.
    
    Args:
        github_files: List of file data from GitHub API
        
    Returns:
        List of ModifiedFile objects
    """
    modified_files = []
    
    for file_data in github_files:
        filename = file_data.get('filename', '')
        status = file_data.get('status', '')
        additions = file_data.get('additions', 0)
        deletions = file_data.get('deletions', 0)
        changes = file_data.get('changes', 0)
        patch = file_data.get('patch', None)
        
        # Detect file language
        language = detect_file_language(filename)
        
        # Create ModifiedFile object
        modified_file = ModifiedFile(
            filename=filename,
            status=status,
            additions=additions,
            deletions=deletions,
            changes=changes,
            patch=patch,
            language=language
        )
        
        modified_files.append(modified_file)
    
    return modified_files

def detect_file_language(file_path: str) -> Optional[str]:
    """
    Detect programming language of a file based on extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Language name or None if unknown
    """
    extension_map = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.jsx': 'JavaScript',
        '.ts': 'TypeScript',
        '.tsx': 'TypeScript',
        '.java': 'Java',
        '.c': 'C',
        '.cpp': 'C++',
        '.h': 'C',
        '.hpp': 'C++',
        '.cs': 'C#',
        '.go': 'Go',
        '.rb': 'Ruby',
        '.php': 'PHP',
        '.swift': 'Swift',
        '.kt': 'Kotlin',
        '.rs': 'Rust'
    }
    
    _, ext = os.path.splitext(file_path)
    return extension_map.get(ext.lower())