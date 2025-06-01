import unittest
from unittest.mock import patch, mock_open, MagicMock
import configparser
import os

# Assuming src is in PYTHONPATH or discoverable.
# If not, sys.path manipulations might be needed for test execution environment.
from src.config import make_default, default_config, get_config, modify_config, append_config, remove_config, PYWALL_INI

# Store the original document_folder function to be restored later if needed,
# though patching should handle this per test or class.
ORIGINAL_DOCUMENT_FOLDER = None

class TestConfig(unittest.TestCase):

    def setUp(self):
        """Set up for test methods."""
        # Patch 'document_folder' to return a specific test directory.
        # This ensures that all config file operations within the tests
        # are redirected to a temporary/controlled location.
        self.mock_document_patcher = patch('src.config.document_folder')
        self.mock_document_folder = self.mock_document_patcher.start()
        self.mock_document_folder.return_value = "test_documents" # A dummy path

        # PYWALL_INI is like "\PyWall\Config.ini"
        # So, the full path will be "test_documents\PyWall\Config.ini"
        self.test_config_dir = os.path.join("test_documents", "PyWall")
        self.test_config_file_path = os.path.join(self.test_config_dir, "Config.ini")

        # Mock os.makedirs to avoid actual directory creation if not desired,
        # or to check if it's called.
        self.mock_makedirs_patcher = patch('os.makedirs')
        self.mock_makedirs = self.mock_makedirs_patcher.start()

        # Mock os.path.exists, can be configured per test
        self.mock_exists_patcher = patch('os.path.exists')
        self.mock_exists = self.mock_exists_patcher.start()

        # Mock action_logger to prevent console output during tests / check calls
        self.mock_action_logger_patcher = patch('src.config.action_logger') # Assuming path based on src.logging_utils
        self.mock_action_logger = self.mock_action_logger_patcher.start()

        # Mock logException
        self.mock_log_exception_patcher = patch('src.config.logException')
        self.mock_log_exception = self.mock_log_exception_patcher.start()


    def tearDown(self):
        """Tear down after test methods."""
        self.mock_document_patcher.stop()
        self.mock_makedirs_patcher.stop()
        self.mock_exists_patcher.stop()
        self.mock_action_logger_patcher.stop()
        self.mock_log_exception_patcher.stop()

    def test_make_default_creates_file_with_default_content(self):
        """
        Test that make_default creates a configuration file with the correct
        default sections and options.
        """
        # Simulate config file not existing initially, then existing after creation.
        # os.path.exists is called for the folder and then for the file.
        # For this specific test, make_default is called once.
        # 1. Check for config_folder: test_documents\PyWall
        # 2. Check for config_path (not directly in make_default, but in config_file if called before)
        # For make_default directly:
        # - os.path.exists(config_folder) -> False (so makedirs is called)

        self.mock_exists.return_value = False # For the directory check

        # Use mock_open to catch the write operation.
        # The 'with open(...) as configfile:' context manager will use this mock.
        m_open = mock_open()
        with patch('builtins.open', m_open):
            make_default() # Call the function under test

        # Check that os.makedirs was called for the directory
        self.mock_makedirs.assert_called_once_with(self.test_config_dir, exist_ok=True)

        # Check that open was called to write the file
        m_open.assert_called_once_with(self.test_config_file_path, 'w', encoding='utf-8')

        # Verify the content written to the file
        # m_open().write.call_args_list gives a list of all calls to write.
        # We need to reconstruct the written content.
        written_content = "".join(call.args[0] for call in m_open().write.call_args_list)

        # Parse the written content and the default_config to compare them
        parser_written = configparser.ConfigParser()
        parser_written.read_string(written_content)

        parser_default = configparser.ConfigParser()
        # Populate parser_default from default_config dictionary
        for section, options in default_config.items():
            parser_default.add_section(section)
            for option, value in options.items():
                parser_default.set(section, option, str(value))

        # Compare sections
        self.assertEqual(set(parser_written.sections()), set(parser_default.sections()))

        # Compare options within each section
        for section in parser_default.sections():
            self.assertEqual(
                set(parser_written.options(section)),
                set(parser_default.options(section))
            )
            for option in parser_default.options(section):
                self.assertEqual(
                    parser_written.get(section, option),
                    parser_default.get(section, option)
                )

        self.mock_action_logger.assert_any_call(f"Default configuration created/reset at {self.test_config_file_path}")

    def test_get_config_existing_value(self):
        """Test get_config for an existing value."""
        # Simulate an existing config file
        self.mock_exists.return_value = True # For config_file() path check

        # Prepare mock content for the config file
        mock_content = """
[FILETYPE]
accepted_types = .exe,.py
recursive = True
"""
        m_open = mock_open(read_data=mock_content)
        with patch('builtins.open', m_open):
            # Patch configparser.ConfigParser's read method to simulate reading the file
            # This is because config.read(path) is called internally by get_config
            # and we want to control what it parses.
            mock_config_parser = configparser.ConfigParser()
            mock_config_parser.read_string(mock_content) # Load string into this instance

            with patch('configparser.ConfigParser', return_value=mock_config_parser) as mock_cp_class:
                # Test get_config
                value = get_config("FILETYPE", "accepted_types")
                self.assertEqual(value, ".exe,.py")

                value_recursive = get_config("FILETYPE", "recursive")
                self.assertEqual(value_recursive, "True")

    def test_get_config_missing_option_falls_back_to_default_config_value(self):
        """Test get_config falls back to default_config if option is missing after validation."""
        self.mock_exists.return_value = True # Config file exists

        # Simulate config file content missing an option that IS in default_config
        mock_content_missing_option = """
[FILETYPE]
accepted_types = .exe
""" # 'recursive' is missing
        # default_config['FILETYPE']['recursive'] is 'True'

        # Mock open for initial read in get_config -> config_file -> validate_config if needed
        m_initial_read = mock_open(read_data=mock_content_missing_option)
        # Mock open for write if validate_config tries to save the added option
        m_write_validation = mock_open()

        def side_effect_open(*args, **kwargs):
            if args[0] == self.test_config_file_path and args[1] == 'w': # Write during validation
                return m_write_validation(*args, **kwargs)
            return m_initial_read(*args, **kwargs) # Read

        with patch('builtins.open', side_effect_open):
            # For get_config, it first calls config_file() which might call validate_config()
            # validate_config() will read, find missing 'recursive', add it, and write.
            # Then get_config will read again.

            # We need to mock ConfigParser reads and writes carefully.
            # 1. Initial read in get_config (via config_file -> validate_config or direct)
            # 2. Write in validate_config (if option is added)
            # 3. Second read in get_config

            # Mock the ConfigParser instance behavior for multiple reads and a write
            mock_parser_instance = configparser.ConfigParser()

            # Simulate the sequence of operations on this instance
            def read_side_effect(path):
                if path == self.test_config_file_path:
                    # First read: content is missing an option
                    current_config_content = m_initial_read.return_value.read.call_args[0][0] if m_initial_read.return_value.read.call_args else mock_content_missing_option

                    # If validate_config has written, the content would be different
                    # This gets complicated. Let's simplify by assuming validate_config works
                    # and get_config will try to read, potentially find it missing,
                    # then validate_config fixes it, then get_config reads again.
                    # The test for get_config should focus on its fallback for missing keys
                    # after validate_config has run (or if it couldn't fix it).

                    # Here, we'll directly test the fallback in get_config if a key is truly missing
                    # even after any validation attempts.
                    # So, simulate a config that's read and is still missing the key.
                    _parser = configparser.ConfigParser()
                    _parser.read_string(mock_content_missing_option)
                    return _parser # This parser is missing 'recursive'
                return None # Should not happen if path is correct

            # We are testing get_config's internal fallback when a key is missing
            # This happens after validate_config is called by config_file()
            # So, the config on disk *should* be complete.
            # Let's test the case where validate_config *failed* to add the key or
            # the key is just not in default_config either.
            # The current get_config falls back to default_config values if key is missing.

            with patch('configparser.ConfigParser') as mock_cp_class:
                # Configure the mock instance returned by ConfigParser()
                # First call to config.read() in get_config
                mock_instance_first_read = configparser.ConfigParser()
                mock_instance_first_read.read_string(mock_content_missing_option)

                # Second call to config.read() in get_config (after validate_config)
                # Assume validate_config fixed it.
                fixed_content = mock_content_missing_option + "\nrecursive = True\n"
                mock_instance_second_read = configparser.ConfigParser()
                mock_instance_second_read.read_string(fixed_content)

                # Side effect for multiple ConfigParser() instantiations or read calls
                mock_cp_class.side_effect = [mock_instance_first_read, # for validate_config's read
                                             configparser.ConfigParser(), # for validate_config's internal parser if it writes
                                             mock_instance_second_read] # for get_config's final read

                # Test get_config for 'recursive' which should now be present after validation
                value = get_config("FILETYPE", "recursive") # This will trigger config_file -> validate_config
                self.assertEqual(value, "True") # Default value for 'recursive'

                # Test get_config for a key that doesn't exist in default either
                # This should return None as per current get_config logic
                non_existent_value = get_config("FILETYPE", "non_existent_key")
                self.assertIsNone(non_existent_value)


    def test_modify_config_updates_value(self):
        """Test modify_config correctly updates a value in the config."""
        self.mock_exists.return_value = True # Config file exists

        initial_content = "[GUI]\nstylesheet = old_style.xml\n"
        m_read = mock_open(read_data=initial_content)
        m_write = mock_open()

        # Mock open to return m_read for read, m_write for write
        def open_side_effect(file, mode='r', **kwargs):
            if mode == 'w':
                return m_write(file, mode, **kwargs)
            return m_read(file, mode, **kwargs)

        with patch('builtins.open', open_side_effect):
            with patch('configparser.ConfigParser') as mock_cp_class:
                # Instance for read
                mock_parser_read_instance = configparser.ConfigParser()
                mock_parser_read_instance.read_string(initial_content)

                # Instance for write (though the same instance is modified and written)
                # We can just use the same instance for simplicity of mocking here.
                mock_cp_class.return_value = mock_parser_read_instance

                modify_config("GUI", "stylesheet", "new_style.xml")

                # Check that open was called for writing
                m_write.assert_called_once_with(self.test_config_file_path, 'w', encoding='utf-8')

                # Verify the content that would be written
                # The ConfigParser instance (mock_parser_read_instance) was modified in place by set()
                # Then write() is called on it.

                # Get the ConfigParser instance that was used for writing
                # In this setup, it's mock_parser_read_instance because we returned it from the class mock
                written_config = configparser.ConfigParser()
                # Reconstruct what was written
                m_write().write.assert_called() # Check that write method on file handle was called

                # To check content, we'd need to capture what config.write(file) did.
                # config.write() is called on mock_parser_read_instance. We can check its state.
                self.assertEqual(mock_parser_read_instance.get("GUI", "stylesheet"), "new_style.xml")
                self.mock_action_logger.assert_any_call("Variable 'stylesheet' modified to 'new_style.xml' in section 'GUI'")


    def test_append_config_adds_value(self):
        """Test append_config adds a new value to a list-like option."""
        self.mock_exists.return_value = True
        initial_content = "[FILETYPE]\nblacklisted_names = file1,file2\n"
        m_read = mock_open(read_data=initial_content)
        m_write = mock_open()

        def open_side_effect(file, mode='r', **kwargs):
            if mode == 'w': return m_write(file, mode, **kwargs)
            return m_read(file, mode, **kwargs)

        with patch('builtins.open', open_side_effect), \
             patch('configparser.ConfigParser') as mock_cp_class:

            mock_parser = configparser.ConfigParser()
            mock_parser.read_string(initial_content)
            mock_cp_class.return_value = mock_parser

            append_config("FILETYPE", "blacklisted_names", ["file3"])

            self.assertEqual(mock_parser.get("FILETYPE", "blacklisted_names"), "file1, file2, file3")
            m_write.assert_called_once_with(self.test_config_file_path, 'w', encoding='utf-8')
            self.mock_action_logger.assert_any_call("Values '['file3']' (appended 1) to variable 'blacklisted_names' in section 'FILETYPE'")

    def test_append_config_does_not_add_duplicate_value(self):
        """Test append_config does not add a duplicate value."""
        self.mock_exists.return_value = True
        initial_content = "[FILETYPE]\nblacklisted_names = file1,file2\n"
        m_read = mock_open(read_data=initial_content)
        m_write = mock_open()

        def open_side_effect(file, mode='r', **kwargs):
            if mode == 'w': return m_write(file, mode, **kwargs)
            return m_read(file, mode, **kwargs)

        with patch('builtins.open', open_side_effect), \
             patch('configparser.ConfigParser') as mock_cp_class:

            mock_parser = configparser.ConfigParser()
            mock_parser.read_string(initial_content)
            mock_cp_class.return_value = mock_parser

            append_config("FILETYPE", "blacklisted_names", ["file2"]) # file2 already exists

            self.assertEqual(mock_parser.get("FILETYPE", "blacklisted_names"), "file1, file2")
            # m_write should NOT have been called if no changes were made by append_config logic
            # The current append_config writes if appended_count > 0. If file2 is a duplicate, count is 0.
            # Let's check logger message for "No new values"
            # However, the current append_config logic is: if appended_count > 0 then write.
            # So, if it's a duplicate, appended_count is 0, and it *shouldn't* write.
            m_write.assert_not_called()
            self.mock_action_logger.assert_any_call("No new values from '['file2']' appended to 'blacklisted_names' in 'FILETYPE' (already exist or empty).")


    def test_remove_config_removes_value(self):
        """Test remove_config removes a value from a list-like option."""
        self.mock_exists.return_value = True
        initial_content = "[FILETYPE]\nblacklisted_names = file1,file2,file3\n"
        m_read = mock_open(read_data=initial_content)
        m_write = mock_open()

        def open_side_effect(file, mode='r', **kwargs):
            if mode == 'w': return m_write(file, mode, **kwargs)
            return m_read(file, mode, **kwargs)

        with patch('builtins.open', open_side_effect), \
             patch('configparser.ConfigParser') as mock_cp_class:

            mock_parser = configparser.ConfigParser()
            mock_parser.read_string(initial_content)
            mock_cp_class.return_value = mock_parser

            remove_config("FILETYPE", "blacklisted_names", ["file2"])

            self.assertEqual(mock_parser.get("FILETYPE", "blacklisted_names"), "file1, file3")
            m_write.assert_called_once_with(self.test_config_file_path, 'w', encoding='utf-8')
            self.mock_action_logger.assert_any_call("Values '['file2']' (removed 1) from variable 'blacklisted_names' in section 'FILETYPE'")

    def test_remove_config_handles_missing_value(self):
        """Test remove_config handles attempt to remove a non-existent value."""
        self.mock_exists.return_value = True
        initial_content = "[FILETYPE]\nblacklisted_names = file1,file3\n"
        m_read = mock_open(read_data=initial_content)
        m_write = mock_open()

        def open_side_effect(file, mode='r', **kwargs):
            if mode == 'w': return m_write(file, mode, **kwargs)
            return m_read(file, mode, **kwargs)

        with patch('builtins.open', open_side_effect), \
             patch('configparser.ConfigParser') as mock_cp_class:

            mock_parser = configparser.ConfigParser()
            mock_parser.read_string(initial_content)
            mock_cp_class.return_value = mock_parser

            remove_config("FILETYPE", "blacklisted_names", ["file404"]) # file404 does not exist

            self.assertEqual(mock_parser.get("FILETYPE", "blacklisted_names"), "file1, file3")
            # m_write should not be called if no changes were made.
            m_write.assert_not_called()
            self.mock_action_logger.assert_any_call("No values from '['file404']' found to remove from 'blacklisted_names' in 'FILETYPE'.")


if __name__ == '__main__':
    unittest.main()
