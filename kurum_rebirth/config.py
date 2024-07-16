from pathlib import Path

from kurum_rebirth.schema import KurumConfig
from pydantic_yaml import parse_yaml_raw_as, to_yaml_str

_config = KurumConfig()

config_path = Path("data/config.yaml")


def get_config() -> KurumConfig:
    return _config


def load_config():
    global _config

    if config_path.exists():
        with config_path.open('r', encoding='utf-8') as f:
            _config = parse_yaml_raw_as(KurumConfig, f.read())


def save_config():
    global _config

    with config_path.open('w', encoding='utf-8') as f:
        f.write(to_yaml_str(_config))
