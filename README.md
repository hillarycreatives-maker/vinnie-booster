# Vinnie Booster

A safe, terminal-style Windows storage analyzer that helps you find what is using disk space without silently deleting anything.

> **Safety first:** Vinnie Booster is report-only. It does not delete, move, modify, or upload files.

## Features

- Recursive scan of a drive or selected folder.
- Largest files and folders ranked by size.
- Protected labels for Windows and application locations.
- Review labels for Downloads, caches, temporary files, installers, archives, backups, and disk images.
- TXT, CSV, and JSON reports.
- Read-only RAM status and practical memory recommendations.
- No third-party Python packages required.

## Requirements

- Windows 10 or Windows 11.
- Python 3.10 or newer.
- PowerShell or Command Prompt.

## Quick start

1. Download `vinnie_booster.py`.
2. Open PowerShell or Command Prompt in the download folder.
3. Scan your personal files first.

In **PowerShell**:

```powershell
py .\vinnie_booster.py "$env:USERPROFILE" --output .\reports
```

In **Command Prompt (`cmd.exe`)**:

```bat
py .\vinnie_booster.py "%USERPROFILE%" --output .\reports
```

4. For a full drive scan, run PowerShell as Administrator and use:

```powershell
py .\vinnie_booster.py C:\ --output .\reports
```

Open the TXT report first. Open the CSV in Excel when you want to sort or filter. Keep the JSON report as the complete machine-readable record.

## Controls

```text
root                 Drive or folder to scan; default is C:\
--output PATH        Report destination; default is storage_scan_reports
--max-depth N        Folder depth limit; default is 12
--ram                Show current RAM status and safe recommendations, then exit
-h, --help           Show all available options
```

Examples:

```powershell
# Scan Downloads only
py .\vinnie_booster.py "$env:USERPROFILE\Downloads" --output .\reports

# Faster first pass with a shallower scan
py .\vinnie_booster.py C:\ --max-depth 6 --output .\reports

# Read-only memory status
py .\vinnie_booster.py --ram
```

The scanner also accepts the PowerShell-style `$env:USERPROFILE` text if it is accidentally pasted into Command Prompt, but `%USERPROFILE%` is the native Command Prompt form.

## What to do after the report

1. Start with the TXT summary and inspect the largest items.
2. Treat **PROTECTED** entries as off-limits. Do not delete Windows, Program Files, ProgramData, Recovery, or application data based only on size.
3. For **REVIEW** entries, open the folder in File Explorer and confirm ownership and contents.
4. Back up personal files before removing them.
5. Prefer uninstalling applications through **Settings → Apps → Installed apps**, rather than deleting their folders.
6. Empty the Recycle Bin only after checking its contents.
7. Remove old installers, ISO files, archives, and videos only when you are certain you no longer need them.
8. Re-run Vinnie Booster after cleanup to verify the result.

## Duplicate-file recommendations

Do not delete duplicates automatically. Compare full paths, filenames, dates, and contents first. Good candidates for manual review include repeated downloads, copied installers, and duplicate exported videos. Do not merge or remove files from AppData, game libraries, cloud-sync folders, databases, Outlook data, or backup sets unless you understand how the application uses them.

A safe workflow is: copy one version to a backup location, open it, verify the other copy is identical and no longer referenced, then remove only the confirmed extra through File Explorer. Cloud-sync folders should be handled in the sync application's own interface.

## RAM “booster” behavior

Vinnie Booster does not claim to create RAM. Memory-cleaner utilities often provide little lasting benefit and can make applications slower. The `--ram` control is intentionally read-only: it reports memory pressure and recommends closing unused applications, browser tabs, and background launchers. Use Windows Task Manager (`Ctrl+Shift+Esc`) to identify unusually heavy processes. Never terminate a process just because it uses RAM; identify it first.

## Privacy

Reports can contain full local file paths. Keep reports private and inspect them before sharing. Vinnie Booster has no network code and does not upload scan results.

## License

MIT. See `LICENSE`.
