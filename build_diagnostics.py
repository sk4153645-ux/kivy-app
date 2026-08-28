#!/usr/bin/env python3
"""
Nilgiri Dairy App - Build Diagnostics and Error Analyzer
Extracts, analyzes, and reports exact build failures
"""

import os
import re
import json
import sys
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime
from dataclasses import dataclass

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    END = '\033[0m'

@dataclass
class BuildError:
    """Represents a build error"""
    error_type: str
    location: str
    message: str
    line_number: int = 0
    severity: str = "ERROR"
    solution: str = ""

class BuildDiagnostics:
    """Analyzes build logs and extracts errors with solutions"""
    
    # Error patterns and their solutions
    ERROR_PATTERNS = {
        r"(?i)gradle build failed": {
            "type": "Gradle Build Error",
            "solutions": [
                "Clear Gradle cache: rm -rf ~/.gradle/caches",
                "Clear buildozer cache: buildozer android clean",
                "Check gradle version compatibility in buildozer.spec"
            ]
        },
        r"(?i)jdk not found|java_home": {
            "type": "JDK Not Found",
            "solutions": [
                "Install JDK: sudo apt-get install openjdk-17-jdk",
                "Set JAVA_HOME: export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64",
                "Verify: java -version"
            ]
        },
        r"(?i)ndk not found|download.*ndk": {
            "type": "NDK Download Failed",
            "solutions": [
                "Ensure 30GB+ free disk space: df -h",
                "Check internet connection",
                "Clear NDK cache: rm -rf ~/.buildozer",
                "Verify NDK version in buildozer.spec matches available versions"
            ]
        },
        r"(?i)requirement.*not found|no module|importerror": {
            "type": "Python Dependency Error",
            "solutions": [
                "Verify requirements.txt contains all dependencies",
                "Check buildozer.spec requirements line",
                "Install missing package: pip install <package-name>",
                "Test locally: python3 -c 'import <module>'"
            ]
        },
        r"(?i)permission denied": {
            "type": "Permission Error",
            "solutions": [
                "Check file permissions: ls -la",
                "Make executable: chmod +x build_validator.py",
                "Run with proper permissions"
            ]
        },
        r"(?i)out of (space|memory)": {
            "type": "Disk/Memory Error",
            "solutions": [
                "Check disk space: df -h",
                "Clear caches: buildozer android cleanall",
                "Remove old builds: rm -rf bin .buildozer",
                "Consider removing large files"
            ]
        },
        r"(?i)timeout|timed out": {
            "type": "Build Timeout",
            "solutions": [
                "Increase timeout in GitHub Actions workflow",
                "Build locally for faster debugging",
                "Check internet connection stability",
                "Clear all caches and retry"
            ]
        },
        r"(?i)compilation failed": {
            "type": "Compilation Error",
            "solutions": [
                "Check main.py for syntax errors: python3 -m py_compile main.py",
                "Verify all imports are in requirements",
                "Check for incompatible Python versions",
                "Review full build.log for details"
            ]
        },
        r"(?i)certificate|ssl|https": {
            "type": "SSL Certificate Error",
            "solutions": [
                "Update certificates: pip install --upgrade certifi",
                "On macOS: /Applications/Python\\ 3.x/Install\\ Certificates.command",
                "Check internet connection"
            ]
        },
        r"(?i)invalid.*manifest|androidmanifest": {
            "type": "Android Manifest Error",
            "solutions": [
                "Verify buildozer.spec permissions",
                "Check android.permissions configuration",
                "Validate package name format",
                "Review android.features compatibility"
            ]
        }
    }

    def __init__(self, build_log_path: str = "build.log"):
        self.log_path = Path(build_log_path)
        self.errors: List[BuildError] = []
        self.warnings: List[BuildError] = []
        self.log_content = ""
        
    def read_build_log(self) -> bool:
        """Read build log file"""
        if not self.log_path.exists():
            print(f"{Colors.RED}✗{Colors.END} Build log not found: {self.log_path}")
            return False
        
        self.log_content = self.log_path.read_text()
        print(f"{Colors.GREEN}✓{Colors.END} Build log loaded: {len(self.log_content)} bytes")
        return True

    def find_buildozer_logs(self) -> List[Path]:
        """Find all buildozer log files"""
        logs = []
        buildozer_dir = Path(".buildozer")
        
        if buildozer_dir.exists():
            logs.extend(buildozer_dir.glob("**/*.log"))
        
        return logs

    def extract_errors(self):
        """Extract errors from logs using pattern matching"""
        print(f"\n{Colors.BLUE}🔍 Extracting errors...{Colors.END}")
        
        lines = self.log_content.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Check for ERROR patterns
            if any(keyword in line.upper() for keyword in ['ERROR', 'FAILED', 'EXCEPTION', 'FATAL']):
                self.errors.append(BuildError(
                    error_type="Detected Error",
                    location=f"build.log:{i}",
                    message=line.strip(),
                    line_number=i,
                    severity="ERROR"
                ))
            
            # Check for WARNING patterns
            elif 'WARNING' in line.upper():
                self.warnings.append(BuildError(
                    error_type="Warning",
                    location=f"build.log:{i}",
                    message=line.strip(),
                    line_number=i,
                    severity="WARNING"
                ))

    def categorize_errors(self):
        """Categorize errors and provide solutions"""
        print(f"{Colors.BLUE}📊 Categorizing errors...{Colors.END}")
        
        categorized = []
        
        for error in self.errors:
            found = False
            for pattern, info in self.ERROR_PATTERNS.items():
                if re.search(pattern, error.message):
                    error.error_type = info["type"]
                    error.solution = "\n  ".join(info["solutions"])
                    found = True
                    break
            
            categorized.append(error)
        
        self.errors = categorized

    def search_gradle_logs(self):
        """Search gradle build logs for errors"""
        print(f"{Colors.BLUE}🔧 Searching gradle logs...{Colors.END}")
        
        gradle_build_paths = [
            ".buildozer/android/platform/build/build/outputs/logs/",
            ".buildozer/android/platform/build-*/build/",
        ]
        
        for pattern in gradle_build_paths:
            for log_file in Path(".").glob(pattern + "**/*.log"):
                content = log_file.read_text()
                if 'error' in content.lower() or 'failed' in content.lower():
                    print(f"  Found gradle log: {log_file}")
                    
                    # Extract relevant error lines
                    for i, line in enumerate(content.split('\n')):
                        if any(k in line.upper() for k in ['ERROR', 'FAILED', 'EXCEPTION']):
                            self.errors.append(BuildError(
                                error_type="Gradle Error",
                                location=str(log_file),
                                message=line.strip(),
                                line_number=i + 1
                            ))

    def generate_report(self) -> Dict:
        """Generate comprehensive diagnostics report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "build_log_path": str(self.log_path),
            "log_size_bytes": len(self.log_content),
            "total_errors": len(self.errors),
            "total_warnings": len(self.warnings),
            "errors": [
                {
                    "type": e.error_type,
                    "location": e.location,
                    "message": e.message,
                    "line": e.line_number,
                    "severity": e.severity,
                    "solution": e.solution
                }
                for e in self.errors
            ],
            "warnings": [
                {
                    "type": w.error_type,
                    "message": w.message,
                    "location": w.location
                }
                for w in self.warnings
            ]
        }
        
        return report

    def print_report(self, report: Dict):
        """Print human-readable report"""
        print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
        print(f"{Colors.BLUE}Build Diagnostics Report{Colors.END}")
        print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")
        
        print(f"📋 Summary:")
        print(f"  Build Log: {report['build_log_path']}")
        print(f"  Size: {report['log_size_bytes']} bytes")
        print(f"  Total Errors: {Colors.RED}{report['total_errors']}{Colors.END}")
        print(f"  Total Warnings: {Colors.YELLOW}{report['total_warnings']}{Colors.END}\n")
        
        if report['errors']:
            print(f"{Colors.RED}❌ ERRORS FOUND:{Colors.END}\n")
            for i, error in enumerate(report['errors'], 1):
                print(f"{Colors.BOLD}{i}. {error['type']}{Colors.END}")
                print(f"   Location: {error['location']}")
                print(f"   Message: {error['message']}\n")
                
                if error['solution']:
                    print(f"{Colors.GREEN}   💡 Solutions:{Colors.END}")
                    for solution in error['solution'].split('\n'):
                        print(f"      • {solution}")
                    print()
        
        if report['warnings']:
            print(f"\n{Colors.YELLOW}⚠️  WARNINGS:{Colors.END}\n")
            for warning in report['warnings']:
                print(f"  • {warning['message']}")

    def save_report(self, report: Dict, output_path: str = "build_diagnostics.json"):
        """Save report to JSON file"""
        output = Path(output_path)
        output.write_text(json.dumps(report, indent=2))
        print(f"\n📄 Detailed report saved to: {Colors.CYAN}{output_path}{Colors.END}")

    def run(self) -> Dict:
        """Run full diagnostics"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}Starting Build Diagnostics...{Colors.END}\n")
        
        if not self.read_build_log():
            return {"error": "No build log found"}
        
        self.extract_errors()
        self.categorize_errors()
        self.search_gradle_logs()
        
        report = self.generate_report()
        self.print_report(report)
        self.save_report(report)
        
        return report

def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        log_path = sys.argv[1]
    else:
        log_path = "build.log"
    
    diagnostics = BuildDiagnostics(log_path)
    report = diagnostics.run()
    
    # Exit with error code if errors found
    sys.exit(1 if report.get("total_errors", 0) > 0 else 0)

if __name__ == "__main__":
    main()
