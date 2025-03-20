"""
Data models for DiffScope.

This module defines the data structures used throughout DiffScope
for representing files, functions, and changes.
"""

from typing import List, Dict, Optional, Any
from enum import Enum
from dataclasses import dataclass


class FileChangeType(str, Enum):
    """Type of change to a file."""
    ADDED = "added"
    MODIFIED = "modified"
    REMOVED = "removed"
    RENAMED = "renamed"


class FunctionChangeType(str, Enum):
    """Type of change to a function."""
    ADDED = "added"
    DELETED = "deleted"
    RENAMED = "renamed"
    SIGNATURE_CHANGED = "signature_changed"
    BODY_CHANGED = "body_changed"
    DOCSTRING_CHANGED = "docstring_changed"


@dataclass
class ModifiedFile:
    """Information about a modified file in a commit."""
    filename: str
    status: str  # 'added', 'modified', 'removed', 'renamed'
    additions: int
    deletions: int
    changes: int
    language: Optional[str] = None
    patch: Optional[str] = None
    previous_filename: Optional[str] = None


@dataclass
class ModifiedFunction:
    """Information about a modified function in a commit."""
    name: str
    file: str
    type: str  # 'function', 'method', etc.
    change_type: FunctionChangeType
    original_start: Optional[int] = None
    original_end: Optional[int] = None
    new_start: Optional[int] = None
    new_end: Optional[int] = None
    changes: int = 0
    diff: Optional[str] = None
    original_name: Optional[str] = None  # For renamed functions


@dataclass
class CommitAnalysisResult:
    """Result of analyzing a commit."""
    commit_sha: str
    repository_url: str
    commit_author: Optional[str] = None
    commit_date: Optional[str] = None
    commit_message: Optional[str] = None
    modified_files: List[ModifiedFile] = None
    modified_functions: List[ModifiedFunction] = None
    
    def __post_init__(self):
        if self.modified_files is None:
            self.modified_files = []
        if self.modified_functions is None:
            self.modified_functions = []
