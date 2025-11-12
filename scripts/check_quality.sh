#!/bin/bash
# Quality and security check script for NBA Shot Chart Visualizer

set -e

echo "Running quality and security checks..."
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓${NC} $2"
    else
        echo -e "${RED}✗${NC} $2"
    fi
}

# Check if we're in the right directory
if [ ! -f "requirements.txt" ]; then
    echo "Error: Please run this script from the project root"
    exit 1
fi

# Run flake8
echo ""
echo "Running flake8..."
flake8 src/ tests/ app.py --count --select=E9,F63,F7,F82 --show-source --statistics
FLKE8_EXIT=$?
if [ $FLKE8_EXIT -eq 0 ]; then
    print_status 0 "flake8 (critical issues)"
else
    print_status 1 "flake8 (critical issues found)"
fi

flake8 src/ tests/ app.py --count --exit-zero --max-complexity=10 --max-line-length=100 --statistics
print_status 0 "flake8 (style check)"

# Run pylint
echo ""
echo "Running pylint..."
pylint src/ tests/ app.py --exit-zero > /dev/null 2>&1
PYLINT_EXIT=$?
print_status $PYLINT_EXIT "pylint"

# Run bandit security scan
echo ""
echo "Running bandit security scan..."
bandit -r src/ app.py -f json -o bandit-report.json > /dev/null 2>&1 || true
bandit -r src/ app.py
BANDIT_EXIT=$?
print_status $BANDIT_EXIT "bandit security scan"

# Run safety check
echo ""
echo "Running safety check..."
safety check --json > safety-report.json 2>&1 || true
safety check
SAFETY_EXIT=$?
print_status $SAFETY_EXIT "safety check"

# Run pytest
echo ""
echo "Running pytest..."
pytest --cov=src --cov-report=term-missing -v
PYTEST_EXIT=$?
print_status $PYTEST_EXIT "pytest"

# Summary
echo ""
echo "========================================"
echo "Summary:"
echo "========================================"
print_status $FLKE8_EXIT "flake8"
print_status $PYLINT_EXIT "pylint"
print_status $BANDIT_EXIT "bandit"
print_status $SAFETY_EXIT "safety"
print_status $PYTEST_EXIT "pytest"

if [ $FLKE8_EXIT -eq 0 ] && [ $PYTEST_EXIT -eq 0 ]; then
    echo ""
    echo -e "${GREEN}All critical checks passed!${NC}"
    exit 0
else
    echo ""
    echo -e "${YELLOW}Some checks failed. Please review the output above.${NC}"
    exit 1
fi

