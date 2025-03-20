"""
Tests for the function_parser module.

This includes tests for function detection, boundary identification, and content extraction.
"""

import os
import json
import pytest
from src.parsers.function_parser import (
    parse_functions,
    get_function_at_line,
    extract_function_content,
    FUNCTION_QUERIES
)

# Sample file paths
SAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "samples")
PYTHON_SAMPLES = {
    "simple_function": os.path.join(SAMPLES_DIR, "python", "simple_function.py"),
    "class_with_methods": os.path.join(SAMPLES_DIR, "python", "class_with_methods.py"),
    "functions_with_line_numbers": os.path.join(SAMPLES_DIR, "python", "functions_with_line_numbers.py")
}
JS_SAMPLES = {
    "simple_function": os.path.join(SAMPLES_DIR, "javascript", "simple_function.js"),
    "class_with_methods": os.path.join(SAMPLES_DIR, "javascript", "class_with_methods.js")
}


def read_sample(file_path):
    """Read a sample file and return its content."""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


class TestFunctionParser:
    """Test cases for the function_parser module."""

    def test_parse_functions_python(self):
        """Test parsing Python functions."""
        # Load and combine samples to test multiple function types
        simple_function = read_sample(PYTHON_SAMPLES["simple_function"])
        class_with_methods = read_sample(PYTHON_SAMPLES["class_with_methods"])
        code = simple_function + "\n\n" + class_with_methods
        
        functions = parse_functions(code, "python")
        
        # Should find 4 functions (1 regular function + 3 methods including __init__)
        assert len(functions) >= 4
        
        # Check the regular function
        simple_func = next(f for f in functions if f['name'] == 'simple_function')
        assert simple_func['node_type'] == 'function'
        
        # Check methods
        method1 = next(f for f in functions if f['name'] == 'method1')
        assert method1['node_type'] == 'method'
        
        method2 = next(f for f in functions if f['name'] == 'method2')
        assert method2['node_type'] == 'method'

    def test_parse_functions_javascript(self):
        """Test parsing JavaScript functions."""
        # Load and combine samples
        simple_function = read_sample(JS_SAMPLES["simple_function"])
        class_with_methods = read_sample(JS_SAMPLES["class_with_methods"])
        code = simple_function + "\n\n" + class_with_methods
        
        functions = parse_functions(code, "javascript")
        
        # Should find multiple functions
        assert len(functions) >= 5  # 1 regular function + constructor + 2 methods + arrow function
        
        # Check the regular function
        simple_func = next(f for f in functions if f['name'] == 'simpleFunction')
        assert simple_func['node_type'] == 'function'
        
        # Check method
        method1 = next(f for f in functions if f['name'] == 'method1')
        assert method1['node_type'] == 'method'
        
        # Check arrow function
        arrow_funcs = [f for f in functions if f['node_type'] == 'arrow_function']
        assert len(arrow_funcs) >= 1
        assert 'arrowFunction' in [f['name'] for f in arrow_funcs]
    
    def test_parse_functions_unsupported_language(self):
        """Test parsing functions in an unsupported language."""
        code = "function test() {}"
        functions = parse_functions(code, "unsupported_language")
        assert functions == []
    
    def test_parse_empty_content(self):
        """Test parsing empty content."""
        functions = parse_functions("", "python")
        assert functions == []
        
        functions = parse_functions(None, "python")
        assert functions == []
    
    def test_get_function_at_line(self):
        """Test finding a function containing a specific line."""
        code = read_sample(PYTHON_SAMPLES["functions_with_line_numbers"])
        
        # Line in the middle of func1
        func = get_function_at_line(code, "python", 3)
        assert func is not None
        assert func['name'] == 'func1'
        
        # Line in the middle of func2
        func = get_function_at_line(code, "python", 8)
        assert func is not None
        assert func['name'] == 'func2'
        
        # Line between functions (blank line)
        func = get_function_at_line(code, "python", 5)
        assert func is None
        
        # Line out of range
        func = get_function_at_line(code, "python", 100)
        assert func is None
    
    def test_extract_function_content(self):
        """Test extracting function content from file content."""
        code = read_sample(PYTHON_SAMPLES["functions_with_line_numbers"])
        functions = parse_functions(code, "python")
        func1 = next(f for f in functions if f['name'] == 'func1')
        func2 = next(f for f in functions if f['name'] == 'func2')
        
        # Extract func1 content
        content1 = extract_function_content(code, func1)
        assert "print(1)" in content1
        assert "print(2)" in content1
        assert "print(3)" not in content1
        
        # Extract func2 content
        content2 = extract_function_content(code, func2)
        assert "print(3)" in content2
        assert "print(4)" in content2
        assert "print(1)" not in content2
    
    def test_extract_function_invalid_content(self):
        """Test extracting function content with invalid inputs."""
        func_info = {'start_line': 1, 'end_line': 3}
        
        # Empty content
        content = extract_function_content("", func_info)
        assert content is None
        
        # None content
        content = extract_function_content(None, func_info)
        assert content is None
        
        # Line numbers out of range
        func_info = {'start_line': 100, 'end_line': 105}
        content = extract_function_content("Line 1\nLine 2\nLine 3", func_info)
        assert content is None
        
    # CLI-based testing methods
    
    def test_parse_cli_input(self, input_content, detect_language, expected_output):
        """
        Test parsing functions from a file specified via command line.
        
        Usage:
            pytest -xvs tests/unit/parsers/test_function_parser.py::TestFunctionParser::test_parse_cli_input --input path/to/file.py
        """
        # Skip if required arguments are missing
        if input_content is None:
            pytest.skip("No input file specified. Use --input argument.")
            
        if detect_language is None:
            pytest.skip("Could not determine language. Please specify using --language.")
        
        # Parse the input
        functions = parse_functions(input_content, detect_language)
        
        # Print the parsed functions in a readable format
        print("\n== Parsed functions: ==")
        formatted_output = json.dumps({"functions": functions}, indent=2)
        print(formatted_output)
        
        # If expected output is provided, validate against it
        if expected_output:
            expected_functions = expected_output.get("functions", [])
            
            # Perform basic validation
            assert len(functions) == len(expected_functions), (
                f"Expected {len(expected_functions)} functions, got {len(functions)}"
            )
            
            # Detailed validation
            errors = []
            for i, (actual, expected) in enumerate(zip(functions, expected_functions)):
                if actual.get("name") != expected.get("name"):
                    errors.append(f"Function {i}: name mismatch. Expected {expected.get('name')}, got {actual.get('name')}")
                
                if actual.get("start_line") != expected.get("start_line"):
                    errors.append(f"Function {i} ({actual.get('name')}): start_line mismatch. "
                                  f"Expected {expected.get('start_line')}, got {actual.get('start_line')}")
                
                if actual.get("end_line") != expected.get("end_line"):
                    errors.append(f"Function {i} ({actual.get('name')}): end_line mismatch. "
                                  f"Expected {expected.get('end_line')}, got {actual.get('end_line')}")
            
            if errors:
                for error in errors:
                    print(f"Error: {error}")
                assert False, f"Found {len(errors)} discrepancies in parsing"
            
            print("\n✅ Output matches expected functions!")
            
    def test_find_function_at_line_cli(self, input_content, detect_language, request):
        """
        Test finding a function at a specific line via command line.
        
        Usage:
            pytest -xvs tests/unit/parsers/test_function_parser.py::TestFunctionParser::test_find_function_at_line_cli --input path/to/file.py --line 42
        """
        # Get line number from command line
        line_number = request.config.getoption("--line")
        
        if line_number is None or input_content is None or detect_language is None:
            pytest.skip("Required parameters missing. Use --input and --line arguments.")
        
        try:
            line_number = int(line_number)
        except ValueError:
            pytest.fail(f"Invalid line number: {line_number}")
        
        function = get_function_at_line(input_content, detect_language, line_number)
        
        if function:
            print(f"\nFunction found at line {line_number}:")
            print(json.dumps(function, indent=2))
        else:
            print(f"\nNo function found at line {line_number}")
        
        # No assertions - this is just for inspection 