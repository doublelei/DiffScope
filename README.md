# DiffScope

A specialized Git analysis tool that extracts function-level changes from commits, allowing developers to focus on semantic changes rather than just line-by-line diffs.

## Current Status

**Phase 1 Implemented**: The library now supports extracting file-level changes from GitHub commits. Function-level change detection will be added in Phase 2.

## Overview

DiffScope helps developers understand code changes at a more semantic level by identifying which functions were modified in a Git commit, rather than just showing raw line-by-line diffs. This makes code reviews more efficient and helps in understanding the actual impact of changes.

Key features:
- Extract file-level changes from Git commits
- Detect function boundaries in various programming languages
- Identify function-level changes between commits
- Present changes in a clear, structured format

## Project Structure

```
DiffScope/
├── src/                  # Source code
│   ├── core/             # Core functionality
│   │   ├── git_analyzer.py     # Git commit analysis
│   │   └── function_detector.py # Function detection logic
│   ├── parsers/          # Language-specific parsers
│   │   └── language_parser.py  # Base and language-specific parsers
│   ├── utils/            # Utility functions
│   │   └── github_api.py        # GitHub API operations (using PyGithub)
│   └── models.py         # Data models
├── tests/                # Test suite
├── examples/             # Usage examples
├── docs/                 # Documentation
├── setup.py              # Package setup script
└── requirements.txt      # Dependencies
```

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/DiffScope.git
cd DiffScope

# Install dependencies
pip install -r requirements.txt

# Install the package in development mode
pip install -e .
```

## Usage

```python
from diffscope import analyze_commit

# Analyze a GitHub commit by URL
results = analyze_commit("https://github.com/username/repo/commit/abc123")

# Access the results
for file in results.modified_files:
    print(f"File: {file.filename}, Changes: {file.changes}")
    print(f"Language: {file.language}")

# Function-level changes (coming in Phase 2)
# for func in results.modified_functions:
#     print(f"Function: {func.function_name} in {func.file_path}")
#     print(f"Type of change: {func.change_type}")
#     print(f"Diff:\n{func.diff}")
```

## Example

Try out the example script:

```bash
python examples/analyze_commit.py
```

This will analyze a sample commit and display the results, as well as save them to `analysis_result.json`.

## Implementation Details

DiffScope works by:
1. Fetching commit information from GitHub using PyGithub
2. Parsing the modified files to detect function boundaries (coming in Phase 2)
3. Mapping line changes to functions (coming in Phase 2)
4. Generating function-level diff information (coming in Phase 2)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
