import os
import re
from github import Github
from pathlib import Path

def get_file_description(file_path):
    """Extract description from Python files."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Try to find module docstring
        module_doc = re.search('"""(.*?)"""', content, re.DOTALL)
        if module_doc:
            return module_doc.group(1).strip()
            
        # Try to find first function/class docstring
        first_doc = re.search('def.*?:.*?"""(.*?)"""', content, re.DOTALL) or \
                   re.search('class.*?:.*?"""(.*?)"""', content, re.DOTALL)
        if first_doc:
            return first_doc.group(1).strip()
            
        # Get first comment block if no docstrings found
        comments = re.findall('#\s*(.*?)\n', content)
        if comments:
            return ' '.join(comments[:3])  # First 3 comment lines
            
        return "No description available"
    except Exception as e:
        return f"Error reading file: {str(e)}"

def create_or_update_docs():
    """Create or update documentation for changed files."""
    # Create docs directory if it doesn't exist
    docs_dir = Path('docs')
    docs_dir.mkdir(exist_ok=True)
    
    # Get repository information from environment
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    token = os.environ.get('DOCS_BOT_TOKEN', '')
    
    if token and repo:
        g = Github(token)
        repo = g.get_repo(repo)
        
        # Get the latest commit
        commit = repo.get_commits()[0]
        changed_files = commit.files
        
        # Update main README if it doesn't exist
        main_readme = docs_dir / 'README.md'
        if not main_readme.exists():
            with open(main_readme, 'w', encoding='utf-8') as f:
                f.write(f"# {repo.name}\n\n")
                f.write(f"{repo.description or ''}\n\n")
                f.write("## Project Documentation\n\n")
                f.write("This documentation is automatically generated from the project files.\n\n")
        
        # Process each changed file
        for file in changed_files:
            file_path = Path(file.filename)
            
            # Only process Python files
            if file_path.suffix != '.py':
                continue
                
            # Create documentation file path
            doc_path = docs_dir / f"{file_path.stem}.md"
            
            # Get file description
            description = get_file_description(file_path)
            
            # Create or update documentation
            with open(doc_path, 'w', encoding='utf-8') as f:
                f.write(f"# {file_path.stem}\n\n")
                f.write(f"File: `{file_path}`\n\n")
                f.write("## Description\n\n")
                f.write(f"{description}\n\n")
                f.write("## Last Updated\n\n")
                f.write(f"Last modified in commit: {commit.sha[:7]}\n")
                f.write(f"Author: {commit.commit.author.name}\n")
                f.write(f"Date: {commit.commit.author.date}\n")
    else:
        # Local development mode - process all Python files
        for file_path in Path().rglob('*.py'):
            if 'venv' not in str(file_path):  # Skip virtual environment
                doc_path = docs_dir / f"{file_path.stem}.md"
                description = get_file_description(file_path)
                
                with open(doc_path, 'w', encoding='utf-8') as f:
                    f.write(f"# {file_path.stem}\n\n")
                    f.write(f"File: `{file_path}`\n\n")
                    f.write("## Description\n\n")
                    f.write(f"{description}\n\n")

if __name__ == '__main__':
    create_or_update_docs()
