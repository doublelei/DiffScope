# DiffScope Tests

This directory contains tests for the DiffScope library. The tests are organized into unit tests and integration tests.

## Test Structure

- `unit/`: Unit tests that don't require external resources
- `integration/`: Integration tests that interact with external APIs like GitHub
- `conftest.py`: Contains pytest configuration and fixtures
- `run_tests.py`: Helper script for running tests with proper configuration

## Running Tests

### Using the Helper Script

The easiest way to run tests is with the included helper script:

```bash
# Run all unit tests
python tests/run_tests.py --unit

# Run integration tests with verbose output and a GitHub token
python tests/run_tests.py --integration --token=your_github_token_here -s

# Run a specific test file with verbose output
python tests/run_tests.py --file=tests/unit/test_git_analyzer.py -v

# Run all tests including API tests
python tests/run_tests.py --all

# Get help
python tests/run_tests.py --help
```

### Basic Commands

Run all tests (excluding live API tests):
```bash
python -m pytest tests/
```

Run a specific test file:
```bash
python -m pytest tests/unit/test_git_analyzer.py
```

Run a specific test:
```bash
python -m pytest tests/integration/test_commit_analysis.py::test_analyze_commit_full_workflow
```

Run with verbose output:
```bash
python -m pytest tests/ -v
```

Show print statements (don't capture stdout/stderr):
```bash
python -m pytest tests/ -v -s
```

### GitHub API Tests with Function Detection

To run the integration tests that test both GitHub API and function detection:

```bash
# Use the --run-live-api flag to enable real GitHub API access
python -m pytest tests/integration/test_commit_analysis.py -v -s --run-live-api
```

The integration tests will analyze real commits and detect function-level changes. This helps verify that:

1. The GitHub API client works correctly
2. Function detection works across different languages
3. The two components integrate properly to produce accurate results

### GitHub Authentication

For running integration tests, you'll need a GitHub token to avoid rate limits:

**Windows PowerShell**:
```powershell
$env:GITHUB_TOKEN="your_github_token_here"
python -m pytest tests/integration --run-live-api
```

**Windows CMD**:
```cmd
set GITHUB_TOKEN=your_github_token_here
python -m pytest tests/integration --run-live-api
```

**Linux/Mac**:
```bash
export GITHUB_TOKEN=your_github_token_here
python -m pytest tests/integration --run-live-api
```

#### Skip Tests on Missing Token

To skip GitHub API tests entirely when no token is available:

```bash
# Windows PowerShell
$env:SKIP_ON_NO_TOKEN="true"
python -m pytest tests/integration --run-live-api

# Linux/Mac
export SKIP_ON_NO_TOKEN=true
python -m pytest tests/integration --run-live-api
```

## Test Output

Use the `-v` option for verbose output and `-s` to see print statements:

```bash
python -m pytest tests/integration/test_commit_analysis.py -v -s --run-live-api
```

The integration tests use the `print_commit_result` fixture to print detailed information about analysis results, including:
- Commit metadata (SHA, author, date, message)
- Modified files with their changes
- Modified functions with their change types
- Function diffs showing exactly what changed

## CLI Testing for Function Parser

The function parser module includes CLI testing capabilities that allow you to test it against arbitrary input files without modifying the test code.

### Testing with Arbitrary Input Files

Test the parser on any file and display the detected functions:

```bash
# Test a Python file (auto-detects language from file extension)
python -m pytest tests/unit/parsers/test_function_parser.py::TestFunctionParser::test_parse_cli_input -vs --input path/to/your/file.py

# Test a JavaScript file with explicit language specification
python -m pytest tests/unit/parsers/test_function_parser.py::TestFunctionParser::test_parse_cli_input -vs --input path/to/your/file.js --language javascript
```

### Validating Against Expected Output

Compare parser results with expected output:

```bash
python -m pytest tests/unit/parsers/test_function_parser.py::TestFunctionParser::test_parse_cli_input -vs --input path/to/your/file.py --expected-output path/to/expected.json
```

The expected JSON file should have a structure like:

```json
{
  "functions": [
    {
      "name": "function_name",
      "start_line": 10,
      "end_line": 20,
      "node_type": "function"
    },
    ...
  ]
}
```

### Finding Functions at Specific Lines

Check which function contains a specific line:

```bash
python -m pytest tests/unit/parsers/test_function_parser.py::TestFunctionParser::test_find_function_at_line_cli -vs --input path/to/your/file.py --line 42
```

### Creating Expected Output Files

To create an expected output file for validation:

1. Run the parser and redirect output to a file:
   ```bash
   python -m pytest tests/unit/parsers/test_function_parser.py::TestFunctionParser::test_parse_cli_input -vs --input path/to/your/file.py > output.txt
   ```

2. Or use the --output-file option to directly save the JSON output:
   ```bash
   python -m pytest tests/unit/parsers/test_function_parser.py::TestFunctionParser::test_parse_cli_input -vs --input path/to/your/file.py --output-file expected.json
   ```

3. Use this file for validation in subsequent tests:
   ```bash
   python -m pytest tests/unit/parsers/test_function_parser.py::TestFunctionParser::test_parse_cli_input -vs --input path/to/your/file.py --expected-output expected.json
   ```

## Creating New Tests

### Test Naming Conventions

- Test files should be named `test_*.py`
- Test functions should be named `test_*`
- Unit tests that don't require external APIs should be placed in the `unit/` directory
- Tests that require external APIs should be placed in the `integration/` directory and marked with `@pytest.mark.live_api`

### Example Test Function

```python
import pytest
from src import some_function

# Unit test (doesn't require external APIs)
def test_some_functionality():
    # Arrange
    input_value = "test"
    
    # Act
    result = some_function(input_value)
    
    # Assert
    assert result == expected_value

# Integration test (requires GitHub API)
@pytest.mark.live_api
def test_github_functionality():
    # This test will be skipped unless --run-live-api is specified
    # Add proper exception handling for robust GitHub API tests
    try:
        # Test code here
        pass
    except Exception as e:
        if "API rate limit exceeded" in str(e):
            pytest.skip("GitHub API rate limit exceeded. Set GITHUB_TOKEN environment variable.")
        else:
            raise
```

### Useful Fixtures

- `print_commit_result`: Prints detailed information about a CommitAnalysisResult object, including function changes
- `mock_github_api`: Mock GitHub API to avoid actual network calls during unit testing
- `input_file`, `language`, etc.: Fixtures for CLI-based testing 