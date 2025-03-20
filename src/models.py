from typing import Optional, List
from pydantic import BaseModel


class ModifiedFile(BaseModel):
    """Information about a modified file"""
    filename: str
    status: Optional[str] = None  # "added", "modified", "deleted"
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: Optional[str] = None
    language: Optional[str] = None


class ModifiedFunction(BaseModel):
    """Information about a modified function"""
    function_name: str
    file_path: str
    language: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    before_content: Optional[str] = None
    after_content: Optional[str] = None
    change_type: Optional[str] = None  # Type of change (added, modified, removed)
    diff: Optional[str] = None  # Function diff for display


class CommitAnalysisResult(BaseModel):
    """Results of analyzing a commit"""
    commit_sha: str
    commit_message: Optional[str] = None
    commit_author: Optional[str] = None
    commit_date: Optional[str] = None
    repository_url: Optional[str] = None
    modified_files: List[ModifiedFile] = []
    modified_functions: List[ModifiedFunction] = []
