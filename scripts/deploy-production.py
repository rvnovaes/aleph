#!/usr/bin/env python3
"""Run production playbooks without putting registry tokens in argv or files."""
import argparse
import json
import os
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument("operation", choices=["prepare", "publish", "stage", "restore", "deploy"])
parser.add_argument("--backup", type=Path)
parser.add_argument("--ref", default="main")
args = parser.parse_args()
playbooks = root / "deploy/ansible"
command = ["ansible-playbook", "-i", str(playbooks / "inventory.ini")]
env = os.environ.copy()
if args.operation == "prepare":
    command += [str(playbooks / "provision.yml")]
elif args.operation == "publish":
    command += [str(playbooks / "publish.yml"), "-e", json.dumps({"release_ref": args.ref})]
else:
    private = root / "deploy/.private/production.json"
    if not private.exists():
        parser.error("Missing deploy/.private/production.json (see deploy/README.md)")
    if private.stat().st_mode & 0o077:
        parser.error("Production variables must have mode 0600")
    command += ["-e", "@" + str(private)]
    if args.operation == "restore":
        if not args.backup:
            parser.error("--backup is required for restore")
        command += [str(playbooks / "restore.yml"), "-e", json.dumps({"backup_dir": str(args.backup.resolve())})]
    else:
        token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
        env["ALEPH_GH_TOKEN"] = token
        command += [str(playbooks / "deploy.yml"), "-e", json.dumps({"activate": args.operation == "deploy"})]
subprocess.run(command, cwd=root, env=env, check=True)
