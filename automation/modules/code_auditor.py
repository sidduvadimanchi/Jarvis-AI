# Backend/Automation/code_auditor.py
# Jarvis AI — Proactive Code Quality Auditor
# ─────────────────────────────────────────────────────────────────────────────
# This module performs static analysis on the project to find common bugs.
# ─────────────────────────────────────────────────────────────────────────────

import ast
import os
import sys
from pathlib import Path

def audit_file(filepath: str) -> list[str]:
    """Analyze a single python file for static errors."""
    issues = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=filepath)
        
        defined_names = set(sys.builtin_module_names) | {'__name__', '__file__', '__doc__', '__path__', '__package__', '__loader__', '__spec__', '__annotations__'}
        used_names = set()

        for node in ast.walk(tree):
            # Track imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    defined_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    defined_names.add(alias.asname or alias.name)
            
            # Track function/class definitions
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined_names.add(node.name)
            
            # Track variable assignments
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined_names.add(target.id)
            
            # Track usage
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Load):
                    used_names.add(node.id)

        # Check for used but not defined (simple heuristic)
        # Note: This is a basic check and won't catch everything (e.g. globals across files)
        # but it will catch obvious local NameErrors like the one in terminal.py earlier.
        undef = used_names - defined_names
        for name in undef:
            # Skip common false positives if any
            if name in ('print', 'range', 'len', 'enumerate', 'dict', 'list', 'set', 'str', 'int', 'float', 'bool', 'Exception', 'type', 'getattr', 'setattr', 'hasattr', 'repr', 'open', 'sum', 'min', 'max', 'any', 'all', 'input', 'super'):
                continue
            issues.append(f"Undefined name '{name}' at top level")

    except SyntaxError as e:
        issues.append(f"Syntax Error: {e}")
    except Exception as e:
        issues.append(f"Audit Error: {e}")
    
    return issues

def AuditCodebase(root_dir: str = ".") -> dict[str, list[str]]:
    """Scan all .py files in the root_dir."""
    results = {}
    for root, _, files in os.walk(root_dir):
        if ".venv" in root or "__pycache__" in root or ".git" in root:
            continue
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                issues = audit_file(path)
                if issues:
                    results[path] = issues
    return results

def FindBugs() -> str:
    """Entry point for AutomationEngine."""
    print("  [Auditor] Scanning codebase for bugs...")
    results = AuditCodebase()
    
    if not results:
        return "Clean code! No obvious bugs found in the current modules."
    
    report = "I found some potential issues in the code:\n"
    for path, issues in results.items():
        rel_path = os.path.relpath(path)
        report += f"  • {rel_path}: {', '.join(issues)}\n"
    
    report += "\nShould I attempt to fix these for you, sir?"
    return report

if __name__ == "__main__":
    # Test on current directory
    print(FindBugs())
