import logging
import re
from pathlib import Path
from collections import defaultdict
from zipfile import ZipFile
from abc import ABCMeta, abstractmethod

import psutil
from pydantic_yaml import parse_yaml_raw_as

from kurum_rebirth.services.storage import Storage
from kurum_rebirth.schema import SyncConfig, InitTask
from kurum_rebirth.const import DATA_ROOT


logger = logging.getLogger(__name__)


class SyncService(metaclass=ABCMeta):
    sync_configs: dict[str, SyncConfig]
    process_sync_configs: dict[str, list[SyncConfig]]

    def __init__(self, storage: Storage, service_handler: 'SyncServiceHandler') -> None:
        self.storage = storage

        self.sync_configs = dict()
        self.process_sync_configs = defaultdict(list)

        self._process_names = []

        self.platform = self.get_platform()
        self.service_handler = service_handler

        service_handler.sync_service = self

    @abstractmethod
    def get_platform(self) -> str:
        raise NotImplementedError

    def poll(self):
        if not self.storage.is_authorized:
            return

        logger.info("Checking backup/restore...")

        self.check_config_init()
        self.check_backup()
        self.check_restore()

    def scan_config(self):
        for config_path in Path(f"{DATA_ROOT}/sync_configs").glob("*.yaml"):
            logger.info("Adding Config: %s", config_path)

            with config_path.open('r', encoding='utf-8') as f:
                sync_config = parse_yaml_raw_as(SyncConfig, f.read())
                sync_config._key = config_path.stem
                self.add_sync_config(sync_config)

    def get_local_last_sync(self, key: str) -> int:
        path = Path(f"{DATA_ROOT}/last_sync/{key}")

        if not path.exists():
            return -1

        with path.open() as f:
            return int(f.read())

    def update_local_last_sync(self, key: str, value: int):
        path = Path(f"{DATA_ROOT}/last_sync/{key}")

        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open('w') as f:
            f.write(f"{value}")

    def check_config_init(self):
        for sync_config in self.sync_configs.values():
            if sync_config.disabled:
                continue

            for init_task in sync_config.get_uninitialized_init_tasks(self.platform):
                sync_config.disabled = True
                self.service_handler.on_init_task(sync_config, init_task)


    def check_backup(self):
        new_process_names = []

        for process in psutil.process_iter():
            new_process_names.append(process.name())

        removed_processes = set(self._process_names) - set(new_process_names)

        if len(removed_processes) > 0:
            logger.info(f"Removed processes: {removed_processes}")

            for process_name in removed_processes:
                if process_name not in self.process_sync_configs:
                    continue

                for sync_config in self.process_sync_configs[process_name]:
                    if sync_config.disabled:
                        continue

                    logger.info("Detected removed process: %s. Triggering %s", process_name, sync_config)
                    self.backup(sync_config)

        self._process_names = new_process_names

    def check_restore(self):
        for sync_config in self.sync_configs.values():
            if sync_config.disabled:
                continue

            # Local sync state is recent
            local_last_sync = self.get_local_last_sync(sync_config._key)
            remote_last_sync = self.storage.get_remote_last_sync(sync_config._key)

            if remote_last_sync == -1:
                continue

            if local_last_sync >= remote_last_sync:
                continue

            self.restore(sync_config)

    def add_sync_config(self, sync_config: SyncConfig):
        self.sync_configs[sync_config._key] = sync_config

        for watcher in sync_config.platform[self.platform].watchers:
            self.process_sync_configs[watcher.process_name].append(sync_config)

    def backup(self, config: SyncConfig):
        if not self.storage.is_authorized:
            logger.warning("Storage not configured.")

        logger.info(f"Backing up {config.name}")

        self.service_handler.on_backup_start(config)

        for task in config.platform[self.platform].backup_tasks:
            logger.info(f"Running backup task: {task.name}")

            base_path = Path(self.expand_path(config, task.base_path))

            logger.info(f"Base Path: {base_path}")

            temp_path = Path(f"{DATA_ROOT}/temp/backup/{config._key}/{task.name}.zip")
            temp_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"Packing...: {str(temp_path)}")
            with ZipFile(str(temp_path), 'w') as f:
                for backup_file_path in base_path.glob(task.pattern):
                    archive_path = str(backup_file_path.absolute()).replace(str(base_path), "")
                    f.write(str(backup_file_path.absolute()), arcname=archive_path)

            upload_path = f"/backups/{config._key}/{task.name}.zip"

            logger.info(f"Uploading: {upload_path}")
            self.storage.upload(f.filename, upload_path)
            logger.info(f"Upload finished: {upload_path}")

            temp_path.unlink()
            temp_path.parent.rmdir()

        self.storage.update_remote_last_sync(config._key)
        last_sync = self.storage.get_remote_last_sync(config._key)
        self.update_local_last_sync(config._key, last_sync)

        logger.info(f"Backup finished: {config.name}")
        self.service_handler.on_backup_end(config)

    def restore(self, config: SyncConfig):
        if not self.storage.is_authorized:
            logger.warning("Storage not configured.")

        logger.info(f"Restoring {config.name}")

        self.service_handler.on_restore_start(config)

        for task in config.platform[self.platform].restore_tasks:
            logger.info(f"Running restore task: {task.name}")

            temp_path = Path(f"{DATA_ROOT}/temp/restore/{config._key}/{task.name}.zip")
            temp_path.parent.mkdir(parents=True, exist_ok=True)

            source_path = f"/backups/{config._key}/{task.name}.zip"

            logger.info(f"Downloading: {source_path}")
            self.storage.download(source_path, str(temp_path))
            logger.info(f"Download finished: {source_path}")


            logger.info(f"Unpacking...: {str(temp_path)}")
            with ZipFile(str(temp_path), 'r') as f:
                f.extractall(self.expand_path(config, task.path))

        last_sync = self.storage.get_remote_last_sync(config._key)
        self.update_local_last_sync(config._key, last_sync)

        logger.info(f"Restored {config.name}")
        self.service_handler.on_restore_end(config)

    def expand_path(self, config: SyncConfig, path: str):
        variable_names = [(f"(@{re.escape(variable_name)})") for variable_name in config.variables]

        def repl(match: re.Match):
            variable_name = match.group(1)[1:]
            return config.get_user_setting(variable_name, "")

        if len(variable_names) > 0:
            path = re.sub(f"({'|'.join(variable_names)})", repl, path)

        return path

    def disable_config(self, config_key: str):
        logger.info(f"Disabled {config_key}.")
        self.sync_configs[config_key].disabled = True


class SyncServiceHandler(metaclass=ABCMeta):
    sync_service: SyncService

    @abstractmethod
    def on_init_task(self, config: SyncConfig, task: InitTask):
        pass

    @abstractmethod
    def on_backup_start(self, config: SyncConfig):
        pass

    @abstractmethod
    def on_backup_end(self, config: SyncConfig):
        pass

    @abstractmethod
    def on_restore_start(self, config: SyncConfig):
        pass

    @abstractmethod
    def on_restore_end(self, config: SyncConfig):
        pass
