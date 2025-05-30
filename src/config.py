"""
Module for handling configuration settings for PyWall.
"""

import pathlib
import sys
import os
import configparser
import ctypes.wintypes
from src.logging_utils import action_logger

PYWALL_INI = "\\PyWall\\Config.ini"
PYWALL = "\\PyWall"

default_config = {
    "FILETYPE": {
        "accepted_types": ".exe",
        "blacklisted_names": "",
        "recursive": "True"
    },
    "GUI": {
        "advanced_mode": "False",
        "stylesheet": "dark_red.xml",
        "first_run": "True"
    },
    "UI": {
        "show_notifications": "True"
    },
    "DEBUG": {
        "create_logs": "False",
        "create_exception_logs": "True",
        "version": "v1.8",
        "shell": "False"
    }
}


def document_folder():
    """
    Get the path to the user's document folder.
    """
    CSIDL_PERSONAL = 5  # My Documents
    SHGFP_TYPE_CURRENT = 0  # Get current value, not default
    buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(
        None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)
    return buf.value


def script_folder():
    """
    Get the path to the script folder.
    """
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.abspath(".")


def config_file():
    """
    Get the configuration file path.
    """
    document_folder_path = document_folder()
    config_path = os.path.join(document_folder_path, PYWALL_INI)
    if os.path.exists(config_path):
        return config_path
    make_default()
    return config_path


def make_default():
    """
    Create the default configuration.
    """
    document_folder_path = document_folder()
    config_folder = os.path.join(document_folder_path, PYWALL)
    if not os.path.exists(config_folder):
        os.makedirs(config_folder)
    config_path = os.path.join(config_folder, "Config.ini")
    config = configparser.ConfigParser()
    for section, options in default_config.items():
        config.add_section(section)
        for option, value in options.items():
            config.set(section, option, value)
    with open(config_path, 'w', encoding='utf-8') as configfile:
        config.write(configfile)
    action_logger("Default configuration created")


def get_config(section, variable, *extra_args):
    """
    Get a configuration value.
    """
    config = configparser.ConfigParser()
    config.read(config_file())
    if extra_args:
        index_value = ''.join(extra_args)
        value = config[section][variable]
        value_list = value.split(', ')
        return value_list[int(index_value)]
    return config[section][variable]


def modify_config(section, variable, value):
    """
    Modify a configuration value.
    """
    config = configparser.ConfigParser()
    config.read(config_file())
    if config.has_option(section, variable):
        config.set(section, variable, value)
        with open(config_file(), 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        action_logger(f"Variable '{variable}' modified in section '{section}'")
    else:
        action_logger(
            f"Variable '{variable}' not found in section '{section}'")


def append_config(section, variable, value: list):
    """
    Append a value to a configuration list.
    """
    config = configparser.ConfigParser()
    config.read(config_file())
    if config.has_option(section, variable):
        current = config.get(section, variable)
        # Clean up any trailing commas
        current = current.rstrip(",")
        # Split by comma and clean up each item
        all_values = [item.strip()
                      for item in current.split(",") if item.strip()]
        for x in value:
            if x not in all_values:
                all_values.append(x)
        # Join with comma and space
        all_values = ", ".join(all_values)
        config.set(section, variable, all_values)
        with open(config_file(), 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        action_logger(
            f"Values '{value}' appended to variable '{variable}' in section '{section}'")
        return True
    return False


def remove_config(section, variable, value: list):
    """
    Remove a value from a configuration list.
    """
    config = configparser.ConfigParser()
    config.read(config_file())
    if config.has_option(section, variable):
        current = config.get(section, variable)
        all_values = current.split(", ") if "," in current else [current]
        for x in value:
            if x in all_values:
                all_values.remove(x)
        all_values = ", ".join(all_values)
        config.set(section, variable, all_values)
        with open(config_file(), 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        action_logger(
            f"Values '{value}' removed from variable '{variable}' in section '{section}'")
        return True
    return False


def config_exists():
    """
    Check if the configuration file exists.
    """
    return os.path.exists(config_file())


def validate_config(default_file=None):
    """
    Validate the configuration file.
    """
    import time
    config = configparser.ConfigParser()

    if default_file is None:
        default_file = default_config

    if config_exists():
        try:
            config.read(config_file())
        except configparser.ParsingError:
            make_default()
            time.sleep(0.1)

        action_logger("-" * 50)
        for x in range(len(default_file.keys())):
            section = list(default_file.keys())[x]
            for option in default_file[section]:
                if config.has_option(section, option):
                    action_logger(f'"{option}" validated')
                else:
                    action_logger(f'Check failed for "{option}"')
                    action_logger("-" * 50)
                    make_default()
        action_logger("-" * 50)
        action_logger("Updating version")
        modify_config("DEBUG", "version", default_file["DEBUG"]["version"])
        action_logger("-" * 50)
        return True

    make_default()
    return True


def setup_config_watcher():
    """Set up a file watcher to automatically reload config when it changes"""
    import threading
    import time
    import os
    from src.logger import actionLogger as logger

    config_last_modified = os.path.getmtime(config_file())

    def watcher():
        nonlocal config_last_modified
        while True:
            try:
                current_modified = os.path.getmtime(config_file())
                if current_modified > config_last_modified:
                    config_last_modified = current_modified
                    reload_config()
            except Exception:
                pass
            time.sleep(2)  # Check every 2 seconds

    def reload_config():
        logger("Config file changed, reloading configuration")
        validate_config()

        # Reset any cached config values here

    # Start watcher in background thread
    threading.Thread(target=watcher, daemon=True).start()
