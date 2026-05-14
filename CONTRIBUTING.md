# Contributing

Thanks for improving PromptForge.

## Development

Install Python 3.12 first. The setup script supports pyenv/pyenv-win, the Windows Python Launcher (`py -3.12`), or a `python` command that already points to Python 3.12.x.

Set up the project environment:

```powershell
.\scripts\setup_env.ps1
```

Run the app from source:

```powershell
.\.venv\Scripts\python.exe -m promptforge
```

Build the Windows executable:

```powershell
.\scripts\build_exe.ps1
```

## Notes

- Keep runtime data out of git. Source runs use `data/`; packaged runs use `dist\PromptForge\PromptForgeData\`.
- Do not commit `.venv`, `build`, `dist`, SQLite databases, or generated PyInstaller `.spec` files unless the build flow is intentionally changed.
- Prefer small, focused changes and verify with `python -m compileall promptforge run_promptforge.py` before opening a PR.
