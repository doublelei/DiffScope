#!/usr/bin/env python
"""
Function-level diff analysis demo script.

This script demonstrates how to use DiffScope to analyze function-level changes
in a diff between two versions of a file.
"""

import sys
import os
import argparse
from pathlib import Path

# Add the parent directory to the path to import DiffScope
sys.path.append(str(Path(__file__).parent.parent))

from src.utils.diff_utils import parse_unified_diff
from src.core.function_detector import analyze_file_diff
from src.parsers.function_parser import parse_functions
from src.models import FunctionChangeType


def main():
    """Run the function-level diff analysis demo."""
    parser = argparse.ArgumentParser(description='Analyze function-level changes in a diff.')
    parser.add_argument('--diff-file', type=str, help='Path to a diff file')
    parser.add_argument('--old-file', type=str, help='Path to the original file')
    parser.add_argument('--new-file', type=str, help='Path to the new file')
    parser.add_argument('--language', type=str, default=None, help='Language of the code')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.diff_file or not os.path.exists(args.diff_file):
        if not (args.old_file and args.new_file):
            parser.error("Either --diff-file or both --old-file and --new-file must be provided")
            return
    
    if args.diff_file and os.path.exists(args.diff_file):
        # Read the diff file
        with open(args.diff_file, 'r') as f:
            diff_content = f.read()
        
        # Parse the diff
        file_diffs = parse_unified_diff(diff_content)
        if not file_diffs:
            print("No file diffs found in the diff file")
            return
        
        # Use the first file diff for simplicity
        file_diff = file_diffs[0]
        
        # Extract file paths
        old_file_path = args.old_file or file_diff.old_file
        new_file_path = args.new_file or file_diff.new_file
        
        # Handle special cases
        if file_diff.is_new_file:
            old_content = ""
            with open(new_file_path, 'r') as f:
                new_content = f.read()
        elif file_diff.is_deleted_file:
            with open(old_file_path, 'r') as f:
                old_content = f.read()
            new_content = ""
        else:
            # Read the original and new files
            try:
                with open(old_file_path, 'r') as f:
                    old_content = f.read()
            except FileNotFoundError:
                print(f"Error: Original file '{old_file_path}' not found")
                return
            
            try:
                with open(new_file_path, 'r') as f:
                    new_content = f.read()
            except FileNotFoundError:
                print(f"Error: New file '{new_file_path}' not found")
                return
    else:
        # Generate diff from the two files
        try:
            with open(args.old_file, 'r') as f:
                old_content = f.read()
        except FileNotFoundError:
            print(f"Error: Original file '{args.old_file}' not found")
            return
        
        try:
            with open(args.new_file, 'r') as f:
                new_content = f.read()
        except FileNotFoundError:
            print(f"Error: New file '{args.new_file}' not found")
            return
        
        # Generate the diff
        import difflib
        diff_lines = difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=args.old_file,
            tofile=args.new_file
        )
        diff_content = ''.join(diff_lines)
        
        # Parse the generated diff
        file_diffs = parse_unified_diff(diff_content)
        if not file_diffs:
            print("No changes detected between the files")
            return
        
        file_diff = file_diffs[0]
        old_file_path = args.old_file
        new_file_path = args.new_file
    
    # Determine language if not specified
    language = args.language
    if not language:
        # Try to determine from file extension
        ext = os.path.splitext(new_file_path or old_file_path)[1].lower()
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.go': 'go',
            '.rb': 'ruby',
            '.rs': 'rust',
            '.php': 'php',
        }
        language = language_map.get(ext)
        
        if not language:
            print(f"Warning: Unable to determine language from file extension '{ext}'")
            print("Defaulting to Python. Use --language to specify the language.")
            language = 'python'
    
    # Analyze the diff
    modified_functions = analyze_file_diff(
        file_diff,
        old_content,
        new_content,
        language,
        new_file_path or old_file_path
    )
    
    # Display results
    if file_diff.is_new_file:
        print(f"New file: {new_file_path}")
    elif file_diff.is_deleted_file:
        print(f"Removed file: {old_file_path}")
    elif file_diff.is_rename:
        print(f"Renamed file: {old_file_path} -> {new_file_path}")
    else:
        print(f"Modified file: {new_file_path}")
    
    print(f"Language: {language}")
    print(f"Found {len(modified_functions)} modified functions:")
    
    for i, func in enumerate(modified_functions, 1):
        print(f"\n{i}. {func.name} ({func.change_type.value}):")
        
        if func.change_type == FunctionChangeType.RENAMED:
            print(f"   Renamed from: {func.original_name}")
        
        if func.original_start:
            print(f"   Original location: lines {func.original_start}-{func.original_end}")
        
        if func.new_start:
            print(f"   New location: lines {func.new_start}-{func.new_end}")
        
        print(f"   Changed lines: {func.changes}")
        
        if func.diff:
            print("\n   --- Diff ---")
            for line in func.diff.splitlines()[:10]:  # Show first 10 lines
                print(f"   {line}")
            if len(func.diff.splitlines()) > 10:
                print(f"   ... ({len(func.diff.splitlines()) - 10} more lines)")


if __name__ == "__main__":
    main() 