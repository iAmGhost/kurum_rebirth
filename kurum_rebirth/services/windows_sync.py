import os
import re
from kurum_rebirth.schema import SyncConfig

from kurum_rebirth.services.sync import SyncService

SAFE_VARS = ['%AppData%', '%LocalAppData%', '%UserProfile%', '%ProgramFiles%', '%ProgramFiles(x86)%']


class WindowsSyncService(SyncService):
    def expand_path(self, config: SyncConfig, path: str):
        path = super().expand_path(config, path)

        patterns = [f"({re.escape(var)})" for var in SAFE_VARS]

        def repl(match: re.Match):
            return os.getenv(match.group(1)[1:-1])

        path = re.sub(f"({'|'.join(patterns)})", repl, path)

        return path

    def get_platform(self) -> str:
        return "windows"
