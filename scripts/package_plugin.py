#!/usr/bin/env python3
"""Create and verify a native npm/DSH tarball without lifecycle scripts or network."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = re.compile(r"^(?:package\.json|README\.md|THIRD_PARTY_NOTICES\.md|requirements-acceptance\.txt|LICENSE|cordis\.patch\.yml|src/[^/]+\.js|runtime/[^/]+\.py|research_bridge/(?:[^/]+/)*[^/]+\.py|scenarios/(?:[^/]+/)*[^/]+\.(?:py|R|json|md)|skills/[^/]+/SKILL\.md|tests/[^/]+\.(?:mjs|py)|tests/fixtures/[^/]+\.(?:xsd|json)|scripts/[^/]+\.(?:mjs|py|ps1)|docs/(?:[^/]+/)*[^/]+\.(?:md|json|py))$")

def verify_tarball(tarball):
    members = []
    with tarfile.open(tarball, "r:gz") as archive:
        for item in archive.getmembers():
            name = PurePosixPath(item.name)
            if not item.isfile() or name.is_absolute() or ".." in name.parts or not name.parts or name.parts[0] != "package":
                raise ValueError("Unexpected archive member: " + item.name)
            relative = "/".join(name.parts[1:])
            if not ALLOWED.fullmatch(relative) or "__pycache__" in name.parts:
                raise ValueError("File outside package allowlist: " + relative)
            members.append(relative)
        def read(name):
            handle = archive.extractfile("package/" + name)
            if handle is None:
                raise ValueError("Missing archive member: " + name)
            return handle.read()
        manifest = json.loads(read("package.json"))
        if manifest.get("dsh", {}).get("manifestVersion") != 1:
            raise ValueError("Missing native DSH manifestVersion 1")
        if manifest.get("dsh", {}).get("bundle", {}).get("patch") != "./cordis.patch.yml":
            raise ValueError("Invalid DSH bundle patch declaration")
        if manifest.get("main") != "./src/index.js":
            raise ValueError("Invalid plugin entry")
        required = {"README.md", "LICENSE", "cordis.patch.yml", "src/index.js", "runtime/cli.py", "research_bridge/core.py", "research_bridge/catalog.py", "research_bridge/verify.py", "skills/research-toolkit/SKILL.md", "skills/research-bridge-lab/SKILL.md", "docs/bridge-research-guide.md", "tests/dsh-host.test.mjs", "scripts/install.ps1"}
        missing = required - set(members)
        if missing:
            raise ValueError("Missing files: " + ", ".join(sorted(missing)))
        for source in (ROOT / "research_bridge").rglob("*.py"):
            if source.relative_to(ROOT).as_posix() not in members:
                raise ValueError("Missing Python module in tarball: " + str(source))
    return manifest, sorted(members)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--npm", default=shutil.which("npm.cmd") or shutil.which("npm"))
    parser.add_argument("--node", default=shutil.which("node"))
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--cache", default=str(ROOT.parent / "npm-cache"))
    args = parser.parse_args()
    if not args.npm or not args.node:
        raise ValueError("npm and Node are required; provide --npm and --node with their absolute paths")
    npm_path = Path(args.npm).resolve()
    npm_candidates = [npm_path] if npm_path.suffix == ".js" else [npm_path.parent / "node_modules/npm/bin/npm-cli.js", npm_path.parent / "npm/bin/npm-cli.js"]
    npm_cli = next((candidate for candidate in npm_candidates if candidate.is_file()), None)
    if npm_cli is None:
        raise ValueError("Cannot locate npm-cli.js; provide --npm with its absolute path")
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    expected = output / (manifest["name"].replace("@", "").replace("/", "-") + "-" + manifest["version"] + ".tgz")
    if expected.exists() and not args.overwrite:
        raise FileExistsError("Refusing to replace existing tarball: " + str(expected))
    command = [args.node, str(npm_cli), "pack", "--json", "--offline", "--ignore-scripts", "--no-audit", "--no-fund", "--update-notifier=false", "--cache", str(Path(args.cache).resolve()), "--pack-destination", str(output)]
    # Invoke npm's JavaScript through Node directly: .cmd would introduce shell
    # parsing of user-selected output paths on Windows.
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=120)
    if completed.returncode:
        raise RuntimeError("npm pack failed: " + completed.stderr.strip())
    packed = json.loads(completed.stdout)
    if len(packed) != 1 or packed[0].get("filename") != expected.name:
        raise ValueError("Unexpected npm pack result")
    package, members = verify_tarball(expected)
    report = dict(status="passed", package=package["name"], version=package["version"],
                  format="npm-tgz-with-native-dsh-bundle", path=str(expected),
                  bytes=expected.stat().st_size, sha256=hashlib.sha256(expected.read_bytes()).hexdigest(),
                  file_count=len(members), files=members, lifecycle_scripts=False, network=False,
                  dsh_activation="not_performed")
    report_path = output / "package-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(dict(report, report_path=str(report_path)), ensure_ascii=False))
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps(dict(status="failed", reason=str(error)), ensure_ascii=False))
        raise SystemExit(1)
