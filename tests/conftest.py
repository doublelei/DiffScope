import pytest
import os

def pytest_configure(config):
    """Configure pytest."""
    # Register custom markers
    config.addinivalue_line(
        "markers", "live_api: mark test as using live GitHub API (may be subject to rate limits)"
    )

def pytest_addoption(parser):
    """Add command-line options to pytest."""
    parser.addoption(
        "--run-live-api",
        action="store_true",
        default=False,
        help="Run tests that hit the live GitHub API",
    )

def pytest_collection_modifyitems(config, items):
    """Modify test collection based on command-line options."""
    if config.getoption("--run-live-api"):
        # Check for GitHub token when running live API tests
        if not os.environ.get('GITHUB_TOKEN'):
            print("\nWARNING: Running live API tests without GITHUB_TOKEN environment variable.")
            print("You may encounter rate limiting issues with the GitHub API.")
            print("Set the GITHUB_TOKEN environment variable with a valid GitHub personal access token.")
            print("For example: export GITHUB_TOKEN=your_token_here (bash) or $env:GITHUB_TOKEN=\"your_token_here\" (PowerShell)\n")
        # --run-live-api given in cli: do not skip live_api tests
        return
    
    skip_live_api = pytest.mark.skip(reason="need --run-live-api option to run")
    for item in items:
        if "live_api" in item.keywords:
            item.add_marker(skip_live_api)

@pytest.fixture
def print_commit_result():
    """
    Fixture to print detailed information about a CommitAnalysisResult.
    
    Usage in tests:
        def test_something(print_commit_result):
            result = analyze_commit(url)
            print_commit_result(result)
    """
    def _print_commit_result(result):
        print("\n" + "="*80)
        print(f"COMMIT ANALYSIS RESULT")
        print("="*80)
        print(f"Commit SHA:     {result.commit_sha}")
        print(f"Repository:     {result.repository_url}")
        print(f"Author:         {result.commit_author}")
        print(f"Date:           {result.commit_date}")
        print(f"Commit Message: {result.commit_message[:60]}..." if len(result.commit_message or '') > 60 
              else result.commit_message)
        
        print("\nMODIFIED FILES:")
        print("-"*80)
        for i, file in enumerate(result.modified_files, 1):
            print(f"{i}. {file.filename}")
            print(f"   Status: {file.status}, Language: {file.language or 'Unknown'}")
            print(f"   Changes: +{file.additions} -{file.deletions} ({file.changes} total)")
            if hasattr(file, 'patch') and file.patch:
                patch_preview = file.patch[:100] + "..." if len(file.patch) > 100 else file.patch
                print(f"   Patch Preview: {patch_preview}")
            print()
        
        if result.modified_functions:
            print("\nMODIFIED FUNCTIONS:")
            print("-"*80)
            for i, func in enumerate(result.modified_functions, 1):
                print(f"{i}. {func.name} in {func.file}")
                print(f"   Type: {func.type}, Changes: {func.changes}")
                print()
                
        print("="*80 + "\n")
        
    return _print_commit_result 