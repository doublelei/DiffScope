# DiffScope Development Plan

This document outlines the development strategy for implementing DiffScope, a tool for analyzing function-level changes in Git commits.

## 1. System Architecture

DiffScope will be implemented using a modular architecture with three main components:

```
┌─────────────────┐     ┌───────────────────┐     ┌─────────────────────────┐
│                 │     │                   │     │                         │
│  Git Change     │────>│  Function         │────>│  Function-Level         │
│  Processing     │     │  Boundary         │     │  Change                 │
│                 │     │  Detection        │     │  Identification         │
└─────────────────┘     └───────────────────┘     └─────────────────────────┘
```

While these components will execute sequentially in the final workflow, we'll design them with well-defined interfaces so they can be developed and tested independently.

## 1.1 Simplification Constraints

For the initial version, we will focus on a minimal viable product with the following constraints:

1. **No Repository Cloning**: We will only use Git APIs (GitHub, GitLab, etc.) to analyze repositories without cloning them locally.
2. **Remote Public Repositories Only**: We will only support remote public repositories, not local repositories.
3. **Minimal Error Handling**: We'll implement basic error handling but accept that some edge cases may not be handled in the initial version.
4. **Focus on Core Functionality**: We'll prioritize the core workflow over advanced features or optimizations.
5. **Limited Language Support**: We'll start with 2-3 key languages (Python, JavaScript) and expand later.

These constraints help us deliver a working solution quickly while avoiding over-engineering.

## 2. Module Design

### 2.1 Git Change Processing Module

**Purpose:** Extract raw file changes from Git commits

**Components:**
- Repository handler: Clone/fetch repositories when needed
- Commit retriever: Get specific commits by URL or SHA
- Diff extractor: Extract file-level diffs from commits
- File content extractor: Get before/after versions of changed files

**Input:** Git commit URL or SHA
**Output:** List of `ModifiedFile` objects with file-level changes

### 2.2 Function Boundary Detection Module

**Purpose:** Identify function boundaries in source code files

**Components:**
- Language detector: Determine programming language of files
- Parser factory: Create appropriate parser for each language
- Language-specific parsers: Extract function boundaries
- Function mapper: Map files to their contained functions

**Input:** File content (before and after versions)
**Output:** Function boundaries with metadata (name, start/end lines)

### 2.3 Function-Level Change Identification Module

**Purpose:** Determine which functions changed and how they changed

**Components:**
- Change mapper: Map line changes to function boundaries
- Function differ: Generate function-level diffs
- Change classifier: Determine type of change (added, modified, removed)
- Result formatter: Create structured output of changed functions

**Input:** File changes and function boundaries
**Output:** List of `ModifiedFunction` objects with function-level changes

## 3. Development Phases

### Phase 1: Infrastructure and Core Git Processing (Weeks 1-2)

#### Goals:
- Set up project structure and CI/CD pipeline
- Implement core Git commit retrieval and file change extraction
- Create basic CLI interface

#### Tasks:
1. Set up development environment and project structure
2. Implement Git repository handler (clone, checkout)
3. Implement commit retrieval from URLs and SHAs
4. Extract file-level changes from commits
5. Implement basic CLI with commit input handling
6. Write tests for Git processing module

#### Deliverables:
- Working command-line tool that extracts file-level changes
- Ability to process both local and remote repositories
- Unit tests for Git processing functionality

### Phase 2: Function Boundary Detection (Weeks 3-4)

#### Goals:
- Set up Tree-sitter for parsing code
- Create language detection system
- Implement function boundary detection for initial languages

#### Tasks:
1. Integrate Tree-sitter and language grammars
2. Implement language detection based on file extensions and content
3. Create base parser interface
4. Implement language-specific parsers (start with Python, JavaScript)
5. Create function boundary detection algorithm
6. Map file line ranges to function definitions
7. Write tests for function detection module

#### Deliverables:
- Function boundary detection for 2-3 initial languages
- Language detection system
- Unit tests for parser components

### Phase 3: Function-Level Change Identification (Weeks 5-6)

#### Goals:
- Map line changes to function boundaries
- Generate function-level diffs
- Classify function changes

#### Tasks:
1. Implement algorithm to map file changes to function boundaries
2. Create function change classifier (added, modified, removed)
3. Generate function-specific diffs with context
4. Implement function move/rename detection (optional)
5. Create structured output of changed functions
6. Write tests for change identification module

#### Deliverables:
- Complete function-level change detection
- Classified function changes with diffs
- Unit tests for change identification

### Phase 4: Integration and Polish (Weeks 7-8)

#### Goals:
- Integrate all modules
- Improve error handling and edge cases
- Create user-friendly output formats
- Add additional language support

#### Tasks:
1. Integrate all modules with well-defined interfaces
2. Implement comprehensive error handling
3. Add output formats (JSON, markdown, HTML)
4. Add support for additional languages
5. Performance optimization
6. Create comprehensive documentation
7. End-to-end testing

#### Deliverables:
- Complete integrated tool
- Comprehensive documentation
- Multiple output formats
- Support for 5+ programming languages

## 4. Testing Strategy

### Unit Testing
- Each module will have dedicated unit tests
- Mock interfaces between modules
- Test with various language samples and diff scenarios

### Integration Testing
- Test the complete pipeline with real Git repositories
- Include edge cases like merge commits, large diffs
- Test with multiple languages in the same repository

### Performance Testing
- Benchmark processing time for various repository sizes
- Optimize for large diffs and repositories

## 5. Development Approach

### Modular Development
While the modules execute sequentially in the final workflow, we'll develop them with clear interfaces that allow for independent development and testing. This approach has several advantages:

1. **Parallel Development:** Team members can work on different modules simultaneously
2. **Testability:** Each module can be tested in isolation with mock inputs
3. **Flexibility:** Implementation details can change within a module without affecting others
4. **Extensibility:** New language support or Git backends can be added without changing the core logic

### Dependency Management

The modules have these dependencies:

- **Git Change Processing:** External dependency on Git repositories
- **Function Boundary Detection:** Depends on file content from Git Change Processing
- **Function-Level Change Identification:** Depends on outputs from both previous modules

To manage these dependencies during development:

1. Create mock data generators for each module interface
2. Define clear data exchange formats between modules
3. Use dependency injection for module interactions

## 6. Implementation Considerations

### Language Support Strategy
Start with a few widely used languages (Python, JavaScript) and expand to others (Java, C/C++, Go, etc.) in later phases.

### Performance Optimization
- Use lazy loading for repository content
- Process only changed files
- Implement caching for function boundary detection
- Consider parallel processing for large repositories

### Error Handling
- Implement robust error handling at module boundaries
- Gracefully degrade when specific language parsing fails
- Provide helpful error messages for troubleshooting

## 7. Milestones and Timeline

| Milestone                                    | Timeline   | Key Deliverables                                      |
|----------------------------------------------|------------|-------------------------------------------------------|
| Project Setup & Git Change Processing        | Week 1-2   | Repository handler, commit retrieval, file diff extraction |
| Function Boundary Detection                  | Week 3-4   | Tree-sitter integration, function detection for initial languages |
| Function-Level Change Identification         | Week 5-6   | Change mapping, function diffs, change classification |
| Integration, Optimization, and Documentation | Week 7-8   | Complete tool, documentation, additional languages    | 