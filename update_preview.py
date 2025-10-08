#!/usr/bin/env python3
"""
Helper script to update the preview screenshot in README.md.
Automatically copies the most recent PNG from outputs/figures/ to screenshot.png,
commits the change, and pushes to GitHub.
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

def git_commit_and_push(file_path):
    """Commit the screenshot change and push to GitHub"""
    try:
        # Add the file
        subprocess.run(["git", "add", file_path], check=True)
        
        # Commit with the specified message
        commit_msg = "Update preview image"
        result = subprocess.run(["git", "commit", "-m", commit_msg], 
                              check=True, capture_output=True, text=True)
        
        # Extract commit hash from the output
        commit_hash = result.stdout.strip().split()[-1]
        
        # Push to GitHub
        subprocess.run(["git", "push"], check=True)
        
        return commit_hash
    except subprocess.CalledProcessError as e:
        print(f"❌ Git operation failed: {e}")
        return None
    except FileNotFoundError:
        print("❌ Git not found. Please commit and push manually.")
        return None

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
        
        # Commit and push
        commit_hash = git_commit_and_push(dest_path)
        if commit_hash:
            print(f"✅ Committed: {dest_path}")
            print(f"🔗 Commit hash: {commit_hash}")
            print("🚀 Pushed to GitHub successfully!")
        else:
            print("⚠️  Screenshot updated but commit/push failed. Please handle manually.")
            
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()