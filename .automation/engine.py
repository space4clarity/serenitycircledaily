"""Shared local runtime helpers for checked, unattended publication."""

from __future__ import annotations

import contextlib

from html.parser import HTMLParser

import json

import os

from pathlib import Path

import re

import shutil

import subprocess

import sys

ROOT = Path(__file__).resolve().parent.parent

AUTO = ROOT / ".automation"

def normalize(text):
    return re.sub(r"\s+", " ", text).strip()

def read_json(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)

def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, encoding="utf-8", capture_output=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result.stdout.rstrip("\r\n")

def codex_json(prompt, schema, destination):
    codex = shutil.which("codex")
    if not codex:
        raise RuntimeError("Codex CLI is not on PATH")
    # Run the Node entry point directly on Windows, avoiding cmd.exe quoting rules.
    node_entry = Path(codex).parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
    command = [shutil.which("node"), str(node_entry)] if os.name == "nt" and node_entry.exists() else [codex]
    command += ["exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only",
                "--disable", "shell_tool", "--disable", "unified_exec", "--disable", "apps",
                "--disable", "plugins", "--disable", "browser_use", "--disable", "computer_use",
                "--disable", "image_generation", "--disable", "memories", "--disable", "code_mode_host",
                "-c", 'web_search="disabled"', "--color", "never", "--output-schema", str(AUTO / schema), "--output-last-message", str(destination), "-"]
    # The model receives source text via stdin. It never handles Git credentials or publishing.
    result = subprocess.run(command, input=prompt, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=600)
    destination.with_suffix(".log").write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    if result.returncode or not destination.exists():
        raise RuntimeError(f"Codex generation failed (exit {result.returncode}); see {destination.with_suffix('.log')}")
    return read_json(destination)

class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ("href", "src") and value:
                self.links.append(value)

def check_site():
    checked = 0
    for path in ROOT.rglob("*.html"):
        if ".git" in path.parts or ".automation" in path.parts:
            continue
        parser = LinkCollector()
        parser.feed(path.read_text(encoding="utf-8"))
        for link in parser.links:
            if re.match(r"^[a-z]+:|^//|^#", link, re.I):
                continue
            relative = link.split("#")[0].split("?")[0]
            target = ROOT / relative.lstrip("/") if relative.startswith("/") else path.parent / relative
            if not target.exists():
                raise ValueError(f"Broken local link: {path.relative_to(ROOT)} -> {link}")
        checked += 1
    print(f"Checked {checked} HTML pages: no broken local links", flush=True)

@contextlib.contextmanager
def run_lock():
    # An OS-held lock is released automatically after a crash; a leftover file is harmless.
    lock = (AUTO / "run.lock").open("a+b")
    lock.seek(0)
    if os.name == "nt":
        import msvcrt
        lock.write(b"0")
        lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            lock.close()
            raise RuntimeError("Another daily run is already active")
    else:
        import fcntl
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        yield
    finally:
        lock.close()
