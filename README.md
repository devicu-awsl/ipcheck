# ipcheck

A lightweight diagnostic tool for AI developers to inspect network configuration, IP reputation signals, and local account traces (--local). Results help identify issues; they do not guarantee account safety or predict a provider's enforcement decisions.

## Run on Windows

Download `ipcheck-v<version>.exe` from the [latest release](https://github.com/devicu-awsl/ipcheck/releases/latest). The Windows x64 executable includes Python and its dependencies. Save it in a folder you can write to and optionally rename it to `ipcheck.exe` so the filename stays the same across updates.

From PowerShell, run `.\ipcheck.exe` for the diagnostic report or `.\ipcheck.exe --version` to check the installed version.

After a diagnostic run, ipcheck checks the public releases for a newer version. It verifies the download against GitHub's SHA-256 and replaces the saved executable after the process exits. The next launch uses the new version. To skip the update check in a PowerShell session, run `$env:IPCHECK_NO_UPDATE = '1'` before starting ipcheck.

## Build and release

[Auto Build ipcheck.exe](https://github.com/devicu-awsl/ipcheck/actions/workflows/build-ipcheck.yml) runs on Mondays at 00:00 UTC. To run it on demand, select **Run workflow** on the `main` branch. It builds the latest stable PyPI package compatible with Python 3.11 and publishes a versioned release after the Windows executable passes a version check. If the release for that version already has its verified Windows asset, the run skips the build.
