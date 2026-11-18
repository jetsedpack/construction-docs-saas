# Windows packaging prototype

Build on a controlled Windows 11 machine with Python 3.12:

1. Open PowerShell at repo root.
2. Run: .\packaging\build_windows.ps1
3. Inspect the output of Qt pyside6-deploy and validate the resulting .exe on a clean VM.

This uses Qt's official packaging path: https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html

**No signed installer is currently created.** Before real distribution: pin lockfile, build reproducibly, include SBOM and dependency scanning, sign EXE/MSI with a trusted certificate, secure auto-update, verify VC++ runtime/Windows version, test DPI settings, ensure no secrets are packed into artifact, backup and restore DPAPI keys.

Never load actual confidential construction records into this PoC executable before threat review and data-processing authorization.
