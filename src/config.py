"""
Module for handling configuration settings for PyWall.
"""

import pathlib
import sys
import os
import configparser
import ctypes.wintypes
from src.logging_utils import action_logger # action_logger is already from logging_utils

# Attempt to import logException from src.logger, define fallback if not found
try:
    from src.logger import logException
except ImportError:
    print("Warning: src.logger.logException not found. Using fallback print for exception logging.")
    def logException(e, message=""):
        if message:
            print(f"LOG_EXCEPTION: {message} - {type(e).__name__}: {e}")
        else:
            print(f"LOG_EXCEPTION: {type(e).__name__}: {e}")

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
        "version": "v1.8", # Ensure this is updated with new versions
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
    try:
        ctypes.windll.shell32.SHGetFolderPathW(
            None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)
        return buf.value
    except Exception as e:
        logException(e, "Error getting document folder path via SHGetFolderPathW")
        return os.getcwd()


def script_folder():
    """
    Get the path to the script folder.
    """
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.abspath(".")


def config_file():
    """
    Get the configuration file path. Creates default if not exists.
    """
    document_folder_path = document_folder()
    config_path = os.path.join(document_folder_path, PYWALL_INI)
    try:
        if not os.path.exists(config_path):
            action_logger(f"Config file not found at {config_path}, creating default.")
            make_default()
    except OSError as e:
        logException(e, f"OSError while checking or preparing for default config file at {config_path}")
    return config_path


def make_default(cfg_path_override=None): # Allow path override for specific cases
    """
    Create the default configuration.
    If cfg_path_override is provided, it uses that path instead of the default.
    """
    if cfg_path_override:
        config_path = cfg_path_override
        # Ensure directory exists for the override path
        config_folder = os.path.dirname(cfg_path_override)
    else:
        document_folder_path = document_folder()
        config_folder = os.path.join(document_folder_path, PYWALL)
        config_path = os.path.join(config_folder, "Config.ini")

    try:
        if not os.path.exists(config_folder):
            os.makedirs(config_folder, exist_ok=True)

        config = configparser.ConfigParser()
        for section, options in default_config.items():
            config.add_section(section)
            for option, value in options.items():
                config.set(section, option, value)

        with open(config_path, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        action_logger(f"Default configuration created/reset at {config_path}")

    except OSError as e:
        logException(e, f"OSError creating default configuration at {config_path}")
    except configparser.Error as e:
        logException(e, f"ConfigParser error creating default configuration at {config_path}")


def get_config(section, variable, *extra_args):
    """
    Get a configuration value.
    """
    cfg_file_path = config_file()
    config = configparser.ConfigParser()
    try:
        read_ok = config.read(cfg_file_path)
        if not read_ok:
            action_logger(f"Config file {cfg_file_path} was not read successfully or is empty. Validating/Remaking default.")
            validate_config() # This will attempt to fix or remake default
            read_ok = config.read(cfg_file_path) # Try reading again
            if not read_ok: # If still not readable, critical issue
                 logException(RuntimeError(f"Config file {cfg_file_path} unreadable after validation attempt."), "get_config critical read failure")
                 # Fallback to in-memory default_config for this specific request if possible
                 if section in default_config and variable in default_config[section]:
                     action_logger(f"CRITICAL: Falling back to hardcoded default for {section}/{variable}")
                     return default_config[section][variable]
                 return None # Cannot satisfy

        if extra_args:
            index_value_str = ''.join(extra_args)
            value_str = config.get(section, variable)
            value_list = value_str.split(', ')
            try:
                index = int(index_value_str)
                return value_list[index]
            except ValueError as e:
                logException(e, f"Invalid index value '{index_value_str}' for {section}/{variable}")
                return None
            except IndexError as e:
                logException(e, f"Index {index_value_str} out of bounds for {section}/{variable} list")
                return None
        return config.get(section, variable)
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        logException(e, f"Missing section/option for {section}/{variable} in {cfg_file_path}. Validating and retrying.")
        validate_config() # Attempt to add missing keys
        # Retry reading the specific key after validation
        config.read(cfg_file_path) # Re-read
        try:
            return config.get(section, variable) # Try again
        except (configparser.NoSectionError, configparser.NoOptionError) as e2:
            logException(e2, f"Still missing {section}/{variable} after validation. Falling back to default.")
            if section in default_config and variable in default_config[section]:
                return default_config[section][variable]
            return None
    except configparser.Error as e:
        logException(e, f"ConfigParser error reading {cfg_file_path} for {section}/{variable}")
        if section in default_config and variable in default_config[section]:
            return default_config[section][variable]
        return None
    except Exception as e:
        logException(e, f"Unexpected error getting config for {section}/{variable}")
        return None


def modify_config(section, variable, value):
    """
    Modify a configuration value.
    """
    cfg_file_path = config_file()
    config = configparser.ConfigParser()
    try:
        if not os.path.exists(cfg_file_path): # Ensure file exists before reading
            action_logger(f"Config file {cfg_file_path} not found by modify_config. Creating default first.")
            make_default(cfg_file_path) # Pass path to ensure it's the one we try to write to

        config.read(cfg_file_path)
        if not config.has_section(section):
            action_logger(f"Section '{section}' not found in modify_config. Adding new section.")
            config.add_section(section)

        config.set(section, str(variable), str(value))
        with open(cfg_file_path, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        action_logger(f"Variable '{variable}' modified to '{value}' in section '{section}'")
    except configparser.Error as e:
        logException(e, f"ConfigParser error modifying {section}/{variable} in {cfg_file_path}")
    except OSError as e:
        logException(e, f"OSError writing modified config to {cfg_file_path}")
    except Exception as e:
        logException(e, f"Unexpected error modifying config for {section}/{variable}")


def append_config(section, variable, value_to_append: list):
    """
    Append a value to a configuration list. Ensures value is a list.
    """
    if not isinstance(value_to_append, list):
        value_to_append = [str(value_to_append)]

    cfg_file_path = config_file()
    config = configparser.ConfigParser()
    try:
        if not os.path.exists(cfg_file_path):
            action_logger(f"Config file {cfg_file_path} not found by append_config. Creating default first.")
            make_default(cfg_file_path)

        config.read(cfg_file_path)
        if not config.has_section(section):
            action_logger(f"Section '{section}' not found in append_config. Adding new section.")
            config.add_section(section)

        current_value_str = ""
        if config.has_option(section, variable):
            current_value_str = config.get(section, variable)

        all_values = [item.strip() for item in current_value_str.split(",") if item.strip()] if current_value_str else []

        appended_count = 0
        for val_item in value_to_append:
            str_val_item = str(val_item).strip()
            if str_val_item and str_val_item not in all_values:
                all_values.append(str_val_item)
                appended_count +=1

        if appended_count > 0:
            new_value_str = ", ".join(all_values)
            config.set(section, variable, new_value_str)
            with open(cfg_file_path, 'w', encoding='utf-8') as configfile:
                config.write(configfile)
            action_logger(f"Values '{value_to_append}' (appended {appended_count}) to variable '{variable}' in section '{section}'")
        else:
            action_logger(f"No new values from '{value_to_append}' appended to '{variable}' in '{section}' (already exist or empty).")
        return True
    except configparser.Error as e:
        logException(e, f"ConfigParser error appending to {section}/{variable} in {cfg_file_path}")
    except OSError as e:
        logException(e, f"OSError writing appended config to {cfg_file_path}")
    except Exception as e:
        logException(e, f"Unexpected error appending config for {section}/{variable}")
    return False


def remove_config(section, variable, value_to_remove: list):
    """
    Remove a value from a configuration list. Ensures value is a list.
    """
    if not isinstance(value_to_remove, list):
        value_to_remove = [str(value_to_remove)]

    cfg_file_path = config_file()
    config = configparser.ConfigParser()
    try:
        if not os.path.exists(cfg_file_path):
            action_logger(f"Config file {cfg_file_path} not found by remove_config. Nothing to remove.")
            return False

        config.read(cfg_file_path)
        if not config.has_option(section, variable):
            action_logger(f"Variable '{variable}' not found in section '{section}' for removal. Nothing to do.")
            return False

        current_value_str = config.get(section, variable)
        all_values = [item.strip() for item in current_value_str.split(", ") if item.strip()]

        removed_count = 0
        temp_values = list(all_values)
        for val_item in value_to_remove:
            str_val_item = str(val_item).strip()
            if str_val_item in temp_values:
                temp_values.remove(str_val_item)
                removed_count += 1

        if removed_count > 0:
            new_value_str = ", ".join(temp_values)
            config.set(section, variable, new_value_str)
            with open(cfg_file_path, 'w', encoding='utf-8') as configfile:
                config.write(configfile)
            action_logger(f"Values '{value_to_remove}' (removed {removed_count}) from variable '{variable}' in section '{section}'")
        else:
            action_logger(f"No values from '{value_to_remove}' found to remove from '{variable}' in '{section}'.")
        return True

    except configparser.Error as e:
        logException(e, f"ConfigParser error removing from {section}/{variable} in {cfg_file_path}")
    except OSError as e:
        logException(e, f"OSError writing removed config to {cfg_file_path}")
    except Exception as e:
        logException(e, f"Unexpected error removing config for {section}/{variable}")
    return False


def config_exists():
    """
    Check if the configuration file exists.
    """
    doc_path = document_folder()
    cfg_path = os.path.join(doc_path, PYWALL_INI)
    return os.path.exists(cfg_path)


def validate_config(default_conf_data=None):
    """
    Validate the configuration file. Adds missing sections/options from default_config
    without fully overwriting user's existing valid settings.
    """
    import time
    config = configparser.ConfigParser()
    cfg_file_path = config_file()

    if default_conf_data is None:
        default_conf_data = default_config

    if not os.path.exists(cfg_file_path):
        action_logger(f"Config file {cfg_file_path} not found by validate_config. Creating default.")
        make_default(cfg_file_path) # Pass path to ensure it's this one
        if not os.path.exists(cfg_file_path):
            action_logger(f"FATAL: Failed to create default config at {cfg_file_path} during validation.")
            return False

    try:
        read_ok = config.read(cfg_file_path)
        if not read_ok: # File is empty or completely unreadable but not necessarily a parsing error for configparser
            action_logger(f"Config file {cfg_file_path} could not be read (empty or unreadable). Recreating default.")
            make_default(cfg_file_path)
            time.sleep(0.1)
            read_ok = config.read(cfg_file_path) # Try reading again
            if not read_ok:
                 logException(RuntimeError(f"Config file {cfg_file_path} still unreadable after recreating."), "validate_config read failure")
                 return False # Critical failure
    except configparser.Error as e:
        logException(e, f"Config file {cfg_file_path} is corrupted. Recreating default.")
        make_default(cfg_file_path)
        time.sleep(0.1)
        try:
            config.read(cfg_file_path)
        except configparser.Error as e2:
            logException(e2, f"Failed to read config file {cfg_file_path} even after recreating from corruption.")
            return False

    action_logger("--- Validating Configuration Structure ---")
    needs_save = False # Flag to track if changes were made that require saving

    for section_key, section_values in default_conf_data.items():
        if not config.has_section(section_key):
            action_logger(f"Missing section '{section_key}'. Adding with default values.")
            config.add_section(section_key)
            for option_key, option_value in section_values.items():
                config.set(section_key, option_key, str(option_value))
            needs_save = True
        else: # Section exists, check its options
            for option_key, default_option_value in section_values.items():
                if not config.has_option(section_key, option_key):
                    action_logger(f"Missing option '{option_key}' in section '{section_key}'. Adding with default value: '{default_option_value}'.")
                    config.set(section_key, option_key, str(default_option_value))
                    needs_save = True
                # else: Option exists, for now, we don't validate its type or content beyond existence
                    # action_logger(f'Option "{option_key}" in section "{section_key}" validated.')

    if needs_save:
        action_logger("Configuration was updated with missing sections/options. Saving changes.")
        try:
            with open(cfg_file_path, 'w', encoding='utf-8') as configfile:
                config.write(configfile)
        except OSError as e:
            logException(e, f"OSError writing updated config during validation to {cfg_file_path}")
            return False # Failed to save the fixes

    action_logger("--- Updating version (if necessary) ---")
    try:
        # Ensure DEBUG section exists after potential fixes, then get version
        if not config.has_section("DEBUG"): # Should have been added if missing
             config.add_section("DEBUG") # Add it if somehow still missing
             action_logger("DEBUG section was missing, added for version check.")
             needs_save = True # Mark for saving

        current_version = config.get("DEBUG", "version", fallback=None) # fallback handles NoOptionError
        default_version = default_conf_data.get("DEBUG", {}).get("version")

        if default_version is not None and current_version != default_version:
            config.set("DEBUG", "version", default_version)
            action_logger(f"Updated version from '{current_version}' to '{default_version}'.")
            needs_save = True # Version was updated, so save
        else:
            action_logger("Version is current or default version not specified.")

        if needs_save: # Save again if version update caused a change
            action_logger("Saving configuration after version update.")
            with open(cfg_file_path, 'w', encoding='utf-8') as configfile:
                config.write(configfile)

    except configparser.Error as e: # Catch errors from get/set during version update
        logException(e, "ConfigParser error during version update in validate_config")
    except OSError as e: # Catch errors from file write during version update
        logException(e, f"OSError writing version-updated config to {cfg_file_path}")
        return False
    except Exception as e:
        logException(e, "Unexpected error during version update in validate_config")

    action_logger("--- Validation and Update Process Complete ---")
    return True


def setup_config_watcher():
    """Set up a file watcher to automatically reload config when it changes"""
    import threading
    import time
    try:
        from src.logger import actionLogger as config_watcher_logger
    except ImportError:
        config_watcher_logger = lambda msg: print(f"CONFIG_WATCHER_LOG: {msg}")

    cfg_file_path = config_file()
    try:
        # Ensure file exists before getting mtime, validate_config might create it
        if not os.path.exists(cfg_file_path):
            action_logger("Config file doesn't exist, attempting validation to create it before watcher starts.", "ConfigWatcher")
            validate_config() # This should create it if all goes well
            if not os.path.exists(cfg_file_path):
                 logException(FileNotFoundError(f"Config file {cfg_file_path} still missing after validation."), "ConfigWatcherSetup")
                 return # Cannot proceed

        config_last_modified = os.path.getmtime(cfg_file_path)
    except OSError as e:
        logException(e, f"Cannot start config watcher: failed to getmtime for {cfg_file_path}")
        return

    def watcher():
        nonlocal config_last_modified
        while True:
            try:
                time.sleep(2) # Check every 2 seconds
                if not os.path.exists(cfg_file_path):
                    config_watcher_logger(f"Config file {cfg_file_path} deleted. Watcher waiting for its recreation.")
                    # config_last_modified could be set to 0 or None to force reload if file reappears
                    continue

                current_modified = os.path.getmtime(cfg_file_path)
                if current_modified != config_last_modified:
                    config_watcher_logger(f"Config file {cfg_file_path} change detected (Timestamp: {current_modified}). Reloading.")
                    try:
                        reload_config_successfully = reload_config()
                        if reload_config_successfully:
                            config_last_modified = current_modified # Update only on successful reload
                            config_watcher_logger("Config reloaded successfully, watcher timestamp updated.")
                        else:
                            config_watcher_logger("Config reload attempt failed. Watcher timestamp not updated.")
                            # Keep old timestamp to retry reload on next detected change or fixed issue
                    except Exception as e_reload: # Catch any unexpected error from reload_config itself
                        logException(e_reload, "Exception during reload_config call in watcher")
                        config_watcher_logger("Config reload attempt failed due to an exception. Watcher timestamp not updated.")


            except FileNotFoundError:
                config_watcher_logger(f"Config file {cfg_file_path} not found during check. Watcher waiting.")
            except OSError as e_watch:
                logException(e_watch, f"OSError in config watcher for {cfg_file_path}. Watcher continuing.")
            except Exception as e_watch_general:
                logException(e_watch_general, "Unexpected error in config watcher loop. Watcher continuing.")

    def reload_config(): # Renamed from previous version, now returns success status
        config_watcher_logger("Attempting to reload configuration by re-validating...")
        try:
            success = validate_config() # validate_config handles its own logging
            if success:
                # Reset any cached config values here if the application caches them.
                config_watcher_logger("Configuration re-validated successfully.")
                return True
            else:
                config_watcher_logger("Configuration re-validation failed.")
                return False
        except Exception as e:
            logException(e, "Exception during validate_config in reload_config")
            return False


    try:
        watcher_thread = threading.Thread(target=watcher, daemon=True)
        watcher_thread.name = "ConfigWatcherThread"
        watcher_thread.start()
        action_logger("Configuration watcher started.")
    except Exception as e:
        logException(e, "Failed to start configuration watcher thread.")
