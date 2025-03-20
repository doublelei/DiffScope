import re
import os
from typing import Dict, List, Tuple, Optional, Union, Any
import base64
from github import Github, Auth
from github.GithubException import GithubException
from github.Commit import Commit
from github.ContentFile import ContentFile
from github.Repository import Repository

# Initialize GitHub client with authentication token if available
github_token = os.environ.get('GITHUB_TOKEN')
if github_token:
    # Use the newer authentication method to avoid deprecation warning
    auth = Auth.Token(github_token)
    github_client = Github(auth=auth)
    print("Initialized GitHub client with authentication token")
else:
    github_client = Github()
    print("WARNING: No GITHUB_TOKEN found. Using unauthenticated GitHub client (subject to rate limits)")

def parse_github_url(github_url: str) -> Tuple[str, str, str]:
    """
    Parse a GitHub URL to extract owner, repo, and commit SHA.
    
    Args:
        github_url: URL to a GitHub commit (e.g., https://github.com/owner/repo/commit/sha)
        
    Returns:
        Tuple of (owner, repo_name, commit_sha)
    """
    # Pattern for GitHub commit URLs
    pattern = r"https?://github\.com/([^/]+)/([^/]+)/commit/([^/]+)"
    match = re.match(pattern, github_url)
    
    if not match:
        raise ValueError(f"Invalid GitHub commit URL: {github_url}")
    
    owner, repo, commit_sha = match.groups()
    return owner, repo, commit_sha

def get_repo(owner: str, repo: str) -> Repository:
    """
    Get a GitHub repository object.
    
    Args:
        owner: Repository owner
        repo: Repository name
        
    Returns:
        GitHub Repository object
    """
    try:
        return github_client.get_repo(f"{owner}/{repo}")
    except GithubException as e:
        raise ValueError(f"Failed to get repository {owner}/{repo}: {e}")

def get_commit(owner: str, repo: str, commit_sha: str) -> Commit:
    """
    Get a GitHub commit object.
    
    Args:
        owner: Repository owner
        repo: Repository name
        commit_sha: Commit SHA
        
    Returns:
        GitHub Commit object
    """
    try:
        repository = get_repo(owner, repo)
        return repository.get_commit(commit_sha)
    except GithubException as e:
        raise ValueError(f"Failed to get commit {commit_sha}: {e}")

def get_commit_data(owner: str, repo: str, commit_sha: str) -> Dict[str, Any]:
    """
    Get commit data from GitHub API.
    
    Args:
        owner: Repository owner
        repo: Repository name
        commit_sha: Commit SHA
        
    Returns:
        Dictionary containing commit data
    """
    commit = get_commit(owner, repo, commit_sha)
    
    # Convert commit object to dictionary with essential information
    files_data = []
    for file in commit.files:
        file_dict = {
            'filename': file.filename,
            'status': file.status,
            'additions': file.additions,
            'deletions': file.deletions,
            'changes': file.changes,
            'patch': file.patch if hasattr(file, 'patch') else None
        }
        files_data.append(file_dict)
    
    # Construct unified commit data
    commit_data = {
        'sha': commit.sha,
        'commit': {
            'message': commit.commit.message,
            'author': {
                'name': commit.commit.author.name,
                'date': commit.commit.author.date.isoformat()
            },
            'committer': {
                'name': commit.commit.committer.name,
                'date': commit.commit.committer.date.isoformat()
            }
        },
        'files': files_data,
        'stats': {
            'additions': commit.stats.additions,
            'deletions': commit.stats.deletions,
            'total': commit.stats.total
        },
        'parents': [{'sha': parent.sha} for parent in commit.parents]
    }
    
    return commit_data

def get_commit_files(owner: str, repo: str, commit_sha: str) -> List[Dict[str, Any]]:
    """
    Get list of files changed in a commit from GitHub API.
    
    Args:
        owner: Repository owner
        repo: Repository name
        commit_sha: Commit SHA
        
    Returns:
        List of file data dictionaries
    """
    commit = get_commit(owner, repo, commit_sha)
    
    files_data = []
    for file in commit.files:
        file_dict = {
            'filename': file.filename,
            'status': file.status,
            'additions': file.additions,
            'deletions': file.deletions,
            'changes': file.changes,
            'patch': file.patch if hasattr(file, 'patch') else None
        }
        files_data.append(file_dict)
    
    return files_data

def get_file_content(owner: str, repo: str, file_path: str, ref: str) -> Optional[str]:
    """
    Get content of a file at a specific commit from GitHub API.
    
    Args:
        owner: Repository owner
        repo: Repository name
        file_path: Path to file in the repository
        ref: Commit SHA or branch name
        
    Returns:
        Content of the file as string, or None if file doesn't exist
    """
    try:
        repository = get_repo(owner, repo)
        content_file = repository.get_contents(file_path, ref=ref)
        
        # Handle case where content_file might be a list (for directories)
        if isinstance(content_file, list):
            return None
        
        return content_file.decoded_content.decode('utf-8')
    except GithubException as e:
        if e.status == 404:
            return None
        raise ValueError(f"Failed to get file content for {file_path} at {ref}: {e}")

def get_file_content_before_after(owner: str, repo: str, file_path: str, commit_sha: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Get the content of a file before and after a commit.
    
    Args:
        owner: Repository owner
        repo: Repository name
        file_path: Path to file in the repository
        commit_sha: SHA of the commit
        
    Returns:
        Tuple of (content_before, content_after)
    """
    commit = get_commit(owner, repo, commit_sha)
    
    # Get parent commit SHA
    parent_sha = commit.parents[0].sha if commit.parents else None
    
    # Get content after the commit
    after_content = get_file_content(owner, repo, file_path, commit_sha)
    
    # Get content before the commit (if parent exists)
    before_content = None
    if parent_sha:
        before_content = get_file_content(owner, repo, file_path, parent_sha)
    
    return before_content, after_content 