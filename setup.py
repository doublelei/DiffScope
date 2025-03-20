from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="diffscope",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A tool for analyzing function-level changes in Git commits",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/DiffScope",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.25.0",
        "pydantic>=2.0.0",
        "PyGithub>=2.1.1",
    ],
    entry_points={
        "console_scripts": [
            "diffscope=diffscope.main:app",
        ],
    },
)
