# DiffScope

Function-level git commit analysis tool. DiffScope helps you analyze Git commits to identify which functions were modified, added, or deleted.

## Features

- Analyze GitHub commits at both file and function levels
- Identify exactly which functions were changed in each commit
- Detect function changes including signature, body, and docstring changes
- Supports multiple programming languages using tree-sitter
- Simple API for integration into other tools

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/DiffScope.git
cd DiffScope

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Basic Usage

```python
from diffscope import analyze_commit

# Analyze a GitHub commit
result = analyze_commit("https://github.com/owner/repo/commit/sha")

# Print file-level changes
print(f"Files changed: {len(result.modified_files)}")
for file in result.modified_files:
    print(f"- {file.filename}: +{file.additions} -{file.deletions}")

# Print function-level changes
print(f"Functions changed: {len(result.modified_functions)}")
for function in result.modified_functions:
    print(f"- {function.name} in {function.file}: {function.change_type}")
```

### GitHub Authentication

To avoid rate limits, set a GitHub token in your environment:

```bash
# Linux/Mac
export GITHUB_TOKEN=your_token_here

# Windows PowerShell
$env:GITHUB_TOKEN="your_token_here"

# Windows CMD
set GITHUB_TOKEN=your_token_here
```

## Running Tests

DiffScope includes a comprehensive test suite with both unit tests and integration tests.

### Unit Tests

Run the unit tests (no GitHub API calls):

```bash
python -m pytest tests/unit
```

### Integration Tests

Integration tests require the `--run-live-api` flag to enable tests that make real GitHub API calls:

```bash
# Run with a GitHub token to avoid rate limits
export GITHUB_TOKEN=your_token_here
python -m pytest tests/integration --run-live-api
```

You can also use the provided test helper:

```bash
# Run all tests including integration tests
python tests/run_tests.py --all --token=your_github_token_here
```

### Testing with Verbose Output

To see detailed test output including function changes:

```bash
python -m pytest tests/integration/test_commit_analysis.py -v -s --run-live-api
```

## Supported Languages

DiffScope currently supports function detection for:

- Python
- JavaScript
- TypeScript
- Java
- C/C++
- Go

## Project Structure

```
src/
├── parsers/          # Function parsing using tree-sitter
├── core/             # Core analysis functionality
├── utils/            # Utility functions and tools
├── models.py         # Data models
└── __init__.py       # Main API

tests/
├── unit/             # Unit tests
├── integration/      # Integration tests
└── samples/          # Test data
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup

1. Clone the repository
2. Install development dependencies: `pip install -r requirements-dev.txt`
3. Run the tests: `python -m pytest`

### Adding Tests

When adding features, please add corresponding tests:

- Unit tests for isolated functionality
- Integration tests for end-to-end workflows

See the [test documentation](tests/README.md) for more details.

## License

[MIT License](LICENSE)
