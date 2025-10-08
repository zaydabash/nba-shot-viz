import shutil
import subprocess
import sys
from pathlib import Path

PNG_DIR = Path("outputs/figures")
PREVIEW = PNG_DIR / "screenshot.png"


def newest_png():
    files = [p for p in PNG_DIR.glob("*.png") if p.name != "screenshot.png"]
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def main(msg: str = "Update preview image"):
    PNG_DIR.mkdir(parents=True, exist_ok=True)
    src = newest_png()
    if not src:
        print("No PNGs found in outputs/figures to use as preview.")
        sys.exit(1)

    # Copy newest chart to the preview path
    shutil.copy2(src, PREVIEW)

    # Force-add even if outputs/* is gitignored
    subprocess.run(["git", "add", "-f", str(PREVIEW)], check=True)
    subprocess.run(["git", "commit", "-m", msg], check=True)

    # Try a normal push first
    try:
        subprocess.run(["git", "push"], check=True)
    except subprocess.CalledProcessError:
        print(
            "Normal push failed. If you're in Cursor without saved creds, run:\n"
            "export GITHUB_TOKEN='<YOUR_PAT>' && "
            "git push https://${GITHUB_TOKEN}@github.com/zaydabash/nba-shot-viz.git HEAD:main && "
            "unset GITHUB_TOKEN"
        )
        raise

    print(f"Preview updated -> {PREVIEW} (from {src.name})")


if __name__ == "__main__":
    commit_msg = "Update preview image"
    if len(sys.argv) > 1:
        commit_msg = " ".join(sys.argv[1:])
    main(commit_msg)