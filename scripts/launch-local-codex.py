#!/usr/bin/env python3
"""Launch the official local UI using native Codex auth, without copied tokens."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import webbrowser


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment.update(
        OPENJARVIS_HOME=str(Path.home() / ".local/share/openjarvis-official-trial"),
        OPENAI_CODEX_USE_LOCAL_AUTH="1",
        OPENAI_CODEX_BASE_URL="https://chatgpt.com/backend-api/codex",
        CUDA_VISIBLE_DEVICES="",
    )
    # This launcher explicitly selects the local Codex account flow.
    environment.pop("OPENAI_CODEX_API_KEY", None)
    url = "http://127.0.0.1:8001"

    def ready():
        try:
            with urllib.request.urlopen(url + "/v1/info", timeout=2) as response:
                info = json.load(response)
            return info.get("model") == "codex/gpt-6.1-sol" and info.get("agent") == "simple"
        except Exception:
            return False

    if not ready():
        result = subprocess.run(
            [sys.executable, "-m", "openjarvis.cli", "start", "--host", "127.0.0.1",
             "--port", "8001", "--engine", "cloud", "--model", "codex/gpt-6.1-sol",
             "--agent", "simple"],
            cwd=root, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=30,
        )
        if result.returncode:
            print("OpenJarvis could not start; check the existing local server before retrying.")
            return 1
        deadline = time.monotonic() + 90
        while not ready():
            if time.monotonic() >= deadline:
                print("OpenJarvis did not become ready within 90 seconds.")
                return 1
            time.sleep(1)
    webbrowser.open(url)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("OpenJarvis launch failed. No credentials were printed.")
        raise SystemExit(1) from None
