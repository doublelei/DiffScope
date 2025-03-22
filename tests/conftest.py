"""
Test configuration for DiffScope.

This file adds custom command-line options to pytest for testing
file processing functionality against arbitrary inputs.
"""

import pytest
import os
import json

def pytest_configure(config):
    """Configure pytest."""
    # Register custom markers
    config.addinivalue_line(
        "markers", "live_api: mark test as using live GitHub API (may be subject to rate limits)"
    )

def pytest_addoption(parser):
    """Add custom command-line options to pytest."""
    parser.addoption(
        "--run-live-api",
        action="store_true",
        default=False,
        help="Run tests that hit the live GitHub API",
    )
    parser.addoption(
        "--input",
        action="store",
        default=None,
        help="Path to input file for function parser testing"
    )
    parser.addoption(
        "--expected-output",
        action="store",
        default=None,
        help="Path to expected JSON output file (optional)"
    )
    parser.addoption(
        "--language",
        action="store",
        default=None,
        help="Language of the input file (e.g., python, javascript)"
    )
    parser.addoption(
        "--line",
        action="store",
        default=None,
        help="Line number to find function at"
    )
    parser.addoption(
        "--output-file",
        action="store",
        default=None,
        help="Path to save parser output as JSON"
    )
    # Add commit analysis options
    parser.addoption(
        "--commit_url", 
        action="store", 
        default=None,
        help="Specify a GitHub commit URL to analyze"
    )
    parser.addoption(
        "--commit_file", 
        action="store", 
        default=None,
        help="Specify a file containing GitHub commit URLs to analyze (txt or json format)"
    )
    parser.addoption(
        "--save-results",
        action="store",
        default=None,
        help="Path to save commit analysis results. Can be: 1) a directory (creates subdirectories for results with/without "
             "function changes), 2) a .json file (creates separate files for results with/without function changes), or "
             "3) a .jsonl file (efficient streaming format for large datasets). Also saves a list of URLs without detected "
             "function changes to a separate file for future testing."
    )

def pytest_collection_modifyitems(config, items):
    """Modify test collection based on command-line options."""
    if config.getoption("--run-live-api"):
        # Check for GitHub token when running live API tests
        if not os.environ.get('GITHUB_TOKEN'):
            print("\nWARNING: Running live API tests without GITHUB_TOKEN environment variable.")
            print("You may encounter rate limiting issues with the GitHub API.")
            print("Set the GITHUB_TOKEN environment variable with a valid GitHub personal access token.")
            print("For example: export GITHUB_TOKEN=your_token_here (bash) or $env:GITHUB_TOKEN=\"your_token_here\" (PowerShell)\n")
        # --run-live-api given in cli: do not skip live_api tests
        return
    
    skip_live_api = pytest.mark.skip(reason="need --run-live-api option to run")
    for item in items:
        if "live_api" in item.keywords:
            item.add_marker(skip_live_api)

@pytest.fixture
def print_commit_result():
    """
    Fixture to print detailed information about a CommitAnalysisResult.
    
    Usage in tests:
        def test_something(print_commit_result):
            result = analyze_commit(url)
            print_commit_result(result)
    """
    def _print_commit_result(result, commit_url=None):
        print("\n" + "="*80)
        print(f"COMMIT ANALYSIS RESULT")
        print("="*80)
        print(f"Commit SHA:     {result.commit_sha}")
        print(f"Repository:     {result.repository_url}")
        if commit_url:
            print(f"Complete URL:   {commit_url}")
        print(f"Author:         {result.commit_author}")
        print(f"Date:           {result.commit_date}")
        print(f"Commit Message: {result.commit_message[:60]}..." if len(result.commit_message or '') > 60 
              else result.commit_message)
        
        print("\nMODIFIED FILES:")
        print("-"*80)
        for i, file in enumerate(result.modified_files, 1):
            print(f"{i}. {file.filename}")
            print(f"   Status: {file.status}, Language: {file.language or 'Unknown'}")
            print(f"   Changes: +{file.additions} -{file.deletions} ({file.changes} total)")
            if hasattr(file, 'patch') and file.patch:
                patch_preview = file.patch[:100] + "..." if len(file.patch) > 100 else file.patch
                print(f"   Patch Preview: {patch_preview}")
            print()
        
        if result.modified_functions:
            print("\nMODIFIED FUNCTIONS:")
            print("-"*80)
            for i, func in enumerate(result.modified_functions, 1):
                print(f"{i}. {func.name} in {func.file}")
                print(f"   Type: {func.type}, Change Type: {func.change_type.value}")
                
                # Print line position information
                if func.original_start is not None and func.original_end is not None:
                    print(f"   Original Position: Lines {func.original_start}-{func.original_end}")
                if func.new_start is not None and func.new_end is not None:
                    print(f"   New Position: Lines {func.new_start}-{func.new_end}")
                
                # Print original name for renamed functions
                if func.change_type.value == "renamed" and hasattr(func, 'original_name') and func.original_name:
                    print(f"   Original Name: {func.original_name}")
                
                print(f"   Changes: {func.changes}")
                
                # Print diff preview if available
                if func.diff:
                    diff_lines = func.diff.splitlines()
                    # Show at most 10 lines of the diff
                    diff_preview = "\n      ".join(diff_lines[:10])
                    if len(diff_lines) > 10:
                        diff_preview += "\n      ..."
                    print(f"   Diff Preview: \n      {diff_preview}")
                
                print()
                
        print("="*80 + "\n")
        
    return _print_commit_result

@pytest.fixture
def input_file(request):
    """Get the input file path from command line."""
    return request.config.getoption("--input")

@pytest.fixture
def expected_output_file(request):
    """Get the expected output file path from command line."""
    return request.config.getoption("--expected-output")

@pytest.fixture
def language(request):
    """Get the language from command line."""
    return request.config.getoption("--language")

@pytest.fixture
def line_number(request):
    """Get the line number from command line."""
    line = request.config.getoption("--line")
    if line is not None:
        try:
            return int(line)
        except ValueError:
            pytest.fail(f"Invalid line number: {line}")
    return None

@pytest.fixture
def output_file(request):
    """Get the output file path from command line."""
    return request.config.getoption("--output-file")

@pytest.fixture
def input_content(input_file):
    """Load content from the input file."""
    if not input_file or not os.path.exists(input_file):
        pytest.skip(f"Input file not specified or does not exist: {input_file}")
    
    with open(input_file, "r", encoding="utf-8") as f:
        return f.read()

@pytest.fixture
def expected_output(expected_output_file):
    """Load expected output from JSON file."""
    if not expected_output_file:
        return None
        
    if not os.path.exists(expected_output_file):
        pytest.skip(f"Expected output file does not exist: {expected_output_file}")
    
    with open(expected_output_file, "r", encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture
def detect_language(input_file, language):
    """Auto-detect language if not specified."""
    if language:
        return language
        
    if input_file:
        ext = os.path.splitext(input_file)[1].lower()
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
            '.cs': 'csharp',
            # Add more mappings as needed
        }
        return language_map.get(ext)
    
    return None 

@pytest.fixture
def commit_url(request):
    """Get the commit URL from command line."""
    return request.config.getoption("--commit_url")

@pytest.fixture
def commit_file(request):
    """Get the commit file path from command line."""
    return request.config.getoption("--commit_file")

@pytest.fixture
def save_results_path(request):
    """Get the path to save commit analysis results."""
    return request.config.getoption("--save-results") 

@pytest.fixture
def save_failed_urls_path(request, save_results_path):
    """
    Get the path to save URLs of commits with no function changes.
    Automatically derived from save_results_path if not explicitly set.
    """
    if not save_results_path:
        return None
        
    # If save_results_path is a directory, use it with a default filename
    if os.path.isdir(save_results_path):
        return os.path.join(save_results_path, "failed_urls.txt")
    
    # If save_results_path is a file, derive the failed URLs filename from it
    base, ext = os.path.splitext(save_results_path)
    return f"{base}_failed_urls.txt"

def save_commit_analysis_result(result, output_path, commit_url=None, save_failed_urls=True):
    """
    Save a CommitAnalysisResult to a file.
    
    Args:
        result: The CommitAnalysisResult object
        output_path: Path to save the results. If it's a directory, a filename will be generated
                     based on the commit SHA and repository.
        commit_url: Optional complete commit URL for reference
        save_failed_urls: Whether to save URLs of commits with no function changes to a separate file
    
    Returns:
        The path to the saved file
    """
    import os
    import json
    import datetime
    
    # Determine if this is a "success" case (has modified functions) or not
    has_function_changes = bool(result.modified_functions)
    
    # Save URL to the failed URLs file if appropriate
    if save_failed_urls and commit_url and not has_function_changes:
        # Determine the path for the failed URLs file
        if os.path.isdir(output_path):
            failed_urls_file = os.path.join(output_path, "failed_urls.txt")
        else:
            base, ext = os.path.splitext(output_path)
            failed_urls_file = f"{base}_failed_urls.txt"
        
        # Append the URL to the file
        os.makedirs(os.path.dirname(os.path.abspath(failed_urls_file)), exist_ok=True)
        with open(failed_urls_file, 'a', encoding='utf-8') as f:
            f.write(f"{commit_url}\n")
        
        # Print a message about saving the failed URL
        print(f"\nAdded commit URL to failed URLs file: {failed_urls_file}")
    
    # Create serializable dictionary from result
    result_dict = {
        "commit_sha": result.commit_sha,
        "repository_url": result.repository_url,
        "commit_url": commit_url,
        "commit_author": result.commit_author,
        "commit_date": result.commit_date,
        "commit_message": result.commit_message,
        "timestamp": datetime.datetime.now().isoformat(),
        "has_function_changes": has_function_changes,
        "modified_files": [],
        "modified_functions": []
    }
    
    # Serialize modified files
    for file in result.modified_files:
        file_dict = {
            "filename": file.filename,
            "status": file.status,
            "additions": file.additions,
            "deletions": file.deletions,
            "changes": file.changes,
            "language": file.language
        }
        # Only include patch if it exists and isn't too large
        if hasattr(file, 'patch') and file.patch and len(file.patch) < 10000:
            file_dict["patch"] = file.patch
        if hasattr(file, 'previous_filename') and file.previous_filename:
            file_dict["previous_filename"] = file.previous_filename
            
        result_dict["modified_files"].append(file_dict)
    
    # Serialize modified functions
    for func in result.modified_functions:
        func_dict = {
            "name": func.name,
            "file": func.file,
            "type": func.type,
            "change_type": func.change_type.value,
            "changes": func.changes,
            "original_start": func.original_start,
            "original_end": func.original_end,
            "new_start": func.new_start,
            "new_end": func.new_end
        }
        
        # Include optional fields if they exist
        if hasattr(func, 'original_name') and func.original_name:
            func_dict["original_name"] = func.original_name
            
        # Only include diffs and content if they're not too large
        if func.diff and len(func.diff) < 10000:
            func_dict["diff"] = func.diff
        if func.original_content and len(func.original_content) < 10000:
            func_dict["original_content"] = func.original_content
        if func.new_content and len(func.new_content) < 10000:
            func_dict["new_content"] = func.new_content
            
        result_dict["modified_functions"].append(func_dict)
    
    # Determine output file path
    if os.path.isdir(output_path):
        # If it's a directory, create a filename based on commit SHA and repo
        repo_name = result.repository_url.split('/')[-1] if result.repository_url else "unknown"
        
        # Create subdirectories for success/failure cases
        status_dir = "with_functions" if has_function_changes else "no_functions"
        output_subdir = os.path.join(output_path, status_dir)
        os.makedirs(output_subdir, exist_ok=True)
        
        filename = f"{repo_name}_{result.commit_sha[:8]}.json"
        output_file = os.path.join(output_subdir, filename)
        
        # Write the result to the output file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, indent=2, ensure_ascii=False)
            
        print(f"\nCommit analysis results saved to: {output_file}")
    else:
        # If it's a file path, use it directly but append a suffix based on success/failure
        output_file = output_path
        base, ext = os.path.splitext(output_file)
        
        # Create separate files for success/failure cases
        if has_function_changes:
            output_file = f"{base}_with_functions{ext}"
        else:
            output_file = f"{base}_no_functions{ext}"
        
        # Determine file extension
        _, ext = os.path.splitext(output_file)
        
        # Check if output path ends with .jsonl (JSON Lines format)
        if ext.lower() == '.jsonl':
            # Make sure the directory exists
            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
            
            # Append the new result to the file in JSON Lines format (one JSON object per line)
            with open(output_file, 'a', encoding='utf-8') as f:
                # Add a newline if the file is not empty and doesn't end with a newline
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    with open(output_file, 'rb+') as f_check:
                        f_check.seek(-1, os.SEEK_END)
                        last_char = f_check.read(1)
                        if last_char != b'\n':
                            f.write('\n')
                
                # Write the new JSON object as a single line
                f.write(json.dumps(result_dict, ensure_ascii=False))
            
            # Count the number of lines to get an approximate count of results
            result_count = 0
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    for _ in f:
                        result_count += 1
            
            status_str = "with function changes" if has_function_changes else "without function changes"
            print(f"\nCommit analysis result ({status_str}) appended to: {output_file} (total results: {result_count})")
        else:
            # Make sure the directory exists
            os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
            
            # For standard JSON files, use a more efficient approach - append to a JSON array
            # Start with an empty array if the file doesn't exist or is empty
            file_exists = os.path.exists(output_file) and os.path.getsize(output_file) > 0
            
            if not file_exists:
                # Create a new file with a JSON array containing the first result
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump([result_dict], f, ensure_ascii=False)
                
                status_str = "with function changes" if has_function_changes else "without function changes"
                print(f"\nNew commit analysis results file created: {output_file} ({status_str})")
            else:
                # Try to append to the existing file efficiently
                try:
                    # If the file already exists, use a trick to append to the JSON array:
                    # 1. Open the file
                    # 2. Seek to position right before the closing ']'
                    # 3. Write a comma + new result + closing bracket
                    with open(output_file, 'r+', encoding='utf-8') as f:
                        # Check if file is a valid JSON array by reading first and last characters
                        f.seek(0)
                        first_char = f.read(1).strip()
                        if first_char != '[':
                            raise ValueError("File is not a JSON array")
                        
                        # Find the position of the last ']'
                        f.seek(0, os.SEEK_END)
                        pos = f.tell() - 1
                        # Go backwards until we find the closing bracket
                        while pos > 0:
                            f.seek(pos)
                            char = f.read(1)
                            if char == ']':
                                break
                            pos -= 1
                        
                        if pos <= 0:
                            raise ValueError("Could not find closing bracket in JSON file")
                        
                        # Count number of items in the array (by counting commas + 1)
                        f.seek(0)
                        content = f.read(pos)
                        # This is an approximation, won't be accurate if commas exist inside strings
                        result_count = content.count(',') + 1
                        
                        # Position file pointer at the position right before the closing bracket
                        f.seek(pos)
                        
                        # Write comma + new object + closing bracket
                        f.write(',')
                        f.write(json.dumps(result_dict, ensure_ascii=False))
                        f.write(']')
                        
                        # Truncate file at current position to remove anything that might have been after
                        f.truncate()
                    
                    status_str = "with function changes" if has_function_changes else "without function changes"
                    print(f"\nCommit analysis result ({status_str}) appended to: {output_file} (total results: approximately {result_count + 1})")
                except (ValueError, json.JSONDecodeError) as e:
                    # If any issue occurs, fall back to the safer but less efficient method
                    print(f"Warning: Couldn't efficiently append to {output_file}. Creating a new file. Error: {e}")
                    
                    # Read all existing content, parse it, add new result, write back
                    try:
                        with open(output_file, 'r', encoding='utf-8') as f:
                            try:
                                existing_data = json.load(f)
                                if not isinstance(existing_data, list):
                                    existing_data = [existing_data]
                            except json.JSONDecodeError:
                                # If the file is not valid JSON, start fresh
                                existing_data = []
                        
                        # Add new result and write back
                        existing_data.append(result_dict)
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(existing_data, f, ensure_ascii=False)
                        
                        status_str = "with function changes" if has_function_changes else "without function changes"
                        print(f"\nCommit analysis results ({status_str}) saved to: {output_file} (total results: {len(existing_data)})")
                    except Exception as e2:
                        # If all else fails, create a new file
                        print(f"Warning: Could not update existing file due to error: {e2}. Creating a new file.")
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump([result_dict], f, ensure_ascii=False)
                        
                        status_str = "with function changes" if has_function_changes else "without function changes"
                        print(f"\nNew commit analysis results file created: {output_file} ({status_str})")
    
    return output_file 