import os
import pathlib
import subprocess
import sys  # Added missing sys import at the module level

from context_menu import menus

from src.config import document_folder
from src.pop import toastNotification


# Having to define stuff anew in this script, since it's technically separate in the context of the shell
# this means duping already existing code :(


def getScriptFolder():
    document_folder_path = str(document_folder())
    return document_folder_path + "\\PyWall\\Executable.txt"

def pop(title, text, close: bool):
    toastNotification(title, text)
    if close:
        sys.exit(0)


# The "open" command is repeated because I'm too lazy to define it and then just call it later, code redundancy go brr #
def pyWallPath(folder):
    return pathlib.Path(str(folder) + "/PyWall.exe")


def pyWallScript(folder):
    return pathlib.Path(str(folder) + "/main.py")


def getFolder():
    try:
        with open(getScriptFolder(), 'r') as sf:
            folder = sf.read()
            return folder
    except FileNotFoundError:
        pop("PyWall.exe not found",
            "Could not find PyWall, please open the program and try again.", True)
    except OSError as e: # Catch other potential OS errors during file read
        pop(f"Error reading script folder: {type(e).__name__}",
            f"Could not read PyWall's location. Details: {e}", True)
    return None # Ensure None is returned on error


def allowAccess(filenames, params):
    folder = getFolder()
    if not folder: # Explicitly check if folder is None
        # pop message already shown by getFolder() if it failed to find the file
        return

    try:
        # Ensure paths are constructed safely, even if folder name might be unusual
        pywall_exe_path = pyWallPath(folder)
        main_py_path = pyWallScript(folder)

        if pywall_exe_path.is_file() or main_py_path.is_file():
            # Determine which command to use (prefer exe if available)
            if pywall_exe_path.is_file():
                command_parts = [str(pywall_exe_path), "-file", str(filenames), "-allow", "true", "-rule_type", str(params)]
                # Use subprocess.run for better control and error handling if needed in future.
                # For now, sticking to subprocess.call as per original code, but with direct executable call.
                subprocess.call(f'cmd /c cd "{folder}" && PyWall.exe -file "{filenames}" -allow true -rule_type {params}', shell=True)

            elif main_py_path.is_file(): # Fallback to python script
                subprocess.call(f'cmd /c cd "{folder}" && python "{main_py_path}" -file "{filenames}" -allow true -rule_type {params}', shell=True)
        else:
            # This case implies getFolder() found Executable.txt but PyWall.exe/main.py is missing from that location.
            if os.path.exists(getScriptFolder()): # Check before removing
                 os.remove(getScriptFolder())
            pop("PyWall application not found",
                "PyWall.exe or main.py is missing from the recorded location. Please reinstall or reconfigure.", True)

    except FileNotFoundError: # Should ideally be caught by getFolder or path checks
        pop("PyWall application path error",
            "A FileNotFoundError occurred while trying to run PyWall. Please check installation.", True)
    except PermissionError:
        pop("Permission Denied",
            "Permission denied when trying to execute PyWall.", True)
    except subprocess.SubprocessError as spe:
         pop("Subprocess Error",
            f"Failed to run PyWall. Details: {spe}", True)
    except Exception as e: # General fallback
        pop("Error allowing access",
            f"An unexpected error occurred: {e}", True)


def denyAccess(filenames, params):
    folder = getFolder()
    if not folder:
        return

    try:
        pywall_exe_path = pyWallPath(folder)
        main_py_path = pyWallScript(folder)

        if pywall_exe_path.is_file() or main_py_path.is_file():
            if pywall_exe_path.is_file():
                 subprocess.call(f'cmd /c cd "{folder}" && PyWall.exe -file "{filenames}" -allow false -rule_type {params}', shell=True)
            elif main_py_path.is_file():
                 subprocess.call(f'cmd /c cd "{folder}" && python "{main_py_path}" -file "{filenames}" -allow false -rule_type {params}', shell=True)

        else:
            if os.path.exists(getScriptFolder()):
                os.remove(getScriptFolder())
            pop("PyWall application not found",
                "PyWall.exe or main.py is missing from the recorded location. Please reinstall or reconfigure.", True)

    except FileNotFoundError:
        pop("PyWall application path error",
            "A FileNotFoundError occurred while trying to run PyWall. Please check installation.", True)
    except PermissionError:
        pop("Permission Denied",
            "Permission denied when trying to execute PyWall.", True)
    except subprocess.SubprocessError as spe:
         pop("Subprocess Error",
            f"Failed to run PyWall. Details: {spe}", True)
    except Exception as e:
        pop("Error denying access",
            f"An unexpected error occurred: {e}", True)


def createInternetAccessMenu():
    IAM = menus.ContextMenu('PyWall', type='FILES')
    IAM_ALLOW = createAllowMenu()
    IAM_DENY = createDenyMenu()
    IAM.add_items([IAM_ALLOW, IAM_DENY])
    IAM.compile()

    IAM_Folder = menus.ContextMenu('PyWall', type='DIRECTORY')
    IAM_Folder.add_items([IAM_ALLOW, IAM_DENY])
    IAM_Folder.compile()

    updateRegistry()


def createAllowMenu():
    IAM_ALLOW = menus.ContextMenu('Allow Internet Access')
    IAM_ALLOW.add_items([
        menus.ContextCommand("Allow inbound connections",
                             python=allowAccess, params='in'),
        menus.ContextCommand("Allow outbound connections",
                             python=allowAccess, params="out"),
        menus.ContextCommand(
            "Allow inbound and outbound connections", python=allowAccess, params="both")
    ])
    return IAM_ALLOW


def createDenyMenu():
    IAM_DENY = menus.ContextMenu('Deny Internet Access')
    IAM_DENY.add_items([
        menus.ContextCommand("Deny inbound connections",
                             python=denyAccess, params='in'),
        menus.ContextCommand("Deny outbound connections",
                             python=denyAccess, params="out"),
        menus.ContextCommand(
            "Deny inbound and outbound connections", python=denyAccess, params="both")
    ])
    return IAM_DENY


def updateRegistry():
    import winreg

    # Attempt to import logException and actionLogger, assuming they're in src.logger
    # Fallback definitions if import fails, to prevent NameError
    try:
        from src.logger import logException, actionLogger
    except ImportError:
        print("Warning: src.logger.logException or actionLogger not found. Using fallback print statements for logging.")
        def logException(e, message=""):
            if message:
                print(f"LOG_EXCEPTION: {message} - {type(e).__name__}: {e}")
            else:
                print(f"LOG_EXCEPTION: {type(e).__name__}: {e}")

        def actionLogger(message):
            print(f"ACTION_LOGGER: {message}")

    FILES_ALLOW_BOTH = r"Software\Classes\*\shell\PyWall\shell\Allow Internet Access\shell\Allow inbound and outbound connections\command"
    FILES_ALLOW_IN = r"Software\Classes\*\shell\PyWall\shell\Allow Internet Access\shell\Allow inbound connections\command"
    FILES_ALLOW_OUT = r"Software\Classes\*\shell\PyWall\shell\Allow Internet Access\shell\Allow outbound connections\command"
    FILES_DENY_BOTH = r"Software\Classes\*\shell\PyWall\shell\Deny Internet Access\shell\Deny inbound and outbound connections\command"
    FILES_DENY_IN = r"Software\Classes\*\shell\PyWall\shell\Deny Internet Access\shell\Deny inbound connections\command"
    FILES_DENY_OUT = r"Software\Classes\*\shell\PyWall\shell\Deny Internet Access\shell\Deny outbound connections\command"

    DIR_ALLOW_BOTH = FILES_ALLOW_BOTH.replace("*", "Directory")
    DIR_ALLOW_IN = FILES_ALLOW_IN.replace("*", "Directory")
    DIR_ALLOW_OUT = FILES_ALLOW_OUT.replace("*", "Directory")
    DIR_DENY_BOTH = FILES_DENY_BOTH.replace("*", "Directory")
    DIR_DENY_IN = FILES_DENY_IN.replace("*", "Directory")
    DIR_DENY_OUT = FILES_DENY_OUT.replace("*", "Directory")

    key = winreg.HKEY_CURRENT_USER
    sub_keys_to_modify = [
        FILES_ALLOW_BOTH, FILES_DENY_BOTH, FILES_ALLOW_IN, FILES_DENY_IN, FILES_ALLOW_OUT, FILES_DENY_OUT,
        DIR_ALLOW_BOTH, DIR_DENY_BOTH, DIR_ALLOW_IN, DIR_DENY_IN, DIR_ALLOW_OUT, DIR_DENY_OUT
    ]

    PYWALL_REG_FILE_ICON_KEY = r"Software\Classes\*\shell\PyWall"
    PYWALL_REG_FOLDER_ICON_KEY = r"Software\Classes\Directory\shell\PyWall"

    try:
        folder = getFolder()
        if not folder:
            message = "Could not get folder path. Skipping registry updates."
            actionLogger(message)
            # Consider a more visible warning to the user if this is critical
            # For now, just logging and exiting the function.
            return

        icon_path = str(pyWallPath(folder)) + ",0"

        # Icon setting for files
        try:
            with winreg.OpenKey(key, PYWALL_REG_FILE_ICON_KEY, 0, winreg.KEY_WRITE) as pywall_key_handle:
                winreg.SetValueEx(pywall_key_handle, 'Icon', 0, winreg.REG_SZ, icon_path)
        except FileNotFoundError:
            msg = f"Registry key {PYWALL_REG_FILE_ICON_KEY} not found. Cannot set file icon."
            actionLogger(msg) # Use actionLogger for less severe, potentially expected issues
            logException(FileNotFoundError(msg), msg) # Log with exception type
        except PermissionError as pe:
            msg = f"Permission denied for registry key {PYWALL_REG_FILE_ICON_KEY} (file icon)."
            actionLogger(msg)
            logException(pe, msg)
        except OSError as oe:
            msg = f"OSError for registry key {PYWALL_REG_FILE_ICON_KEY} (file icon): {oe}"
            actionLogger(msg)
            logException(oe, msg)
        except Exception as e:
            msg = f"Unexpected error for registry key {PYWALL_REG_FILE_ICON_KEY} (file icon): {e}"
            actionLogger(msg)
            logException(e, msg)

        # Icon setting for folders
        try:
            with winreg.OpenKey(key, PYWALL_REG_FOLDER_ICON_KEY, 0, winreg.KEY_WRITE) as pywall_folder_key_handle:
                winreg.SetValueEx(pywall_folder_key_handle, 'Icon', 0, winreg.REG_SZ, icon_path)
        except FileNotFoundError:
            msg = f"Registry key {PYWALL_REG_FOLDER_ICON_KEY} not found. Cannot set folder icon."
            actionLogger(msg)
            logException(FileNotFoundError(msg), msg)
        except PermissionError as pe:
            msg = f"Permission denied for registry key {PYWALL_REG_FOLDER_ICON_KEY} (folder icon)."
            actionLogger(msg)
            logException(pe, msg)
        except OSError as oe:
            msg = f"OSError for registry key {PYWALL_REG_FOLDER_ICON_KEY} (folder icon): {oe}"
            actionLogger(msg)
            logException(oe, msg)
        except Exception as e:
            msg = f"Unexpected error for registry key {PYWALL_REG_FOLDER_ICON_KEY} (folder icon): {e}"
            actionLogger(msg)
            logException(e, msg)

        # Modifying command sub_keys
        for reg_path in sub_keys_to_modify:
            try:
                # Open with write access, ensure key exists or handle FileNotFoundError
                with winreg.OpenKey(key, reg_path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as sub_key_handle:
                    current_value, reg_type = winreg.QueryValueEx(sub_key_handle, None) # Read default value

                    if reg_type != winreg.REG_SZ:
                        msg = f"Registry value for {reg_path} is not REG_SZ. Skipping modification."
                        actionLogger(msg)
                        continue

                    if ' -c ' not in current_value:
                        msg = f"Registry value for {reg_path} does not contain ' -c '. Skipping modification."
                        actionLogger(msg)
                        continue

                    arg_index = current_value.index(" -c ")

                    modified_value = current_value.replace(
                        r"([' '.join(sys.argv[1:]) ],'", ",").replace("')\"", ",")

                    # Validate semicolon positions before slicing
                    semicolon_indices = [i for i, char in enumerate(modified_value) if char == ';']
                    if len(semicolon_indices) < 3:
                        msg = f"Malformed registry value (not enough semicolons) for {reg_path}. Value: '{modified_value}'. Skipping."
                        actionLogger(msg)
                        continue

                    thirdSemi_idx = semicolon_indices[2]

                    replacement_value = modified_value[:arg_index + 4] + modified_value[thirdSemi_idx + 1:]
                    winreg.SetValueEx(sub_key_handle, None, 0, winreg.REG_SZ, replacement_value)

            except FileNotFoundError:
                msg = f"Command registry key {reg_path} not found. Cannot update."
                actionLogger(msg)
                logException(FileNotFoundError(msg), msg)
            except PermissionError as pe:
                msg = f"Permission denied for command registry key: {reg_path}."
                actionLogger(msg)
                logException(pe, msg)
            except ValueError as ve:
                msg = f"ValueError processing registry key {reg_path} (e.g., substring not found): {ve}."
                actionLogger(msg)
                logException(ve, msg)
            except OSError as oe:
                msg = f"OSError for command registry key {reg_path}: {oe}."
                actionLogger(msg)
                logException(oe, msg)
            except Exception as e:
                msg = f"Unexpected error for command registry key {reg_path}: {e}."
                actionLogger(msg)
                logException(e, msg)

    except FileNotFoundError as fnfe_outer:
        # This would likely be from getFolder() if it raised instead of returning None and printing
        msg = f"Outer FileNotFoundError in updateRegistry (likely from getFolder): {fnfe_outer}"
        actionLogger(msg) # Or print if actionLogger itself failed to load
        logException(fnfe_outer, msg)
    except PermissionError as pe_outer:
        msg = f"Outer PermissionError in updateRegistry: {pe_outer}"
        actionLogger(msg)
        logException(pe_outer, msg)
    except OSError as oe_outer:
        msg = f"Outer OSError in updateRegistry: {oe_outer}"
        actionLogger(msg)
        logException(oe_outer, msg)
    except Exception as e_outer: # Catch-all for the entire updateRegistry function
        msg = f"A major unexpected error occurred in updateRegistry: {e_outer}"
        actionLogger(msg) # Or print as last resort
        logException(e_outer, msg)


def removeInternetAccessMenu():
    menus.removeMenu('PyWall', type='FILES')
    menus.removeMenu("PyWall", type="DIRECTORY")
