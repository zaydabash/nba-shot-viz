#!/usr/bin/env python3
"""
Helper script to update the preview screenshot in README.md.
Automatically copies the most recent PNG from outputs/figures/ to screenshot.png
and commits the change.
"""

import os
import shutil
import subprocess
import glob
from pathlib import Path

def get_most_recent_png():
    """Get the most recently modified PNG file in outputs/figures/"""
    png_files = glob.glob("outputs/figures/*.png")
    if not png_files:
        raise FileNotFoundError("No PNG files found in outputs/figures/")
    
    # Sort by modification time (most recent first)
    most_recent = max(png_files, key=os.path.getmtime)
    return most_recent

def copy_to_screenshot(source_path):
    """Copy the source PNG to screenshot.png"""
    dest_path = "outputs/figures/screenshot.png"
    shutil.copy2(source_path, dest_path)
    return dest_path

def git_commit(file_path):
    """Commit the screenshot change"""
    try:
        # Add the file
        subprocess.run(["git", "add", file_path], check=True)
        
        # Commit with a descriptive message
        commit_msg = f"Update preview screenshot from {os.path.basename(file_path)}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        
        print(f"✅ Committed: {commit_msg}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Git commit failed: {e}")
        return False
    except FileNotFoundError:
        print("❌ Git not found. Please commit manually.")
        return False

def main():
    """Main function to update preview screenshot"""
    try:
        # Ensure we're in the project root
        if not os.path.exists("outputs/figures"):
            print("❌ outputs/figures/ directory not found. Run from project root.")
            return
        
        # Get the most recent PNG
        source_png = get_most_recent_png()
        print(f"📸 Most recent PNG: {source_png}")
        
        # Copy to screenshot.png
        dest_path = copy_to_screenshot(source_png)
        print(f"📋 Copied to: {dest_path}")
        
        # Commit the change
        if git_commit(dest_path):
            print("🎉 Preview screenshot updated and committed!")
        else:
            print("⚠️  Screenshot updated but commit failed. Please commit manually.")
            
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
