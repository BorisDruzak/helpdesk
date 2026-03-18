from pathlib import Path


def connection_rejected_flag_path(data_root: Path | None) -> Path:
    root = data_root or Path(".")
    return Path(root) / "connection_rejected.flag"
