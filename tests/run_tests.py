#!/usr/bin/env python
"""
Helper script to run DiffScope tests with appropriate configurations.

Usage:
  python run_tests.py [options]

Options:
  --all                 Run all tests including GitHub API tests
  --unit                Run only unit tests (no GitHub API tests)
  --integration         Run integration tests (requires GitHub token)
  --file=<path>         Run tests from a specific file
  --token=<token>       GitHub token to use for API tests
  --verbose, -v         Verbose output
  --print-output, -s    Show print statements (don't capture stdout/stderr)
  --help, -h            Show this help message
"""

import os
import sys
import subprocess
import argparse

def main():
    parser = argparse.ArgumentParser(description='Run DiffScope tests')
    parser.add_argument('--all', action='store_true', help='Run all tests including GitHub API tests')
    parser.add_argument('--unit', action='store_true', help='Run only unit tests (no GitHub API tests)')
    parser.add_argument('--integration', action='store_true', help='Run integration tests (requires GitHub token)')
    parser.add_argument('--file', type=str, help='Run tests from a specific file')
    parser.add_argument('--token', type=str, help='GitHub token to use for API tests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--print-output', '-s', action='store_true', help='Show print statements (don\'t capture stdout/stderr)')
    
    args = parser.parse_args()
    
    # Set GitHub token if provided
    if args.token:
        os.environ['GITHUB_TOKEN'] = args.token
        print(f"Using provided GitHub token")
    elif 'GITHUB_TOKEN' in os.environ:
        print(f"Using GITHUB_TOKEN from environment")
    elif args.all or args.integration:
        print("WARNING: No GitHub token provided. You may encounter rate limits.")
        print("Consider setting --token or the GITHUB_TOKEN environment variable.")
    
    # Build pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Test target
    if args.file:
        cmd.append(args.file)
    elif args.unit:
        cmd.append("tests/unit/")
    elif args.integration:
        cmd.append("tests/integration/")
    else:
        cmd.append("tests/")
    
    # Add flags
    if args.verbose or args.integration or args.all:
        cmd.append("-v")
    
    if args.print_output:
        cmd.append("-s")
    
    if args.all or args.integration:
        cmd.append("--run-live-api")
    
    # Print command
    print(f"Running: {' '.join(cmd)}")
    
    # Execute command
    result = subprocess.run(cmd)
    return result.returncode

if __name__ == "__main__":
    sys.exit(main()) 