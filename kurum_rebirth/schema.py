import typing as t
from pathlib import Path

from pydantic import BaseModel
from pydantic_yaml import parse_yaml_raw_as, to_yaml_str


class DropboxConfig(BaseModel):
    refresh_token: str = None


class KurumConfig(BaseModel):
    active_storage: t.Optional[t.Literal['dropbox']] = None
    dropbox: DropboxConfig = DropboxConfig()


class BackupTask(BaseModel):
    name: str
    base_path: str
    pattern: str
    excludes: list[str] = []


class RestoreTask(BaseModel):
    name: str
    path: str


class InitTask(BaseModel):
    type: t.Literal['folder_picker']
    name: str
    description: str
    required: bool = True


class SyncUserSetting(BaseModel):
    kurum_version: int = 1
    values: dict[str, t.Any] = {}


class SyncWatcher(BaseModel):
    process_name: str


class PlatformSyncOptions(BaseModel):
    watchers: list[SyncWatcher]
    init_tasks: list[InitTask] = []
    backup_tasks: list[BackupTask] = []
    restore_tasks: list[RestoreTask] = []


class SyncConfig(BaseModel):
    _key: str
    name: str
    platform: dict[str, PlatformSyncOptions]
    disabled: bool = False
    variables: list[str] = []

    def get_uninitialized_init_tasks(self, platform: str):
        for init_task in self.platform[platform].init_tasks:
            if init_task.required and not self.get_user_setting(init_task.name):
                yield init_task

        return

    def read_user_settings(self):
        config_path = Path(f"user_settings/{self._key}.yaml")

        config_path.parent.mkdir(exist_ok=True)

        if config_path.exists():
            with config_path.open("r", encoding='utf-8') as f:
                return parse_yaml_raw_as(SyncUserSetting, f.read())

        return SyncUserSetting()


    def write_user_settings(self, new_config: SyncUserSetting):
        config_path = Path(f"user_settings/{self._key}.yaml")

        config_path.parent.mkdir(exist_ok=True)

        with config_path.open("w", encoding='utf-8') as f:
            f.write(to_yaml_str(new_config))

    def set_user_setting(self, name: str, value):
        config = self.read_user_settings()
        config.values[name] = value
        self.write_user_settings(config)

    def get_user_setting(self, name: str, default_value = None):
        config = self.read_user_settings()
        return config.values.get(name, default_value)

