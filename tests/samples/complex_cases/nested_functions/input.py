"""
Test case for nested functions in Python.

This sample contains functions within functions to test
proper identification of nested function boundaries.
"""

def outer_function(param1, param2=None):
    """An outer function containing nested functions."""
    
    x = param1
    
    def inner_function1():
        """First inner function."""
        nonlocal x
        x += 1
        return x
    
    def inner_function2(y):
        """Second inner function with its own parameter."""
        return x + y
        
    # Define a lambda function
    mapper = lambda z: z * inner_function1()
    
    result = inner_function2(10) + mapper(2)
    return result

# A class with a method containing a nested function
class TestClass:
    def method_with_inner(self):
        """A method containing an inner function."""
        counter = 0
        
        def increment():
            """Inner function inside a method."""
            nonlocal counter
            counter += 1
            return counter
            
        return [increment() for _ in range(5)] 