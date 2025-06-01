"""
cmdWorker module for handling firewall rules.
"""

import subprocess
import os
import sys
import ctypes
import pathlib
from src.pop import toastNotification, infoMessage, icons
from src.logger import actionLogger, logException
from src.config import get_config, config_file

ignoredFiles = get_config("FILETYPE", "blacklisted_names").split(",")


def admin():
    try:
        is_admin = os.getuid() == 0
    except AttributeError:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    return is_admin


def path_error(path: pathlib.Path):
    if not pathlib.Path.exists(path):
        try:
            icon = icons("critical")
            infoMessage(
                "Path type does not exist",
                "allTypes is None",
                "The indicated path does not exist or "
                "has been incorrectly typed, please try again",
                icon
            )
            return
        except NameError:
            actionLogger(
                f"Commands detected, skipping infoMessage, specified path '{path}' does not exist")
            toastNotification(
                "Path doesn't exist",
                f'"{str(path.name).title()}" doesn\'t exist or is not a valid '
                f'target please try again.'
            )
            return
    try:
        icon = icons("info")
        infoMessage(
            "No accepted filetype found",
            "allTypes is None",
            f'None of the accepted filetypes were found in the suffixes of the files in:\n"{path}"',
            icon
        )
        return
    except NameError:
        actionLogger(
            "Commands detected, skipping infoMessage, no accepted filetypes were found")
        if path.is_dir():
            toastNotification(
                "No accepted filetypes",
                f'No file in\n"{path}"\nis a valid target, please try again.'
            )
        else:
            toastNotification(
                "Filetype not accepted",
                f'Suffix "{path.suffix}" in file "{path.name}" is not a valid'
                f' target, please try again'
            )
        return


def get_allowed_types():
    allowed_types_str = get_config("FILETYPE", "accepted_types")
    if not allowed_types_str:
        return []
    return [t.strip() for t in allowed_types_str.split(",")]


allowedTypes = get_allowed_types()


def path_foreach_in(path):  # A rather telling name, isn't?
    from glob import glob
    glob_pattern = os.path.join(path, '*')
    filesNoRecursive = sorted(glob(glob_pattern), key=os.path.getctime)
    if get_config("FILETYPE", "recursive") == "True":
        filesRecursive = sorted(
            glob(glob_pattern + r"/**", recursive=True), key=os.path.getctime)
        files = sorted(filesRecursive + filesNoRecursive, key=os.path.getctime)
    elif get_config("FILETYPE", "recursive") == "False":
        files = filesNoRecursive
    else:
        from src.config import modify_config
        modify_config("FILETYPE", "recursive", "True")
        filesRecursive = sorted(
            glob(glob_pattern + r"/**", recursive=True), key=os.path.getctime)
        files = sorted(filesRecursive + filesNoRecursive, key=os.path.getctime)
    return files


def _validate_rule_type(rule_type: str) -> bool:
    """Validates the firewall rule type."""
    if rule_type not in {"both", "in", "out"}:
        from src.shellHandler import pop # Keep import local if only used here
        pop(
            "Rule type is invalid",
            f"The selected rule type ('{rule_type}') is not valid, please try again",
            True
        )
        actionLogger(f"Invalid rule type received: {rule_type}")
        return False
    return True


def _gather_target_files(path_str: str) -> list[pathlib.Path] | None:
    """Gathers all target files based on path, allowed types, and ignored files."""
    try:
        # Ensure path_str is a string before stripping, then convert to Path
        path = pathlib.Path(str(path_str).strip())

        if not path.exists():
            actionLogger(f"Path does not exist: {path}")
            path_error(path) # path_error handles user notification
            return None

        all_files = []
        if path.is_dir():
            actionLogger(f"Folder detected: {path}, gathering files.")
            # path_foreach_in expects a string path, ensure it gets one
            raw_files = path_foreach_in(str(path))
            all_files = [
                f for f in (pathlib.Path(y) for y in raw_files)
                if f.is_file() and \
                   any(allowed_suffix in f.suffix for allowed_suffix in allowedTypes) and \
                   f.stem not in ignoredFiles
            ]
        elif path.is_file():
            actionLogger(f"File detected: {path}, checking validity.")
            if path.stem not in ignoredFiles and \
               any(allowed_suffix in path.suffix for allowed_suffix in allowedTypes):
                all_files = [path]
            else:
                actionLogger(f"File '{path.name}' is ignored or not an allowed type.")
                all_files = None # Explicitly set to None if file is not valid
        else:
            actionLogger(f"Path is not a file or directory: {path}")
            path_error(path) # Or a more specific error
            return None

        if not all_files: # This check is now more robust
            actionLogger(f"No allowed files found for path: {path}")
            # Avoid calling path_error if it was a single file that was invalid due to type/ignore,
            # as path_error might give a generic "no accepted filetype found" for the parent dir.
            if not (path.is_file() and (path.stem in ignoredFiles or not any(allowed_suffix in path.suffix for allowed_suffix in allowedTypes))):
                path_error(path) # Call path_error if no suitable files were found generally
            return None

        actionLogger(f"Found {len(all_files)} target file(s) for {path}")
        return all_files

    except OSError as e:
        logException("gather_files_os_error", e)
        try:
            path_obj_for_error = pathlib.Path(str(path_str).strip())
        except Exception:
            path_obj_for_error = pathlib.Path(path_str)
        path_error(path_obj_for_error)
        return None
    except Exception as e: # Catch any other unexpected error
        logException("gather_files_unexpected_error", e)
        try:
            path_obj_for_error = pathlib.Path(str(path_str).strip())
        except Exception:
            path_obj_for_error = pathlib.Path(path_str)
        path_error(path_obj_for_error)
        return None


def _build_firewall_command(action: str, rule_type: str, file_path: pathlib.Path) -> str | None:
    """Constructs a netsh advfirewall command string using f-strings."""
    rule_name = f"PyWall blocked {file_path.stem}"
    program_path = str(file_path) # Convert pathlib.Path to string for the command

    if action == "deny":
        return f'@echo off && netsh advfirewall firewall add rule name="{rule_name}" dir={rule_type} program="{program_path}" action=block'
    elif action == "allow":
        return f'@echo off && netsh advfirewall firewall delete rule name="{rule_name}" dir={rule_type} program="{program_path}"'

    actionLogger(f"Invalid action '{action}' for building command for {file_path.name}")
    return None


def _execute_firewall_commands(commands: list[str], original_action: str, file_path: pathlib.Path) -> bool:
    """Executes firewall commands with admin privilege handling."""
    if not admin():
        actionLogger("Admin privileges required. Attempting to re-run with elevation.")
        try:
            icon = icons("critical")
            infoMessage(
                "Not Admin",
                "Missing UAC privileges",
                "This task requires elevation, please run as Admin",
                icon
            )
        except Exception as e:
            logException("elevation_info_error", e)
            actionLogger("InfoMessage display failed. Proceeding with elevation attempt.")
            toastNotification("Admin Required", "This task requires elevation. Attempting to elevate.")

        # Ensure all arguments for re-launch are strings
        args_list = [str(arg) for arg in sys.argv]
        args = " ".join(args_list)

        try:
            ctypes.windll.shell32.ShellExecuteW(None, "runas", str(sys.executable), args, None, 1)
            actionLogger("Successfully requested admin elevation. Exiting current process.")
            sys.exit("Admin re-run")
        except Exception as e:
            logException("elevation_shellexecute_error", e)
            actionLogger(f"Failed to re-launch with admin rights. Error: {e}")
            toastNotification("Elevation Failed", "Could not acquire admin privileges for firewall changes.")
            return False

    executed_successfully = True
    action_desc = "blocking" if original_action == "deny" else "allowing"

    for command in commands:
        if command:
            actionLogger(f"Executing command: {command}")
            try:
                # Using shell=True, command must be a string.
                process = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
                if process.stdout:
                    actionLogger(f"Command output: {process.stdout}")
                if process.stderr: # Should be empty if check=True, but good practice
                    actionLogger(f"Command error output: {process.stderr}")
            except subprocess.CalledProcessError as e:
                logException("firewall_subprocess_error", e)
                error_message = f"Error {action_desc} {file_path.name}. Command failed: {e.cmd}. Stderr: {e.stderr}"
                actionLogger(error_message)
                toastNotification("Command Error", f"Firewall command failed for {file_path.name}.") # Simplified message for user
                executed_successfully = False
            except Exception as e:
                logException("firewall_command_execution_error", e)
                error_message = f"An unexpected error occurred while {action_desc} {file_path.name}."
                actionLogger(error_message + f" Command: {command}. Error: {e}")
                toastNotification("Execution Error", f"Unexpected error processing {file_path.name}.") # Simplified
                executed_successfully = False

    if executed_successfully:
        cmn_log = "blocked" if original_action == "deny" else "allowed"
        actionLogger(f"Successfully {cmn_log} {file_path.stem} for relevant rule types.")
    else:
        actionLogger(f"One or more firewall commands failed for {file_path.stem}.")

    return executed_successfully


def access_handler(path, action, rule_type: str): # Parameter 'path' will be path_str from now on
    path_str = path # Rename for clarity within the function, matching new helpers

    # Restore the original allFiles initialization, it will be populated by _gather_target_files
    # allFiles = [] # Refactor Test - This line is no longer needed here.

    if not _validate_rule_type(rule_type):
        return "Invalid rule type"

    target_files = _gather_target_files(path_str)
    if not target_files:
        actionLogger(f"No valid target files found for path: '{path_str}'. Operation aborted.")
        # _gather_target_files or path_error would have shown a message to the user
        return "No target files"

    try:
        # For user-facing messages, use the name of the original path given.
        display_path_name = pathlib.Path(str(path_str).strip()).name
    except Exception:
        display_path_name = str(path_str) # Fallback

    all_operations_successful = True

    for file_path_obj in target_files: # Renamed to avoid confusion with original path parameter
        commands_to_execute = []
        if rule_type == "both":
            cmd_in = _build_firewall_command(action, "in", file_path_obj)
            cmd_out = _build_firewall_command(action, "out", file_path_obj)
            if cmd_in: commands_to_execute.append(cmd_in)
            if cmd_out: commands_to_execute.append(cmd_out)
        else:
            cmd = _build_firewall_command(action, rule_type, file_path_obj)
            if cmd: commands_to_execute.append(cmd)

        if not commands_to_execute:
            actionLogger(f"No commands to execute for {file_path_obj.name} (action: {action}, rule: {rule_type}). Skipping.")
            continue

        try:
            if not _execute_firewall_commands(commands_to_execute, action, file_path_obj):
                actionLogger(f"Failed to execute firewall commands for {file_path_obj.name}. Marking overall operation as failed.")
                all_operations_successful = False
        except Exception as e:
            logException("access_handler_loop_error", e)
            toastNotification("Error", f"A critical error occurred while processing {file_path_obj.name}.")
            all_operations_successful = False
            # Depending on severity, might 'return "Execution error"' here

    if all_operations_successful:
        toast_message_path = display_path_name
        # If the original path was a directory and many files were processed,
        # it might be better to refer to the directory name.
        # If it was a single file, its name is fine.
        # The current display_path_name should handle this reasonably.
        if action == "deny":
            toastNotification(
                "Success", f'Internet access rules updated for denying\n"{toast_message_path}"')
        elif action == "allow":
            toastNotification(
                "Success", f'Internet access rules updated for allowing\n"{toast_message_path}"')
    else:
        toastNotification(
            "Operation Partly Failed", f'Some rules for "{display_path_name}" may not have been applied. Check logs.'
        )
        return "Operation failed for some files"

    return "Operation completed"


def open_config():
    subprocess.call(f'cmd /c @echo off && {config_file()}')
