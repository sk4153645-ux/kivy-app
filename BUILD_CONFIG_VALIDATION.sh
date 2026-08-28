#!/bin/bash

#####################################################
# Nilgiri Dairy App - Build Configuration Validator
# This script validates all build prerequisites
#####################################################

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Build Configuration Validation${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

ERRORS=0
WARNINGS=0

# ============== CHECK PYTHON ==============
echo -e "${BLUE}[1] Python Environment${NC}"
if command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo -e "${GREEN}✓${NC} Python 3 found: $PY_VERSION"
else
    echo -e "${RED}✗${NC} Python 3 not found!"
    ERRORS=$((ERRORS+1))
fi

# ============== CHECK JAVA ==============
echo ""
echo -e "${BLUE}[2] Java Environment${NC}"
if command -v java &> /dev/null; then
    JAVA_VERSION=$(java -version 2>&1 | head -1)
    echo -e "${GREEN}✓${NC} Java found: $JAVA_VERSION"
else
    echo -e "${RED}✗${NC} Java not found!"
    ERRORS=$((ERRORS+1))
fi

# ============== CHECK BUILDOZER ==============
echo ""
echo -e "${BLUE}[3] Buildozer${NC}"
if command -v buildozer &> /dev/null; then
    BUILDOZER_VERSION=$(buildozer --version 2>&1)
    echo -e "${GREEN}✓${NC} Buildozer found: $BUILDOZER_VERSION"
else
    echo -e "${RED}✗${NC} Buildozer not installed!"
    echo "   Install with: pip install buildozer"
    ERRORS=$((ERRORS+1))
fi

# ============== CHECK CYTHON ==============
echo ""
echo -e "${BLUE}[4] Cython${NC}"
if python3 -c "import Cython; print(Cython.__version__)" &> /dev/null; then
    CYTHON_VERSION=$(python3 -c "import Cython; print(Cython.__version__)")
    echo -e "${GREEN}✓${NC} Cython found: $CYTHON_VERSION"
else
    echo -e "${RED}✗${NC} Cython not installed!"
    echo "   Install with: pip install Cython"
    ERRORS=$((ERRORS+1))
fi

# ============== CHECK BUILDOZER.SPEC ==============
echo ""
echo -e "${BLUE}[5] buildozer.spec Configuration${NC}"
if [ ! -f "buildozer.spec" ]; then
    echo -e "${RED}✗${NC} buildozer.spec not found!"
    ERRORS=$((ERRORS+1))
else
    echo -e "${GREEN}✓${NC} buildozer.spec found"
    
    # Check key configurations
    if grep -q "package.name" buildozer.spec; then
        PKG_NAME=$(grep "^package.name" buildozer.spec | cut -d'=' -f2 | xargs)
        echo -e "${GREEN}  ✓${NC} package.name: $PKG_NAME"
    else
        echo -e "${RED}  ✗${NC} package.name not defined"
        ERRORS=$((ERRORS+1))
    fi
    
    if grep -q "package.domain" buildozer.spec; then
        PKG_DOMAIN=$(grep "^package.domain" buildozer.spec | cut -d'=' -f2 | xargs)
        echo -e "${GREEN}  ✓${NC} package.domain: $PKG_DOMAIN"
    else
        echo -e "${RED}  ✗${NC} package.domain not defined"
        ERRORS=$((ERRORS+1))
    fi
    
    if grep -q "android.api" buildozer.spec; then
        ANDROID_API=$(grep "^android.api" buildozer.spec | cut -d'=' -f2 | xargs)
        echo -e "${GREEN}  ✓${NC} android.api: $ANDROID_API"
    else
        echo -e "${YELLOW}  ⚠${NC} android.api not explicitly defined"
        WARNINGS=$((WARNINGS+1))
    fi
    
    if grep -q "android.minapi" buildozer.spec; then
        ANDROID_MINAPI=$(grep "^android.minapi" buildozer.spec | cut -d'=' -f2 | xargs)
        echo -e "${GREEN}  ✓${NC} android.minapi: $ANDROID_MINAPI"
    else
        echo -e "${YELLOW}  ⚠${NC} android.minapi not explicitly defined"
        WARNINGS=$((WARNINGS+1))
    fi
    
    if grep -q "android.ndk" buildozer.spec; then
        ANDROID_NDK=$(grep "^android.ndk" buildozer.spec | cut -d'=' -f2 | xargs)
        echo -e "${GREEN}  ✓${NC} android.ndk: $ANDROID_NDK"
    else
        echo -e "${YELLOW}  ⚠${NC} android.ndk not explicitly defined"
        WARNINGS=$((WARNINGS+1))
    fi
fi

# ============== CHECK REQUIREMENTS.TXT ==============
echo ""
echo -e "${BLUE}[6] requirements.txt${NC}"
if [ ! -f "requirements.txt" ]; then
    echo -e "${YELLOW}⚠${NC} requirements.txt not found (optional but recommended)"
    WARNINGS=$((WARNINGS+1))
else
    echo -e "${GREEN}✓${NC} requirements.txt found"
    echo "   Contents:"
    while IFS= read -r line; do
        if [ ! -z "$line" ] && [ "${line:0:1}" != "#" ]; then
            echo "   - $line"
        fi
    done < requirements.txt
fi

# ============== CHECK MAIN.PY ==============
echo ""
echo -e "${BLUE}[7] main.py${NC}"
if [ ! -f "main.py" ]; then
    echo -e "${RED}✗${NC} main.py not found!"
    ERRORS=$((ERRORS+1))
else
    echo -e "${GREEN}✓${NC} main.py found"
    
    # Check for syntax errors
    if python3 -m py_compile main.py 2>/dev/null; then
        echo -e "${GREEN}  ✓${NC} No Python syntax errors"
    else
        echo -e "${RED}  ✗${NC} Python syntax errors found!"
        python3 -m py_compile main.py
        ERRORS=$((ERRORS+1))
    fi
fi

# ============== CHECK DISK SPACE ==============
echo ""
echo -e "${BLUE}[8] Disk Space${NC}"
AVAILABLE=$(df -h . | awk 'NR==2 {print $4}')
echo -e "${GREEN}✓${NC} Available disk space: $AVAILABLE"

# ============== CHECK ANDROID SDK/NDK ==============
echo ""
echo -e "${BLUE}[9] Android SDK/NDK (if installed locally)${NC}"
if [ -d "$ANDROID_SDK_ROOT" ]; then
    echo -e "${GREEN}✓${NC} ANDROID_SDK_ROOT: $ANDROID_SDK_ROOT"
else
    echo -e "${YELLOW}ℹ${NC} ANDROID_SDK_ROOT not set (Buildozer will download)"
fi

if [ -d "$ANDROID_NDK_ROOT" ]; then
    echo -e "${GREEN}✓${NC} ANDROID_NDK_ROOT: $ANDROID_NDK_ROOT"
else
    echo -e "${YELLOW}ℹ${NC} ANDROID_NDK_ROOT not set (Buildozer will download)"
fi

# ============== SUMMARY ==============
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Validation Summary${NC}"
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}✓ Passed: $(($(echo $ERRORS | wc -w) - ERRORS))${NC}"
if [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}⚠ Warnings: $WARNINGS${NC}"
fi
if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}✗ Errors: $ERRORS${NC}"
    echo ""
    echo -e "${RED}Build cannot proceed with errors. Please fix them above.${NC}"
    exit 1
else
    echo ""
    echo -e "${GREEN}✅ All checks passed! Ready to build.${NC}"
    exit 0
fi
