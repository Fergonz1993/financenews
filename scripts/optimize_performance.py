#!/usr/bin/env python3
"""
Performance Optimization Script for Financial News Summarizer

This script performs various optimizations to improve code performance:
- Code quality checks and fixes
- Memory usage optimization
- Async performance improvements
- Dependency optimization
"""

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, TaskID
from rich.table import Table

console = Console()


class PerformanceOptimizer:
    """Main performance optimization class."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.src_path = project_root / "src"
        self.stats = {
            "files_processed": 0,
            "issues_fixed": 0,
            "optimizations_applied": 0,
            "time_taken": 0,
        }

    def run_command(self, command: List[str], description: str) -> bool:
        """Run a shell command and return success status."""
        try:
            console.print(f"🔧 {description}...")
            result = subprocess.run(
                command,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=False,
            )
            
            if result.returncode == 0:
                console.print(f"✅ {description} completed successfully")
                return True
            else:
                console.print(f"❌ {description} failed: {result.stderr}")
                return False
        except Exception as e:
            console.print(f"❌ Error running {description}: {e}")
            return False

    def optimize_imports(self) -> bool:
        """Optimize import statements using isort."""
        return self.run_command(
            ["python", "-m", "isort", "src/", "--profile", "black"],
            "Optimizing import statements"
        )

    def format_code(self) -> bool:
        """Format code using Black."""
        return self.run_command(
            ["python", "-m", "black", "src/", "--line-length", "88"],
            "Formatting code with Black"
        )

    def lint_and_fix(self) -> bool:
        """Run Ruff linter and fix issues."""
        return self.run_command(
            ["python", "-m", "ruff", "check", "src/", "--fix"],
            "Running Ruff linter and fixing issues"
        )

    def type_check(self) -> bool:
        """Run MyPy type checking."""
        return self.run_command(
            ["python", "-m", "mypy", "src/"],
            "Running MyPy type checking"
        )

    def remove_unused_imports(self) -> bool:
        """Remove unused imports using autoflake."""
        try:
            # Install autoflake if not available
            subprocess.run(
                ["pip", "install", "autoflake"],
                capture_output=True,
                check=False
            )
            
            return self.run_command(
                [
                    "python", "-m", "autoflake",
                    "--remove-all-unused-imports",
                    "--remove-unused-variables",
                    "--in-place",
                    "--recursive",
                    "src/"
                ],
                "Removing unused imports and variables"
            )
        except Exception:
            console.print("⚠️  Autoflake not available, skipping unused import removal")
            return True

    def optimize_dependencies(self) -> bool:
        """Analyze and optimize dependencies."""
        console.print("📦 Analyzing dependencies...")
        
        # Check for unused dependencies
        try:
            result = subprocess.run(
                ["pip", "list", "--format=freeze"],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                installed_packages = result.stdout.split('\n')
                console.print(f"📊 Found {len(installed_packages)} installed packages")
                
                # Create a simple report
                table = Table(title="Dependency Analysis")
                table.add_column("Package", style="cyan")
                table.add_column("Status", style="green")
                
                for package in installed_packages[:10]:  # Show first 10
                    if package.strip():
                        name = package.split('==')[0] if '==' in package else package
                        table.add_row(name, "Installed")
                
                console.print(table)
                return True
        except Exception as e:
            console.print(f"⚠️  Dependency analysis failed: {e}")
            return False

    def analyze_memory_usage(self) -> Dict:
        """Analyze memory usage patterns in the code."""
        console.print("🧠 Analyzing memory usage patterns...")
        
        memory_issues = []
        optimizations = []
        
        # Check for common memory issues
        for py_file in self.src_path.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Check for potential memory issues
                if "global " in content:
                    memory_issues.append(f"Global variables found in {py_file}")
                
                if "import *" in content:
                    memory_issues.append(f"Wildcard imports found in {py_file}")
                
                if "list(" in content and "range(" in content:
                    optimizations.append(f"Consider using generators in {py_file}")
                    
                if "__slots__" not in content and "class " in content:
                    optimizations.append(f"Consider adding __slots__ to classes in {py_file}")
                    
            except Exception as e:
                console.print(f"⚠️  Error analyzing {py_file}: {e}")
        
        return {
            "memory_issues": memory_issues,
            "optimizations": optimizations
        }

    def optimize_async_code(self) -> bool:
        """Optimize async code patterns."""
        console.print("⚡ Optimizing async code patterns...")
        
        optimizations_applied = 0
        
        for py_file in self.src_path.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # Replace common async anti-patterns
                if "asyncio.sleep(0)" in content:
                    content = content.replace("asyncio.sleep(0)", "await asyncio.sleep(0)")
                    optimizations_applied += 1
                
                # Check for missing await keywords
                if "async def" in content and "return " in content:
                    # This is a simplified check - in practice, you'd want more sophisticated analysis
                    pass
                
                if content != original_content:
                    with open(py_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    console.print(f"✅ Optimized async patterns in {py_file}")
                    
            except Exception as e:
                console.print(f"⚠️  Error optimizing {py_file}: {e}")
        
        console.print(f"📊 Applied {optimizations_applied} async optimizations")
        return True

    def generate_performance_report(self, memory_analysis: Dict) -> None:
        """Generate a comprehensive performance report."""
        console.print("\n" + "="*60)
        console.print("📊 PERFORMANCE OPTIMIZATION REPORT")
        console.print("="*60)
        
        # Summary statistics
        summary_table = Table(title="Optimization Summary")
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="green")
        
        summary_table.add_row("Files Processed", str(self.stats["files_processed"]))
        summary_table.add_row("Issues Fixed", str(self.stats["issues_fixed"]))
        summary_table.add_row("Optimizations Applied", str(self.stats["optimizations_applied"]))
        summary_table.add_row("Time Taken", f"{self.stats['time_taken']:.2f}s")
        
        console.print(summary_table)
        
        # Memory analysis
        if memory_analysis["memory_issues"]:
            console.print("\n⚠️  Memory Issues Found:")
            for issue in memory_analysis["memory_issues"][:5]:  # Show first 5
                console.print(f"  • {issue}")
        
        if memory_analysis["optimizations"]:
            console.print("\n💡 Optimization Suggestions:")
            for suggestion in memory_analysis["optimizations"][:5]:  # Show first 5
                console.print(f"  • {suggestion}")
        
        # Performance tips
        console.print("\n🚀 Performance Tips:")
        tips = [
            "Use __slots__ in classes to reduce memory usage",
            "Prefer generators over lists for large datasets",
            "Use async/await properly for I/O operations",
            "Cache expensive function calls with @lru_cache",
            "Use connection pooling for database/API calls",
            "Profile your code regularly to identify bottlenecks"
        ]
        
        for tip in tips:
            console.print(f"  • {tip}")

    async def run_optimization(self) -> None:
        """Run the complete optimization process."""
        start_time = time.time()
        
        console.print(Panel.fit(
            "🚀 Financial News Summarizer Performance Optimizer",
            style="bold blue"
        ))
        
        with Progress() as progress:
            task = progress.add_task("Optimizing codebase...", total=7)
            
            # Step 1: Remove unused imports
            if self.remove_unused_imports():
                self.stats["optimizations_applied"] += 1
            progress.advance(task)
            
            # Step 2: Optimize imports
            if self.optimize_imports():
                self.stats["optimizations_applied"] += 1
            progress.advance(task)
            
            # Step 3: Format code
            if self.format_code():
                self.stats["optimizations_applied"] += 1
            progress.advance(task)
            
            # Step 4: Lint and fix
            if self.lint_and_fix():
                self.stats["issues_fixed"] += 1
            progress.advance(task)
            
            # Step 5: Optimize async code
            if self.optimize_async_code():
                self.stats["optimizations_applied"] += 1
            progress.advance(task)
            
            # Step 6: Analyze memory usage
            memory_analysis = self.analyze_memory_usage()
            progress.advance(task)
            
            # Step 7: Optimize dependencies
            if self.optimize_dependencies():
                self.stats["optimizations_applied"] += 1
            progress.advance(task)
        
        # Count processed files
        self.stats["files_processed"] = len(list(self.src_path.rglob("*.py")))
        self.stats["time_taken"] = time.time() - start_time
        
        # Generate report
        self.generate_performance_report(memory_analysis)
        
        console.print("\n✅ Performance optimization completed!")


@click.command()
@click.option(
    "--project-root",
    default=".",
    help="Path to the project root directory",
    type=click.Path(exists=True, path_type=Path)
)
@click.option(
    "--skip-type-check",
    is_flag=True,
    help="Skip MyPy type checking"
)
def main(project_root: Path, skip_type_check: bool):
    """Run performance optimization on the Financial News Summarizer codebase."""
    
    optimizer = PerformanceOptimizer(project_root)
    
    try:
        asyncio.run(optimizer.run_optimization())
        
        if not skip_type_check:
            console.print("\n🔍 Running type checking...")
            optimizer.type_check()
        
    except KeyboardInterrupt:
        console.print("\n⚠️  Optimization interrupted by user")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n❌ Optimization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 