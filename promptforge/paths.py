from pathlib import Path
import sys


APP_NAME = "PromptForge"
PORTABLE_DATA_DIR = "PromptForgeData"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def app_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / PORTABLE_DATA_DIR
    return project_root() / "data"


def ensure_data_dirs() -> Path:
    data_dir = app_data_dir()
    (data_dir / "images").mkdir(parents=True, exist_ok=True)
    (data_dir / "backups").mkdir(parents=True, exist_ok=True)
    return data_dir
