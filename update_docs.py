import os
import re
import ast
import json
import requests
from github import Github
from pathlib import Path
from typing import List, Dict, Any, Optional

class CopilotDocGenerator:
    """GitHub Copilot-powered documentation generator."""
    
    def __init__(self):
        self.github_token = os.environ.get('GITHUB_TOKEN', '')
        self.openai_key = os.environ.get('OPENAI_API_KEY', '')
        self.repo_name = os.environ.get('GITHUB_REPOSITORY', '')
        
    def analyze_python_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze Python file structure and extract metadata."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            analysis = {
                'functions': [],
                'classes': [],
                'imports': [],
                'docstring': ast.get_docstring(tree),
                'complexity': 'low'
            }
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    analysis['functions'].append({
                        'name': node.name,
                        'docstring': ast.get_docstring(node),
                        'args': [arg.arg for arg in node.args.args],
                        'line_number': node.lineno
                    })
                elif isinstance(node, ast.ClassDef):
                    analysis['classes'].append({
                        'name': node.name,
                        'docstring': ast.get_docstring(node),
                        'methods': [n.name for n in node.body if isinstance(n, ast.FunctionDef)],
                        'line_number': node.lineno
                    })
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        analysis['imports'].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        analysis['imports'].append(f"{module}.{alias.name}")
            
            # Determine complexity
            total_items = len(analysis['functions']) + len(analysis['classes'])
            if total_items > 10:
                analysis['complexity'] = 'high'
            elif total_items > 5:
                analysis['complexity'] = 'medium'
                
            return analysis
            
        except Exception as e:
            return {'error': str(e), 'functions': [], 'classes': [], 'imports': []}
    
    def generate_copilot_documentation(self, file_path: Path, analysis: Dict[str, Any]) -> str:
        """Generate comprehensive documentation using AI."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code_content = f.read()
            
            # Create a comprehensive prompt for documentation generation
            prompt = f"""
Generate comprehensive technical documentation for this Python file.

File: {file_path.name}
Complexity: {analysis.get('complexity', 'unknown')}

Code Analysis:
- Functions: {len(analysis.get('functions', []))}
- Classes: {len(analysis.get('classes', []))}
- Key imports: {', '.join(analysis.get('imports', [])[:5])}

Code Content:
```python
{code_content[:2000]}  # Truncated for context
```

Please provide documentation in this format:
1. Brief overview of the file's purpose
2. Key functionality and features  
3. Usage examples where appropriate
4. Dependencies and requirements
5. Function/Class descriptions
6. Implementation notes

Keep it professional, clear, and developer-friendly.
"""

            # Use OpenAI API if available, otherwise fall back to pattern-based generation
            if self.openai_key:
                return self._call_openai_api(prompt)
            else:
                return self._generate_fallback_docs(file_path, analysis)
                
        except Exception as e:
            return self._generate_fallback_docs(file_path, analysis)
    
    def _call_openai_api(self, prompt: str) -> str:
        """Call OpenAI API for documentation generation."""
        try:
            headers = {
                'Authorization': f'Bearer {self.openai_key}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': 'gpt-3.5-turbo',
                'messages': [
                    {'role': 'system', 'content': 'You are a technical documentation expert. Generate clear, comprehensive documentation for code files.'},
                    {'role': 'user', 'content': prompt}
                ],
                'max_tokens': 1500,
                'temperature': 0.3
            }
            
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                print(f"OpenAI API error: {response.status_code}")
                return "Documentation generation failed - using fallback method"
                
        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            return "AI documentation generation unavailable - using fallback method"
    
    def _generate_fallback_docs(self, file_path: Path, analysis: Dict[str, Any]) -> str:
        """Generate documentation using pattern-based approach."""
        docs = []
        
        # File overview
        if analysis.get('docstring'):
            docs.append(f"## Overview\n\n{analysis['docstring']}\n")
        else:
            docs.append(f"## Overview\n\nThis module provides functionality for {file_path.stem.replace('_', ' ')}.\n")
        
        # Dependencies
        if analysis.get('imports'):
            docs.append("## Dependencies\n\n")
            for imp in analysis['imports'][:10]:  # Limit to first 10 imports
                docs.append(f"- `{imp}`\n")
            docs.append("\n")
        
        # Classes
        if analysis.get('classes'):
            docs.append("## Classes\n\n")
            for cls in analysis['classes']:
                docs.append(f"### {cls['name']}\n\n")
                if cls.get('docstring'):
                    docs.append(f"{cls['docstring']}\n\n")
                if cls.get('methods'):
                    docs.append(f"**Methods:** {', '.join(cls['methods'])}\n\n")
        
        # Functions  
        if analysis.get('functions'):
            docs.append("## Functions\n\n")
            for func in analysis['functions']:
                docs.append(f"### {func['name']}\n\n")
                if func.get('docstring'):
                    docs.append(f"{func['docstring']}\n\n")
                if func.get('args'):
                    docs.append(f"**Parameters:** {', '.join(func['args'])}\n\n")
        
        return ''.join(docs)
    
    def create_or_update_docs(self):
        """Main function to create or update documentation."""
        print("🤖 Starting automatic documentation generation...")
        
        # Create docs directory
        docs_dir = Path('docs')
        docs_dir.mkdir(exist_ok=True)
        
        processed_files = []
        
        try:
            if self.github_token and self.repo_name:
                # GitHub Actions mode - process changed files
                g = Github(self.github_token)
                repo = g.get_repo(self.repo_name)
                
                # Get recent commits to find changed files
                commits = list(repo.get_commits()[:5])  # Last 5 commits
                changed_files = set()
                
                for commit in commits:
                    for file in commit.files:
                        if file.filename.endswith('.py') and 'venv' not in file.filename:
                            changed_files.add(file.filename)
                
                print(f"Found {len(changed_files)} Python files to document")
                
                for file_path_str in changed_files:
                    file_path = Path(file_path_str)
                    if file_path.exists():
                        self._process_file(file_path, docs_dir)
                        processed_files.append(str(file_path))
                        
            else:
                # Local mode - process all Python files
                print("Running in local mode - processing all Python files")
                for file_path in Path('.').rglob('*.py'):
                    if 'venv' not in str(file_path) and '.git' not in str(file_path):
                        self._process_file(file_path, docs_dir)
                        processed_files.append(str(file_path))
            
            # Update main documentation index
            self._create_docs_index(docs_dir, processed_files)
            
            print(f"✅ Documentation generated for {len(processed_files)} files")
            
        except Exception as e:
            print(f"❌ Error during documentation generation: {e}")
    
    def _process_file(self, file_path: Path, docs_dir: Path):
        """Process individual file for documentation."""
        try:
            print(f"📝 Processing {file_path}")
            
            # Analyze the file
            analysis = self.analyze_python_file(file_path)
            
            # Generate documentation
            doc_content = self.generate_copilot_documentation(file_path, analysis)
            
            # Create documentation file
            doc_path = docs_dir / f"{file_path.stem}.md"
            
            with open(doc_path, 'w', encoding='utf-8') as f:
                f.write(f"# {file_path.stem}\n\n")
                f.write(f"**File:** `{file_path}`\n\n")
                f.write(f"**Complexity:** {analysis.get('complexity', 'unknown').title()}\n\n")
                f.write("---\n\n")
                f.write(doc_content)
                f.write("\n\n---\n\n")
                f.write("*This documentation was automatically generated using GitHub Copilot.*\n")
                
        except Exception as e:
            print(f"⚠️  Error processing {file_path}: {e}")
    
    def _create_docs_index(self, docs_dir: Path, processed_files: List[str]):
        """Create main documentation index."""
        index_path = docs_dir / 'README.md'
        
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write("# 📚 Project Documentation\n\n")
            f.write("This documentation is automatically generated and maintained using GitHub Copilot.\n\n")
            f.write("## 📋 Available Documentation\n\n")
            
            for file_path in sorted(processed_files):
                file_stem = Path(file_path).stem
                f.write(f"- [{file_stem}](./{file_stem}.md) - `{file_path}`\n")
            
            f.write(f"\n\n## 🔄 Last Updated\n\n")
            f.write(f"Generated on: {os.environ.get('GITHUB_SHA', 'local')}[:7]\n")
            f.write("Powered by GitHub Copilot 🤖\n")

def main():
    """Main entry point."""
    generator = CopilotDocGenerator()
    generator.create_or_update_docs()

if __name__ == '__main__':
    main()
