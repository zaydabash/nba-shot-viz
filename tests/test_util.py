"""Tests for utility functions."""
import pytest
from pathlib import Path
from src.util import (
    ensure_dirs,
    csv_path_for,
    html_path_for,
    file_age_minutes,
    is_stale
)


def test_ensure_dirs():
    """Test directory creation."""
    test_dir = "test_output/test_dir"
    ensure_dirs(test_dir)
    assert Path(test_dir).exists()
    Path(test_dir).rmdir()
    Path("test_output").rmdir() if Path("test_output").exists() else None


def test_csv_path_for():
    """Test CSV path generation."""
    path = csv_path_for("Stephen Curry", "2023-24", "Regular Season")
    assert "stephen-curry" in path
    assert "2023-24" in path
    assert "regular-season" in path
    assert path.endswith(".csv")


def test_html_path_for():
    """Test HTML path generation."""
    path = html_path_for("Stephen Curry", "2023-24", "Regular Season", "fg_pct")
    assert "stephen-curry" in path
    assert "2023-24" in path
    assert "regular-season" in path
    assert "fg_pct" in path
    assert path.endswith(".html")


def test_file_age_minutes_nonexistent():
    """Test file age for non-existent file."""
    age = file_age_minutes("nonexistent_file.csv")
    assert age is None


def test_is_stale_nonexistent():
    """Test staleness check for non-existent file."""
    assert is_stale("nonexistent_file.csv") is True

