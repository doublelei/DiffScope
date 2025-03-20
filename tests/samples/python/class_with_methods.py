class MyClass:
    """A simple class with methods."""
    
    def __init__(self, value=0):
        self.value = value
    
    def method1(self):
        """First method that returns a string."""
        return "Hello from method1"
        
    def method2(self, arg1, arg2=None):
        """Second method with multiple arguments.
        
        Args:
            arg1: First argument
            arg2: Optional second argument
        """
        if arg2 is None:
            return arg1
        return arg1 + arg2 