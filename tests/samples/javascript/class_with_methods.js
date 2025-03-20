/**
 * A simple class with methods
 */
class MyClass {
    constructor() {
        this.value = 42;
    }
    
    /**
     * First method that returns a string
     */
    method1() {
        return "Hello from method1";
    }
    
    /**
     * Second method with parameters
     */
    method2(param1, param2 = 0) {
        return param1 + param2;
    }
}

/**
 * An arrow function example
 */
const arrowFunction = (param) => {
    return param * 2;
}; 