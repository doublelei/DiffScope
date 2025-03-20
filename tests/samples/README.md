# DiffScope Test Samples

This directory contains code samples used in the DiffScope test suite. These samples provide realistic code patterns for testing function detection, boundary identification, and content extraction across multiple programming languages.

## Directory Structure

```
samples/
├── python/              # Python code samples
│   ├── simple_function.py
│   ├── class_with_methods.py
│   ├── functions_with_line_numbers.py
│   └── ...
├── javascript/          # JavaScript code samples
│   ├── simple_function.js
│   ├── class_with_methods.js
│   └── ...
├── complex_cases/       # Complex test cases with inputs and expected outputs
│   ├── nested_functions/
│   │   ├── input.py     # Input sample code
│   │   └── expected.json # Expected parser output
│   ├── decorators/
│   │   ├── input.py
│   │   └── expected.json
│   └── ...
└── fixtures/            # JSON fixtures for expected outputs
    ├── python_functions.json
    ├── javascript_functions.json
    └── ...
```

## Usage in Tests

These samples are primarily used for:

1. Testing function detection and boundary identification
2. Verifying correct extraction of function content
3. Handling edge cases and complex code patterns
4. Validating support for different programming languages

## Complex Test Cases

For complex test cases, follow this approach:

1. Create a subdirectory in `complex_cases/` for your test scenario (e.g., `nested_functions/`)
2. Add an input file with your test code (`input.py`, `input.js`, etc.)
3. Create an `expected.json` file with the expected parser output:

```json
{
  "functions": [
    {
      "name": "outer_function",
      "start_line": 1,
      "end_line": 10,
      "node_type": "function",
      "metadata": {
        "nested_functions": 2
      }
    },
    {
      "name": "inner_function1",
      "start_line": 3,
      "end_line": 5,
      "node_type": "function",
      "parent": "outer_function"
    },
    ...
  ]
}
```

4. In your test file, use the helper function `test_parser_with_case(case_name)` to run the test

## Adding New Samples

When adding new samples:

1. Place the file in the appropriate language subdirectory
2. Use descriptive filenames that indicate the code pattern being tested
3. Add clear comments in the code to indicate test boundaries or special cases
4. Consider adding corresponding expected outputs in the fixtures directory

## Style Guidelines

Sample code should:

1. Be simple and focused on the pattern being tested
2. Include descriptive comments explaining key features
3. Use consistent indentation and formatting
4. Avoid external dependencies
5. Be self-contained and runnable independently 