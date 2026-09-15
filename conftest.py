import os
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent / "app" / "normativa_UBU"


def pytest_configure(config):
    os.chdir(PROJECT_DIR)
