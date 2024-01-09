import os

import yaml


def load_config():
    file_path = os.getenv("CONFIG_PATH", "./config/config.yml")
    with open(file_path, "r") as config_file:
        config = yaml.safe_load(config_file)
    return config
