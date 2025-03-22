"""
Function parsing module for detecting function boundaries and extracting metadata.

This module provides utilities to detect and extract information about functions
in source code using tree-sitter. It supports multiple programming languages.
"""

from typing import List, Dict, Optional, Any, Tuple
import logging
from .tree_sitter_utils import (
    get_tree_sitter_parser,
    get_tree_sitter_language,
    is_language_supported,
    parse_code
)

# Set up logging
logger = logging.getLogger(__name__)

# Tree-sitter queries for functions in different languages
FUNCTION_QUERIES = {
    # Python query
    "python": """
        (function_definition
          name: (identifier) @function_name
        ) @function
        
        (class_definition
          name: (identifier) @class_name
          body: (block (function_definition
            name: (identifier) @method_name
          ) @method)
        )
    """,
    
    # JavaScript query
    "javascript": """
        (function_declaration
          name: (identifier) @function_name
        ) @function
        
        (method_definition
          name: (property_identifier) @method_name
        ) @method
        
        (arrow_function) @arrow_function
        
        (variable_declarator
          name: (identifier) @var_name
          value: (arrow_function) @arrow_function_var
        )
    """,
    
    # TypeScript inherits JavaScript's query and adds its own patterns
    "typescript": """
        (function_declaration
          name: (identifier) @function_name
        ) @function
        
        (method_definition
          name: (property_identifier) @method_name
        ) @method
        
        (arrow_function) @arrow_function
        
        (variable_declarator
          name: (identifier) @var_name
          value: (arrow_function) @arrow_function_var
        )
        
        (interface_declaration
          name: (type_identifier) @interface_name
        ) @interface
    """,
    
    # C query
    "c": """
        (function_definition
          declarator: (function_declarator
            declarator: (identifier) @function_name)
        ) @function
        
        (declaration
          declarator: (function_declarator
            declarator: (identifier) @function_name)
        ) @function_declaration
    """,
    
    # C++ query
    "cpp": """
        (function_definition
          declarator: (function_declarator
            declarator: (identifier) @function_name)
        ) @function
        
        (declaration
          declarator: (function_declarator
            declarator: (identifier) @function_name)
        ) @function_declaration
        
        (class_specifier
          name: (type_identifier) @class_name
        ) @class
        
        (method_definition
          declarator: (function_declarator
            declarator: (field_identifier) @method_name)
        ) @method
        
        (class_specifier
          body: (field_declaration_list
            (function_definition
              declarator: (function_declarator
                declarator: (field_identifier) @method_name))
          ) @method
        )
    """,
    
    # Java query
    "java": """
        (method_declaration
          name: (identifier) @method_name
        ) @method
        
        (constructor_declaration
          name: (identifier) @constructor_name
        ) @constructor
        
        (class_declaration
          name: (identifier) @class_name
        ) @class
        
        (interface_declaration
          name: (identifier) @interface_name
        ) @interface
    """,
    
    # PHP query
    "php": """
        (function_definition
          name: (name) @function_name
        ) @function
        
        (method_declaration
          name: (name) @method_name
        ) @method
        
        (class_declaration
          name: (name) @class_name
        ) @class
    """,
    
    # Go query
    "go": """
        (function_declaration
          name: (identifier) @function_name
        ) @function
        
        (method_declaration
          name: (field_identifier) @method_name
        ) @method
        
        (type_declaration
          (type_spec
            name: (type_identifier) @type_name
            type: (struct_type)
          )
        ) @struct
        
        (type_declaration
          (type_spec
            name: (type_identifier) @interface_name
            type: (interface_type)
          )
        ) @interface
    """,
    
    # Ruby query
    "ruby": """
        (method
          name: (identifier) @method_name
        ) @method
        
        (singleton_method
          name: (identifier) @singleton_method_name
        ) @singleton_method
        
        (class
          name: (constant) @class_name
        ) @class
        
        (module
          name: (constant) @module_name
        ) @module
        
        (method_parameters
          (identifier) @parameter
        )
    """,
    
    # Rust query
    "rust": """
        (function_item
          name: (identifier) @function_name
        ) @function
        
        (impl_item
            type: (type_identifier) @impl_type
            body: (declaration_list
                (function_item
                name: (identifier) @method_name
                )+
            )
        ) @impl
        
        (struct_item
          name: (type_identifier) @struct_name
        ) @struct
        
        (trait_item
          name: (type_identifier) @trait_name
        ) @trait
    """,
    
    # csharp query
    "csharp": """
        (method_declaration
          name: (identifier) @method_name
        ) @method
        
        (constructor_declaration
          name: (identifier) @constructor_name
        ) @constructor
        
        (property_declaration
          name: (identifier) @property_name
        ) @property
        
        (class_declaration
          name: (identifier) @class_name
        ) @class
        
        (interface_declaration
          name: (identifier) @interface_name
        ) @interface
    """
}


def parse_functions(content: str, language: str) -> List[Dict]:
    """
    Parse source code to identify functions.
    
    Args:
        content: Source code content
        language: Programming language
        
    Returns:
        List of dictionaries containing function information
    """
    language = language.lower()
    if language not in FUNCTION_QUERIES:
        logger.warning(f"Language '{language}' is not supported for function parsing")
        return []
    
    if not content:
        return []
    

    # Get parser and language
    parser = get_tree_sitter_parser(language)
    tree_sitter_lang = get_tree_sitter_language(language)
    
    # Parse the code
    tree = parser.parse(bytes(content, 'utf8'))
    
    # Create the query
    query = tree_sitter_lang.query(FUNCTION_QUERIES[language])
    
    # Execute the query to get captures
    captures = query.captures(tree.root_node)
    
    # Create function objects from the captures
    functions = []
    
    # Track function positions to avoid duplicates
    # Key is (start_line, end_line) tuple
    function_positions = {}
    
    # Process methods first so they take precedence for node_type
    node_types_by_position = {}
    
    # First, mark methods specifically
    method_types = ['method', 'constructor', 'singleton_method']
    for method_type in method_types:
        if method_type in captures:
            for method_node in captures[method_type]:
                start_line, start_col = method_node.start_point
                end_line, end_col = method_node.end_point
                
                # Convert to 1-indexed lines
                start_line += 1
                end_line += 1
                
                position_key = (start_line, end_line)
                node_types_by_position[position_key] = method_type
    
    # Process function and method nodes
    function_types = [
        'function', 'method', 'constructor', 'arrow_function', 
        'singleton_method', 'function_declaration'
    ]
    
    for function_type in function_types:
        if function_type not in captures:
            continue
            
        for func_node in captures[function_type]:
            # Get the line range
            start_line, start_col = func_node.start_point
            end_line, end_col = func_node.end_point
            
            # Convert to 1-indexed lines
            start_line += 1
            end_line += 1
            
            # Skip if we already processed a function at this position
            position_key = (start_line, end_line)
            if position_key in function_positions:
                continue
            
            # Determine the correct node type (prefer method over function)
            node_type = node_types_by_position.get(position_key, function_type)
            
            # Initialize function data
            func_data = {
                'name': None,
                'start_line': start_line,
                'end_line': end_line,
                'parameters': [],
                'node_type': node_type
            }
            
            # Choose the right name capture based on the node_type
            name_capture_mapping = {
                'function': 'function_name',
                'method': 'method_name',
                'constructor': 'constructor_name',
                'singleton_method': 'singleton_method_name',
                'function_declaration': 'function_name',
                'arrow_function': 'var_name'
            }
            
            name_capture = name_capture_mapping.get(node_type, 'function_name')
            
            if name_capture in captures:
                # For each name node, check if it's contained within this function
                for name_node in captures[name_capture]:
                    if check_node_relationship(name_node, func_node, 'contains'):
                        func_data['name'] = name_node.text.decode('utf8')
                        break
                        
            # Extract parameters based on language and node type
            if language == 'rust' and (node_type == 'function' or node_type == 'method'):
                # Find parameters in Rust functions
                for child in func_node.children:
                    if child.type == 'parameters':
                        # Process each parameter in the parameters list
                        for param_node in child.children:
                            if param_node.type == 'parameter':
                                # Extract parameter name from parameter node
                                param_name = None
                                for param_child in param_node.children:
                                    if param_child.type == 'identifier':
                                        param_name = param_child.text.decode('utf8')
                                        break
                                
                                if param_name:
                                    func_data['parameters'].append(param_name)
            
            # Extract parameters for Ruby methods
            elif language == 'ruby' and (node_type == 'method' or node_type == 'singleton_method'):
                # For Ruby, we need to check all parameter nodes and see if they belong to this method
                if 'parameter' in captures:
                    # We'll store parameters with their position to ensure correct order
                    method_params = []
                    
                    for param_node in captures['parameter']:
                        # Find the parent method_parameters node
                        method_params_node = param_node.parent
                        if method_params_node:
                            # Find the parent method node (could be method or singleton_method)
                            method_node = method_params_node.parent
                            if method_node and method_node.id == func_node.id:
                                # This parameter belongs to this method
                                param_name = param_node.text.decode('utf8')
                                # Store both the parameter name and its position
                                method_params.append((param_node.start_byte, param_name))
                    
                    # Sort parameters by their position to maintain the correct order
                    method_params.sort(key=lambda x: x[0])
                    
                    # Add parameters in the correct order
                    for _, param_name in method_params:
                        if param_name not in func_data['parameters']:
                            func_data['parameters'].append(param_name)
            
            # Extract parameters for csharp methods
            elif language == 'csharp' and (node_type == 'method' or node_type == 'constructor'):
                # Find parameter list in csharp method/constructor
                for child in func_node.children:
                    if child.type == 'parameter_list':
                        # Process each parameter in the list
                        for param_child in child.children:
                            if param_child.type == 'parameter':
                                # Find the identifier within the parameter
                                for param_part in param_child.children:
                                    if param_part.type == 'identifier':
                                        param_name = param_part.text.decode('utf8')
                                        if param_name not in func_data['parameters']:
                                            func_data['parameters'].append(param_name)
            
            # Only add if we found a name (or for anonymous functions in some languages)
            if func_data['name'] or node_type == 'arrow_function':
                # For anonymous functions, create a placeholder name
                if not func_data['name'] and node_type == 'arrow_function':
                    func_data['name'] = f"anonymous_func_{start_line}_{start_col}"
                
                functions.append(func_data)
                function_positions[position_key] = True
    
    # Handle language-specific cases
    
    # JavaScript/TypeScript arrow functions
    if language in ['javascript', 'typescript']:
        # Process arrow functions
        if 'arrow_function' in captures:
            for arrow_node in captures['arrow_function']:
                start_line, start_col = arrow_node.start_point
                end_line, end_col = arrow_node.end_point
                
                # Convert to 1-indexed lines
                start_line += 1
                end_line += 1
                
                # Skip if we already processed a function at this position
                position_key = (start_line, end_line)
                if position_key in function_positions:
                    continue
                
                # Check if this is a named arrow function in a variable declaration
                name = None
                if 'var_name' in captures:
                    for name_node in captures['var_name']:
                        # Check if this name is for this arrow function
                        # Usually it will be the closest name before the arrow function
                        name_line, name_col = name_node.start_point
                        if name_line <= start_line - 1 and check_node_relationship(name_node, arrow_node, 'nearby'):
                            name = name_node.text.decode('utf8')
                            break
                
                # If no name found, use an anonymous name
                if not name:
                    name = f"anonymous_func_{start_line}_{start_col}"
                
                func_data = {
                    'name': name,
                    'start_line': start_line,
                    'end_line': end_line,
                    'parameters': [],
                    'node_type': 'arrow_function'
                }
                functions.append(func_data)
                function_positions[position_key] = True
    
    logger.debug(f"Found {len(functions)} functions in {language} code")
    return functions
    


def check_node_relationship(
    node: Any, 
    reference_node: Any, 
    relationship_type: str = 'contains',
    max_lines: int = 3
) -> bool:
    """
    Check the relationship between two nodes - either containment or proximity.
    
    Args:
        node: The node to check
        reference_node: The reference node (parent or nearby node)
        relationship_type: Type of relationship to check ('contains' or 'nearby')
        max_lines: Maximum number of lines between nodes for 'nearby' relationship
        
    Returns:
        True if the specified relationship exists, False otherwise
    """
    if relationship_type == 'contains':
        # Check if node is contained within reference_node
        start_byte = node.start_byte
        end_byte = node.end_byte
        return (start_byte >= reference_node.start_byte and end_byte <= reference_node.end_byte)
    
    elif relationship_type == 'nearby':
        # Check if nodes are in close proximity by line number
        node_line = node.start_point[0]
        ref_line = reference_node.start_point[0]
        return abs(node_line - ref_line) <= max_lines
    
    else:
        raise ValueError(f"Unknown relationship type: {relationship_type}")


def get_function_at_line(content: str, language: str, line_number: int) -> Optional[Dict]:
    """
    Find the function containing the specified line number.
    
    Args:
        content: Source code content
        language: Programming language
        line_number: Line number to check (1-indexed)
        
    Returns:
        Function information if found, None otherwise
    """
    functions = parse_functions(content, language)
    
    for func in functions:
        if func['start_line'] <= line_number <= func['end_line']:
            return func
    
    return None


def extract_function_content(content: str, start_line: int, end_line: int) -> Optional[str]:
    """
    Extract the content of a function from file content.
    
    Args:
        content: Content of the file
        start_line: Start line of the function
        end_line: End line of the function
        
    Returns:
        String containing the function code
    """
    if not content:
        return None
        
    
    lines = content.splitlines()
    if 0 < start_line <= len(lines) and 0 < end_line <= len(lines):
        return '\n'.join(lines[start_line-1:end_line])
    
    return None 