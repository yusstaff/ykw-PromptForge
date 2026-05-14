from pathlib import Path
import shutil
import uuid


class ImageStore:
    ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

    def __init__(self, image_dir: Path):
        self.image_dir = image_dir
        self.image_dir.mkdir(parents=True, exist_ok=True)

    def copy_into_store(self, source_path: str):
        source = Path(source_path)
        suffix = source.suffix.lower()
        if suffix not in self.ALLOWED_SUFFIXES:
            raise ValueError("仅支持 PNG、JPG、WEBP、BMP、GIF 图片。")

        stored_name = f"{uuid.uuid4().hex}{suffix}"
        target = self.image_dir / stored_name
        shutil.copy2(str(source), str(target))
        return stored_name, source.name

    def duplicate_stored_file(self, stored_path: str) -> str:
        source = self.path_for(stored_path)
        if not source.exists():
            raise FileNotFoundError(str(source))

        suffix = source.suffix.lower()
        stored_name = f"{uuid.uuid4().hex}{suffix}"
        target = self.image_dir / stored_name
        shutil.copy2(str(source), str(target))
        return stored_name

    def path_for(self, stored_path: str) -> Path:
        return self.image_dir / stored_path

    def list_unreferenced_files(self, referenced_paths) -> list:
        normalized = {
            str(path).replace("\\", "/").strip("/")
            for path in referenced_paths
            if str(path).strip()
        }
        files = []
        for path in self.image_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in self.ALLOWED_SUFFIXES:
                continue
            relative_path = path.relative_to(self.image_dir).as_posix()
            if relative_path not in normalized:
                files.append(path)
        return sorted(files, key=lambda item: item.name.lower())

    def remove(self, stored_path: str) -> None:
        path = self.path_for(stored_path)
        if path.exists():
            path.unlink()
