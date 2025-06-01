#!/usr/bin/env python3
"""
PyWall - A simple firewall management tool for Windows.
Allows easy control of inbound and outbound connections for applications.
"""

import argparse
import os
import pathlib
import sys
import configparser # For config related errors

# Attempt to import QApplication safely for environments where it might not be available
# if only CLI is used.
try:
    from PyQt5.QtWidgets import QApplication
except ImportError:
    QApplication = None # Will be checked before use

from src.cmdWorker import access_handler
from src.config import config_exists, document_folder, make_default, validate_config
from src.logger import actionLogger, logException
from src.shellHandler import createInternetAccessMenu, removeInternetAccessMenu


def checkExistingInstall():
    """Check if PyWall is already installed."""
    try:
        doc_folder_path = document_folder() # document_folder() already has error handling
        if doc_folder_path is None: # Should not happen if document_folder handles errors by returning a path
            logException(RuntimeError("Document folder path is None"), "checkExistingInstall: Failed to get document folder.")
            return False
        return os.path.exists(os.path.join(doc_folder_path, "PyWall", "Executable.txt"))
    except OSError as e:
        logException(e, "checkExistingInstall: OSError checking for existing installation.")
        return False
    except Exception as e: # Catch any other unexpected error
        logException(e, "checkExistingInstall: Unexpected error.")
        return False


def saveCurrentFolder():
    """Save the current folder for context menu access."""
    try:
        doc_folder_path = document_folder()
        if doc_folder_path is None:
            logException(RuntimeError("Document folder path is None"), "saveCurrentFolder: Failed to get document folder.")
            return

        pywall_folder = os.path.join(doc_folder_path, "PyWall")
        if not os.path.exists(pywall_folder):
            os.makedirs(pywall_folder)

        executable_txt_path = os.path.join(pywall_folder, "Executable.txt")
        with open(executable_txt_path, 'w', encoding='utf-8') as f:
            f.write(os.path.dirname(os.path.abspath(__file__)))
        actionLogger(f"Current folder saved to {executable_txt_path}")
    except FileNotFoundError as e: # Specific to open() if a parent path component is invalid
        logException(e, f"saveCurrentFolder: FileNotFoundError writing to {executable_txt_path}")
    except PermissionError as e:
        logException(e, f"saveCurrentFolder: PermissionError creating directory or writing to {executable_txt_path}")
    except OSError as e:
        logException(e, f"saveCurrentFolder: OSError creating directory or writing to {executable_txt_path}")
    except Exception as e:
        logException(e, "saveCurrentFolder: Unexpected error.")


def main():
    """Main entry point for PyWall."""
    args = None # Initialize args
    try:
        # Config file setup
        try:
            if not config_exists():
                actionLogger("Config file does not exist, creating default.")
                make_default()
            actionLogger("Validating configuration.")
            if not validate_config(): # validate_config already logs its errors
                actionLogger("Initial validation failed, attempting to recreate default config.")
                make_default() # Attempt to fix by recreating
                if not validate_config(): # If still fails
                    actionLogger("FATAL: Configuration is invalid and could not be fixed. Exiting.")
                    # Consider a pop-up for GUI users if possible, or just exit for CLI
                    sys.exit(1) # Critical error, cannot proceed
        except (OSError, configparser.Error) as e:
            logException(e, "main: Critical error during initial config setup.")
            # Notify user if possible, then exit
            print(f"A critical error occurred with the configuration files: {e}. Please check logs. Exiting.", file=sys.stderr)
            sys.exit(1)

        # Argument Parsing
        parser = argparse.ArgumentParser(description='PyWall - Firewall Management Tool')
        parser.add_argument('-file', help='Target file or directory path', type=str)
        parser.add_argument('-allow', choices=['true', 'True', 'false', 'False'], help='Allow or deny internet access', type=str)
        parser.add_argument('-rule_type', choices=['in', 'out', 'both'], help='Rule type: inbound, outbound, or both', type=str)
        parser.add_argument('-install', action='store_true', help='Install context menu')
        parser.add_argument('-uninstall', action='store_true', help='Uninstall context menu')
        parser.add_argument('-config', action='store_true', help='Open configuration file')
        parser.add_argument("-c", help="Shell handler command string", type=str) # Clarified help

        try:
            # parse_known_args is good if other args might be passed that aren't for PyWall CLI itself
            # For example, if this script is a target for context menu with extra shell-provided args
            parsed_args, unknown_args = parser.parse_known_args()
            args = parsed_args # Assign to args, which was initialized to None
            if unknown_args:
                actionLogger(f"Unknown arguments encountered: {unknown_args}")
        except argparse.ArgumentError as e:
            logException(e, f"main: Argument parsing error. Arguments: {sys.argv[1:]}")
            print(f"Argument Error: {e}. Use -h or --help for usage.", file=sys.stderr)
            sys.exit(2) # Standard exit code for CLI syntax errors
        except SystemExit as e: # Raised by parser on -h, --help, or errors (if exit_on_error=True)
            # For -h or --help, exit code is 0, which is fine.
            # If it's an error (usually exit code 2), log it if not already handled by ArgumentParser.
            if e.code != 0:
                logException(e, f"main: SystemExit during argument parsing. Exit code: {e.code}. Arguments: {sys.argv[1:]}")
            sys.exit(e.code) # Propagate the exit code

        # Save current folder if not already installed (for context menu)
        # This should run early if other operations depend on it, but after arg parsing for -install/-uninstall
        if not checkExistingInstall() and not (args.install or args.uninstall):
            actionLogger("Existing install not detected, saving current folder.")
            saveCurrentFolder() # Has its own error handling

        # --- Shell handler actions (from context menu) ---
        if args.c: # args should be populated from parse_known_args
            actionLogger(f"Shell command received: {args.c}")
            argument_parts = args.c.split(',')
            shell_action_command = argument_parts[0] # e.g. "allowAccess" or "denyAccess"

            # The file path is expected to be in unknown_args if passed by context_menu.py
            # The original code had `arg = all_args[1]` then `file_path = arg[0]`
            # This implies unknown_args (all_args[1]) contains a list of file paths.
            # Let's assume context_menu.py passes the file path as the first unknown arg.
            file_path_str = None
            if unknown_args:
                file_path_str = unknown_args[0]
                actionLogger(f"File path from unknown_args: {file_path_str}")
            else:
                # This case might occur if -c is used directly from CLI without context_menu.py conventions
                # Or if the file path was mistakenly passed as part of the -c string.
                # For now, we require it from unknown_args for shell actions.
                logException(ValueError("Missing file path for shell command"), f"Shell command '{args.c}' executed without file path in unknown_args.")
                print("Error: Shell command requires a file path.", file=sys.stderr)
                sys.exit(1)

            action_type_str = ""
            if "allowAccess" in shell_action_command:
                action_type_str = "allow"
            elif "denyAccess" in shell_action_command:
                action_type_str = "deny"
            else:
                logException(ValueError(f"Unknown shell action: {shell_action_command}"), f"Shell command: {args.c}")
                sys.exit(1)

            rule_type_str = "both" # Default
            if len(argument_parts) > 1: # e.g. "allowAccess,in"
                rule_type_candidate = argument_parts[1]
                if rule_type_candidate in ['in', 'out', 'both']:
                    rule_type_str = rule_type_candidate

            actionLogger(f"Shell action: {shell_action_command}, File: {file_path_str}, Rule: {rule_type_str}")
            try:
                access_handler(pathlib.Path(file_path_str), action_type_str, rule_type_str)
            except TypeError as e: # e.g. if file_path_str is None and pathlib.Path fails
                logException(e, f"TypeError during shell access_handler call. Path: {file_path_str}, Action: {action_type_str}, Rule: {rule_type_str}")
            return # Shell command processed

        # --- Direct CLI actions ---
        if args.install:
            actionLogger("Installing context menu.")
            createInternetAccessMenu() # Assumes this has its own error handling
            saveCurrentFolder() # Ensure folder is saved on explicit install
            return

        if args.uninstall:
            actionLogger("Uninstalling context menu.")
            removeInternetAccessMenu() # Assumes this has its own error handling
            # Optionally remove Executable.txt here or leave it
            return

        if args.config:
            actionLogger("Opening configuration.")
            try:
                from src.cmdWorker import open_config
                open_config()
            except ImportError as e:
                logException(e, "main: Failed to import open_config from src.cmdWorker.")
            return

        if args.file and args.allow and args.rule_type:
            try:
                allow_action_bool = args.allow.lower() == 'true'
                action_str = "allow" if allow_action_bool else "deny"
                file_path_obj = pathlib.Path(str(args.file)) # str() handles if args.file is already Path

                actionLogger(f'File: {file_path_obj}, Action: {action_str}, Rule type: {args.rule_type}')
                access_handler(file_path_obj, action_str, args.rule_type)
            except TypeError as e: # If args.file is None
                logException(e, f"main: TypeError processing -file argument. Value: {args.file}")
            except Exception as e: # Catch any other error during this specific block
                logException(e, f"main: Error processing file access request. Args: {args}")
            return

        # If no CLI arguments that cause an early exit are provided, launch GUI
        if not any(vars(args).values()): # Check if any arguments were actually set/passed
            actionLogger("No specific CLI arguments provided, attempting to launch GUI.")
            if QApplication is None:
                logException(ImportError("PyQt5.QtWidgets.QApplication not found"), "main: Cannot start GUI, PyQt5 is not installed or accessible.")
                print("GUI cannot be started: PyQt5 is not available.", file=sys.stderr)
                sys.exit(1)

            app = QApplication(sys.argv)
            try:
                from src.configGui import start as start_gui # More specific import
                start_gui()
            except ImportError as e: # Dynamic import for GUI might fail
                logException(e, "main: Failed to import start_gui from src.configGui.")
                print(f"GUI Error: Could not import GUI components - {e}", file=sys.stderr)
                sys.exit(1)
            except Exception as e: # Catch-all for errors during GUI startup/execution
                logException(e, "main: An error occurred while starting or running the GUI.")
                # Optionally, show a GUI error message here if possible before exiting
                print(f"An unexpected error occurred with the GUI: {e}", file=sys.stderr)
                sys.exit(1) # Exit after GUI error

            sys.exit(app.exec_()) # Start Qt event loop

        else:
            # If some args were parsed but didn't match any known action sequence (e.g., only -file without -allow)
            actionLogger("Arguments provided but no specific action triggered. Showing help.")
            parser.print_help() # Show help if args were given but no action taken
            sys.exit(0)

    except AttributeError as e: # If args object is None or missing an attribute unexpectedly
        logException(e, f"main: AttributeError, likely an issue with argument parsing state. Args: {args}")
        # This might indicate a logic error in how `args` is handled post-parsing.
        if 'parser' in locals(): # Check if parser is defined
             parser.print_usage(sys.stderr)
        else:
            print("An attribute error occurred. Please check command arguments.", file=sys.stderr)
        sys.exit(1)
    except Exception as critical_error: # Final catch-all for any unhandled exceptions in main
        logException(critical_error, "main: An unexpected critical error occurred.")
        print(f"An unexpected critical error occurred: {critical_error}. Check logs for details.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

# Thanks for taking the time to read this script, you nerd \(￣︶￣*\)) #
