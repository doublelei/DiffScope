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

### GitHub API Tests

Some tests require GitHub API access, which may be subject to rate limits. These tests are marked with the `@pytest.mark.live_api` decorator and are skipped by default.

To run tests that use the GitHub API:

```bash
python -m pytest tests/ --run-live-api
```

#### GitHub Authentication

To avoid rate limits, set a GitHub token before running the tests:

**Windows PowerShell**:
```powershell
$env:GITHUB_TOKEN="your_github_token_here"
python -m pytest tests/ --run-live-api
```

**Windows CMD**:
```cmd
set GITHUB_TOKEN=your_github_token_here
python -m pytest tests/ --run-live-api
```

**Linux/Mac**:
```bash
export GITHUB_TOKEN=your_github_token_here
python -m pytest tests/ --run-live-api
```

#### Skip Tests on Missing Token

To skip GitHub API tests entirely when no token is available:

```bash
# Windows PowerShell
$env:SKIP_ON_NO_TOKEN="true"
python -m pytest tests/ --run-live-api

# Linux/Mac
export SKIP_ON_NO_TOKEN=true
python -m pytest tests/ --run-live-api
```

## Test Output

Use the `-v` option for verbose output and `-s` to see print statements:

```bash
python -m pytest tests/integration/test_commit_analysis.py -v -s --run-live-api
```

The integration tests use the `print_commit_result` fixture to print detailed information about analysis results.

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
    # Add RateLimitExceededException handling for robust GitHub API tests
    try:
        # Test code here
        pass
    except RateLimitExceededException:
        pytest.skip("GitHub API rate limit exceeded. Set GITHUB_TOKEN environment variable.")
```

### Useful Fixtures

- `print_commit_result`: Prints detailed information about a CommitAnalysisResult object 