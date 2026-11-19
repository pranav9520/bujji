import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo


@dataclass
class Settings:
    token: str = field(default_factory=lambda: os.getenv("BUJJI_TOKEN", ""))
    data: Path = field(default_factory=lambda: Path(os.getenv("BUJJI_DATA_DIR", "data")))
    files: Path = field(default_factory=lambda: Path(os.getenv("BUJJI_FILE_ROOT", "data/inbox")))
    timezone: str = field(default_factory=lambda: os.getenv("BUJJI_TIMEZONE", "Asia/Kolkata"))

    def validate(self):
        if len(self.token) < 32:
            raise RuntimeError("BUJJI_TOKEN must contain at least 32 characters. Run scripts/setup.ps1.")
        ZoneInfo(self.timezone)
        self.data.mkdir(parents=True, exist_ok=True)
        self.files.mkdir(parents=True, exist_ok=True)
