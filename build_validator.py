#!/usr/bin/env python3
"""
Nilgiri Dairy App - Build Configuration Validator
Pure Python implementation for build validation and diagnostics
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Dict
from datetime import datetime

# Color codes for terminal output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    END = '\033[0m'

@dataclass
class ValidationResult:
    """Store validation result"""
    name: str
    passed: bool
    message: str
    severity: str = "error"  # error, warning, info

class BuildValidator:
    """Validates build environment and configuration"""
    
    def __init__(self):
        self.results: List[ValidationResult] = []
        self.start_time = datetime.now()
        
    def run_command(self, cmd: str) -> Tuple[bool, str, str]:
        """Run a shell command and return success, stdout, stderr"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "", "Command timed out"
        except Exception as e:
            return False, "", str(e)

    def check_python(self):
        """Check Python installation"""
        print(f"\n{Colors.BLUE}[1] Python Environment{Colors.END}")
        success, stdout, stderr = self.run_command("python3 --version")
        
        if success:
            print(f"{Colors.GREEN}✓{Colors.END} Python 3 found: {stdout}")
            self.results.append(ValidationResult("Python 3", True, stdout))
        else:
            print(f"{Colors.RED}✗{Colors.END} Python 3 not found!")
            self.results.append(ValidationResult("Python 3", False, "Not installed", "error"))

    def check_java(self):
        """Check Java installation"""
        print(f"\n{Colors.BLUE}[2] Java Environment{Colors.END}")
        success, stdout, stderr = self.run_command("java -version")
        
        if success or stderr:  # java -version outputs to stderr
            version = stdout or stderr
            print(f"{Colors.GREEN}✓{Colors.END} Java found: {version.split(chr(10))[0]}")
            self.results.append(ValidationResult("Java", True, version.split('\n')[0]))
        else:
            print(f"{Colors.RED}✗{Colors.END} Java not found!")
            print("   Install: sudo apt-get install openjdk-17-jdk")
            self.results.append(ValidationResult("Java", False, "Not installed", "error"))

    def check_buildozer(self):
        """Check Buildozer installation"""
        print(f"\n{Colors.BLUE}[3] Buildozer{Colors.END}")
        success, stdout, stderr = self.run_command("buildozer --version")
        
        if success:
            print(f"{Colors.GREEN}✓{Colors.END} Buildozer found: {stdout}")
            self.results.append(ValidationResult("Buildozer", True, stdout))
        else:
            print(f"{Colors.RED}✗{Colors.END} Buildozer not installed!")
            print("   Install: pip install buildozer==1.5.0")
            self.results.append(ValidationResult("Buildozer", False, "Not installed", "error"))

    def check_cython(self):
        """Check Cython installation"""
        print(f"\n{Colors.BLUE}[4] Cython{Colors.END}")
        success, stdout, stderr = self.run_command("python3 -c 'import Cython; print(Cython.__version__)'")
        
        if success:
            print(f"{Colors.GREEN}✓{Colors.END} Cython found: {stdout}")
            self.results.append(ValidationResult("Cython", True, stdout))
        else:
            print(f"{Colors.RED}✗{Colors.END} Cython not installed!")
            print("   Install: pip install Cython==0.29.36")
            self.results.append(ValidationResult("Cython", False, "Not installed", "error"))

    def check_buildozer_spec(self):
        """Validate buildozer.spec configuration"""
        print(f"\n{Colors.BLUE}[5] buildozer.spec Configuration{Colors.END}")
        
        spec_path = Path("buildozer.spec")
        if not spec_path.exists():
            print(f"{Colors.RED}✗{Colors.END} buildozer.spec not found!")
            self.results.append(ValidationResult("buildozer.spec", False, "File not found", "error"))
            return
        
        print(f"{Colors.GREEN}✓{Colors.END} buildozer.spec found")
        
        # Read and parse buildozer.spec
        spec_content = spec_path.read_text()
        config = {}
        current_section = None
        
        for line in spec_content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('['):
                current_section = line.strip('[]')
            elif '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
        
        # Check required fields
        required_fields = {
            'package.name': 'Package name',
            'package.domain': 'Package domain',
            'android.api': 'Android API',
            'android.minapi': 'Android min API',
            'android.ndk': 'Android NDK version'
        }
        
        for field, label in required_fields.items():
            if field in config:
                print(f"{Colors.GREEN}  ✓{Colors.END} {label}: {config[field]}")
                self.results.append(ValidationResult(f"buildozer.spec - {label}", True, config[field]))
            else:
                print(f"{Colors.YELLOW}  ⚠{Colors.END} {label} not defined")
                self.results.append(ValidationResult(f"buildozer.spec - {label}", False, "Not defined", "warning"))

    def check_requirements_txt(self):
        """Check requirements.txt"""
        print(f"\n{Colors.BLUE}[6] requirements.txt{Colors.END}")
        
        req_path = Path("requirements.txt")
        if not req_path.exists():
            print(f"{Colors.YELLOW}⚠{Colors.END} requirements.txt not found (optional but recommended)")
            self.results.append(ValidationResult("requirements.txt", False, "Not found", "warning"))
            return
        
        print(f"{Colors.GREEN}✓{Colors.END} requirements.txt found")
        content = req_path.read_text()
        lines = [l.strip() for l in content.split('\n') if l.strip() and not l.startswith('#')]
        
        print("   Contents:")
        for line in lines:
            print(f"   - {line}")
        
        self.results.append(ValidationResult("requirements.txt", True, f"{len(lines)} packages"))

    def check_main_py(self):
        """Check main.py"""
        print(f"\n{Colors.BLUE}[7] main.py{Colors.END}")
        
        main_path = Path("main.py")
        if not main_path.exists():
            print(f"{Colors.RED}✗{Colors.END} main.py not found!")
            self.results.append(ValidationResult("main.py", False, "File not found", "error"))
            return
        
        print(f"{Colors.GREEN}✓{Colors.END} main.py found")
        
        # Check for syntax errors
        success, stdout, stderr = self.run_command("python3 -m py_compile main.py")
        if success:
            print(f"{Colors.GREEN}  ✓{Colors.END} No Python syntax errors")
            self.results.append(ValidationResult("main.py - Syntax", True, "Valid"))
        else:
            print(f"{Colors.RED}  ✗{Colors.END} Python syntax errors found!")
            print(f"   {stderr}")
            self.results.append(ValidationResult("main.py - Syntax", False, stderr, "error"))

    def check_disk_space(self):
        """Check available disk space"""
        print(f"\n{Colors.BLUE}[8] Disk Space{Colors.END}")
        
        success, stdout, stderr = self.run_command("df -h . | awk 'NR==2 {print $4}'")
        if success:
            print(f"{Colors.GREEN}✓{Colors.END} Available disk space: {stdout}")
            self.results.append(ValidationResult("Disk Space", True, stdout))
        else:
            print(f"{Colors.YELLOW}⚠{Colors.END} Could not determine disk space")
            self.results.append(ValidationResult("Disk Space", False, "Unknown", "warning"))

    def check_git(self):
        """Check Git installation"""
        print(f"\n{Colors.BLUE}[9] Git{Colors.END}")
        
        success, stdout, stderr = self.run_command("git --version")
        if success:
            print(f"{Colors.GREEN}✓{Colors.END} Git found: {stdout}")
            self.results.append(ValidationResult("Git", True, stdout))
        else:
            print(f"{Colors.YELLOW}⚠{Colors.END} Git not found (optional)")
            self.results.append(ValidationResult("Git", False, "Not installed", "warning"))

    def print_summary(self):
        """Print validation summary"""
        print(f"\n{Colors.BLUE}{'='*50}{Colors.END}")
        print(f"{Colors.BLUE}Validation Summary{Colors.END}")
        print(f"{Colors.BLUE}{'='*50}{Colors.END}\n")
        
        errors = [r for r in self.results if not r.passed and r.severity == "error"]
        warnings = [r for r in self.results if not r.passed and r.severity == "warning"]
        passed = [r for r in self.results if r.passed]
        
        if passed:
            print(f"{Colors.GREEN}✓ Passed: {len(passed)}{Colors.END}")
        if warnings:
            print(f"{Colors.YELLOW}⚠ Warnings: {len(warnings)}{Colors.END}")
        if errors:
            print(f"{Colors.RED}✗ Errors: {len(errors)}{Colors.END}\n")
            print(f"{Colors.RED}Build cannot proceed with errors. Please fix them above.{Colors.END}")
            return False
        else:
            print(f"\n{Colors.GREEN}✅ All checks passed! Ready to build.{Colors.END}")
            return True

    def generate_report(self):
        """Generate JSON report"""
        report = {
            "timestamp": self.start_time.isoformat(),
            "total_checks": len(self.results),
            "passed": sum(1 for r in self.results if r.passed),
            "errors": sum(1 for r in self.results if not r.passed and r.severity == "error"),
            "warnings": sum(1 for r in self.results if not r.passed and r.severity == "warning"),
            "results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "message": r.message,
                    "severity": r.severity
                }
                for r in self.results
            ]
        }
        
        report_path = Path("validation_report.json")
        report_path.write_text(json.dumps(report, indent=2))
        print(f"\n📄 Report saved to: {report_path}")
        
        return report

    def run(self) -> bool:
        """Run all validation checks"""
        print(f"\n{Colors.BLUE}{'='*50}{Colors.END}")
        print(f"{Colors.BLUE}Build Configuration Validation{Colors.END}")
        print(f"{Colors.BLUE}{'='*50}{Colors.END}")
        
        self.check_python()
        self.check_java()
        self.check_buildozer()
        self.check_cython()
        self.check_buildozer_spec()
        self.check_requirements_txt()
        self.check_main_py()
        self.check_disk_space()
        self.check_git()
        
        success = self.print_summary()
        self.generate_report()
        
        return success

def main():
    """Main entry point"""
    validator = BuildValidator()
    success = validator.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
