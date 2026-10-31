#!/usr/bin/env python3
"""Select a successful CI release and store its immutable digests locally."""
import argparse
import json
import re
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("commit", help="Full 40-character commit SHA")
args = parser.parse_args()
if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
    parser.error("Use a full Git commit SHA")
root = Path(__file__).resolve().parent.parent
runs = json.loads(subprocess.check_output([
    "gh", "run", "list", "--workflow", "images.yml", "--commit", args.commit,
    "--json", "conclusion", "--limit", "20",
], cwd=root))
if not any(run["conclusion"] == "success" for run in runs):
    parser.error("This commit has no successful Production images workflow")
path = root / "deploy/.private/production.json"
data = json.loads(path.read_text())
for component in ["backend", "web"]:
    output = subprocess.check_output([
        "gh", "api", f"/user/packages/container/aleph-{component}/versions",
        "--paginate",
    ], text=True)
    pages = []
    decoder = json.JSONDecoder()
    while output.strip():
        page, end = decoder.raw_decode(output.lstrip())
        pages.append(page)
        output = output.lstrip()[end:]
    versions = [version for page in pages for version in page]
    selected = next((v for v in versions if args.commit in v["metadata"]["container"]["tags"]), None)
    if not selected:
        parser.error(f"No {component} image for this commit")
    data[component + "_image"] = f"ghcr.io/rvnovaes/aleph-{component}@" + selected["name"]
data["release_commit"] = args.commit
path.write_text(json.dumps(data, indent=2))
path.chmod(0o600)
print("Pinned backend and web to successful release " + args.commit)
