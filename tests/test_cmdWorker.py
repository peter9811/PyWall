import unittest
from unittest.mock import MagicMock, patch
import pathlib # For creating mock Path objects if needed

# Assuming src is in PYTHONPATH or discoverable
from src.cmdWorker import _validate_rule_type, _build_firewall_command
# We might need to mock items from src.logger or src.shellHandler if _validate_rule_type calls them for errors
# For now, _validate_rule_type's pop call is from src.shellHandler

class TestCmdWorkerHelpers(unittest.TestCase):

    @patch('src.cmdWorker.pop') # Mocks the pop function from src.shellHandler via src.cmdWorker's import
    @patch('src.cmdWorker.actionLogger') # Mocks actionLogger
    def test_validate_rule_type(self, mock_action_logger, mock_pop):
        """Test _validate_rule_type with valid and invalid inputs."""
        self.assertTrue(_validate_rule_type("in"))
        self.assertTrue(_validate_rule_type("out"))
        self.assertTrue(_validate_rule_type("both"))

        self.assertFalse(_validate_rule_type("invalid_type"))
        mock_pop.assert_called_once() # Ensure pop was called for the invalid type
        mock_action_logger.assert_called_with("Invalid rule type received: invalid_type")

        # Reset mocks for next invalid check if needed, or ensure calls are distinct
        mock_pop.reset_mock()
        mock_action_logger.reset_mock()
        self.assertFalse(_validate_rule_type("other_invalid"))
        mock_pop.assert_called_once()
        mock_action_logger.assert_called_with("Invalid rule type received: other_invalid")


    @patch('src.cmdWorker.actionLogger') # Mocks actionLogger
    def test_build_firewall_command_deny(self, mock_action_logger):
        """Test _build_firewall_command for 'deny' action."""
        mock_file_path = MagicMock(spec=pathlib.Path)
        mock_file_path.stem = "test_app"
        # Configure __str__ if the function casts file_path to string directly
        mock_file_path.__str__.return_value = "C:\\path\\to\\test_app.exe"

        # Test deny 'in'
        expected_cmd_deny_in = '@echo off && netsh advfirewall firewall add rule name="PyWall blocked test_app" dir=in program="C:\\path\\to\\test_app.exe" action=block'
        self.assertEqual(_build_firewall_command("deny", "in", mock_file_path), expected_cmd_deny_in)

        # Test deny 'out'
        expected_cmd_deny_out = '@echo off && netsh advfirewall firewall add rule name="PyWall blocked test_app" dir=out program="C:\\path\\to\\test_app.exe" action=block'
        self.assertEqual(_build_firewall_command("deny", "out", mock_file_path), expected_cmd_deny_out)

        # Note: _build_firewall_command currently doesn't directly handle "both".
        # The calling function access_handler handles "both" by calling _build_firewall_command twice.
        # So, we don't test "both" directly here for command string generation.

    @patch('src.cmdWorker.actionLogger') # Mocks actionLogger
    def test_build_firewall_command_allow(self, mock_action_logger):
        """Test _build_firewall_command for 'allow' action."""
        mock_file_path = MagicMock(spec=pathlib.Path)
        mock_file_path.stem = "test_app"
        mock_file_path.__str__.return_value = "C:\\path\\to\\test_app.exe"

        # Test allow 'in'
        expected_cmd_allow_in = '@echo off && netsh advfirewall firewall delete rule name="PyWall blocked test_app" dir=in program="C:\\path\\to\\test_app.exe"'
        self.assertEqual(_build_firewall_command("allow", "in", mock_file_path), expected_cmd_allow_in)

        # Test allow 'out'
        expected_cmd_allow_out = '@echo off && netsh advfirewall firewall delete rule name="PyWall blocked test_app" dir=out program="C:\\path\\to\\test_app.exe"'
        self.assertEqual(_build_firewall_command("allow", "out", mock_file_path), expected_cmd_allow_out)

    @patch('src.cmdWorker.actionLogger')
    def test_build_firewall_command_invalid_action(self, mock_action_logger):
        """Test _build_firewall_command for an invalid action."""
        mock_file_path = MagicMock(spec=pathlib.Path)
        mock_file_path.stem = "test_app"
        mock_file_path.__str__.return_value = "C:\\path\\to\\test_app.exe"

        self.assertIsNone(_build_firewall_command("invalid_action", "in", mock_file_path))
        mock_action_logger.assert_called_with("Invalid action 'invalid_action' for building command for test_app.exe")


if __name__ == '__main__':
    unittest.main()
