"""Shows the README roughly as GitHub will: renders it with GitHub's Markdown API, points the images at the local
files, and screenshots the page with a headless browser into the version's folder (scripts/viz.py), for example
.local/visualization/viz_v1/readme_preview.png; the page itself goes to .local/visualization/work/.

Usage: python3 scripts/preview_readme.py [version, default v1]
"""

import json
import re
import subprocess
import sys
from pathlib import Path

from viz import WORK, folder

ROOT = Path(__file__).resolve().parents[1]
CSS = "https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.5.1/github-markdown-light.min.css"


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    body = json.dumps({"text": (ROOT / "README.md").read_text(encoding="utf-8"), "mode": "gfm"})
    html = subprocess.run(["gh", "api", "markdown", "--input", "-"], input=body, capture_output=True, text=True, check=True).stdout
    html = re.sub(r'(src|href)="(?!https?:|#|mailto:)([^"]+)"', lambda m: f'{m[1]}="file://{ROOT / m[2]}"', html)
    page = WORK / "readme_preview.html"
    page.write_text(
        f'<html><head><meta charset="utf-8"><link rel="stylesheet" href="{CSS}"><style>body{{margin:0;background:#fff}}'
        f".markdown-body{{box-sizing:border-box;max-width:980px;margin:0 auto;padding:45px}}</style></head>"
        f'<body><article class="markdown-body">{html}</article></body></html>',
        encoding="utf-8",
    )
    shot = folder(sys.argv[1] if len(sys.argv) > 1 else "v1") / "readme_preview.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["brave-browser", "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
         "--virtual-time-budget=8000", "--window-size=1000,9000", f"--screenshot={shot}", f"file://{page}"],
        capture_output=True, check=True,
    )
    print(shot)


if __name__ == "__main__":
    main()
