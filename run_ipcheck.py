import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from http.client import HTTPException
from importlib.metadata import version
from urllib.parse import quote
from urllib.request import Request, urlopen

from packaging.version import Version


REPOSITORY = "devicu-awsl/ipcheck"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASE_VERSION = version("ai-ipcheck")
VERSION_FLAGS = {"--version", "-v", "-V"}
APPLY_UPDATE = """
$ErrorActionPreference = 'Stop'
$stage = $env:IPCHECK_UPDATE_STAGE
$target = $env:IPCHECK_UPDATE_TARGET
$backup = Join-Path $stage 'previous.exe'
$next = Join-Path $stage 'next.exe'
try {
    $launcher = Get-Process -Id $env:IPCHECK_UPDATE_LAUNCHER -ErrorAction SilentlyContinue
    if ($launcher) { $launcher | Wait-Process -Timeout 30 }
    $lock = [IO.FileStream]::new(
        "$target.update.lock", 'OpenOrCreate', 'ReadWrite', 'None', 4096, 'DeleteOnClose'
    )
    try {
        if ((Get-FileHash -LiteralPath $target).Hash -eq $env:IPCHECK_UPDATE_OLD_SHA) {
            if ((Get-FileHash -LiteralPath $next).Hash -ne $env:IPCHECK_UPDATE_NEW_SHA) {
                throw 'The staged download changed after verification.'
            }
            [IO.File]::Replace($next, $target, $backup)
        }
    } finally {
        $lock.Dispose()
    }
    Remove-Item -LiteralPath $stage -Recurse -Force
} catch {
    if ((Test-Path -LiteralPath $backup) -and -not (Test-Path -LiteralPath $target)) {
        Move-Item -LiteralPath $backup -Destination $target
    }
    Set-Content -LiteralPath (Join-Path $stage 'update-error.txt') -Value $_
    Remove-Item -LiteralPath $next -Force -ErrorAction SilentlyContinue
    exit 1
}
"""


def sha256(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def find_update(release, installed, installed_digest):
    tag = release["tag_name"]
    if not tag.startswith("v") or Version(tag[1:]) < installed:
        return None

    asset_tag = tag.replace("!", "-epoch-").replace("+", "-local-")
    names = {f"ipcheck{separator}{asset_tag}.exe" for separator in (" ", ".", "-")}
    for asset in release["assets"]:
        digest = asset.get("digest") or ""
        if (
            asset["name"] in names
            and asset["state"] == "uploaded"
            and re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
        ):
            digest = digest.removeprefix("sha256:")
            if digest == installed_digest:
                return None
            name = quote(asset["name"], safe="")
            url = f"https://github.com/{REPOSITORY}/releases/download/{quote(tag, safe='')}/{name}"
            return url, int(asset["size"]), digest
    return None


def check_for_update():
    request = Request(
        LATEST_RELEASE_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "ipcheck-windows"},
    )
    with urlopen(request, timeout=8) as response:
        release = json.load(response)
    target = Path(sys.executable).resolve()
    installed_digest = sha256(target)
    update = find_update(release, Version(RELEASE_VERSION), installed_digest)
    if update is None:
        return

    url, size, digest = update
    stage = Path(tempfile.mkdtemp(prefix=".ipcheck-update-", dir=target.parent))
    try:
        download = stage / "next.exe"
        with urlopen(url, timeout=15) as response, download.open("wb") as file:
            shutil.copyfileobj(response, file)
        if download.stat().st_size != size or sha256(download) != digest:
            raise ValueError("The downloaded executable did not match the release digest")

        powershell = (
            Path(os.environ["SystemRoot"])
            / "System32/WindowsPowerShell/v1.0/powershell.exe"
        )
        # Let Windows PowerShell use its own DLL search path.
        ctypes.windll.kernel32.SetDllDirectoryW(None)
        # Windows PowerShell needs its own module path when called from PowerShell 7.
        env = {key: value for key, value in os.environ.items() if key.upper() != "PSMODULEPATH"}
        subprocess.Popen(
            [str(powershell), "-NoProfile", "-NonInteractive", "-Command", APPLY_UPDATE],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
            env={
                **env,
                "IPCHECK_UPDATE_STAGE": str(stage),
                "IPCHECK_UPDATE_TARGET": str(target),
                "IPCHECK_UPDATE_LAUNCHER": str(os.getppid()),
                "IPCHECK_UPDATE_OLD_SHA": installed_digest,
                "IPCHECK_UPDATE_NEW_SHA": digest,
            },
        )
    except (OSError, ValueError, HTTPException, subprocess.SubprocessError):
        shutil.rmtree(stage, ignore_errors=True)
        raise
    print(f"ipcheck {release['tag_name']} is ready to install after exit.")


def test_again():
    from msvcrt import getwch

    print("Press Y to test again or any other key to exit.", flush=True)
    try:
        key = getwch()
        if key in ("\x00", "\xe0"):
            getwch()
    except KeyboardInterrupt:
        return False
    return key.lower() == "y"


def run():
    from ipcheck.cli import main

    if sys.argv[1:2] and sys.argv[1] in VERSION_FLAGS:
        print(f"ipcheck {RELEASE_VERSION}")
        return 0

    interactive = sys.platform == "win32" and sys.stdin.isatty() and sys.stdout.isatty()
    result = main()
    while interactive and test_again():
        result = main()

    if (
        sys.platform == "win32"
        and getattr(sys, "frozen", False)
        and os.environ.get("IPCHECK_NO_UPDATE") != "1"
    ):
        try:
            check_for_update()
        except (OSError, ValueError, KeyError, HTTPException, subprocess.SubprocessError):
            print("ipcheck update check unavailable; continuing with the installed version.", file=sys.stderr)
    return result


if __name__ == "__main__":
    sys.exit(run())
