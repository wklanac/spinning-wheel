import pytest
from assertpy import assert_that
from unittest.mock import patch, mock_open

from spinning_wheel.spinning_wheel import spinning_wheel_entrypoint, get_local_file_text, get_git_file_text


@pytest.fixture
def sample_user_source():
    return """
def set_secret():
    print("secret set")

def test_secret():
    print("secret tested")
"""


@pytest.fixture
def sample_lambda_template():
    return """


import boto3
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    pass
    
def create_secret():
    pass
    
def set_secret():
    pass
    
def test_secret():
    pass
"""


class TestSpinningWheelEntrypoint:
    @patch("spinning_wheel.spinning_wheel.get_local_file_text")
    @patch("spinning_wheel.spinning_wheel.get_git_file_text")
    @patch("spinning_wheel.spinning_wheel.open", new_callable=mock_open)
    def test_spinning_wheel_entrypoint(self, mock_file, mock_git_file, mock_local_file, sample_user_source,
                                       sample_lambda_template):
        mock_local_file.return_value = sample_user_source
        mock_git_file.return_value = sample_lambda_template

        spinning_wheel_entrypoint("user_source.py", "output.py")

        mock_local_file.assert_called_once_with("user_source.py")
        mock_git_file.assert_called_once()
        mock_file.assert_called_once_with("output.py", "w")
        mock_file().write.assert_called_once()

        written_content = mock_file().write.call_args[0][0]
        assert_that(written_content).contains("def set_secret():\n    print('secret set')")
        assert_that(written_content).contains("def test_secret():\n    print('secret tested')")
        assert_that(written_content).contains("def lambda_handler(event, context):")
        assert_that(written_content).contains("def create_secret():")


class TestGetLocalFileText:
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="file content")
    def test_get_local_file_text_success(self, mock_file, mock_exists):
        mock_exists.return_value = True
        result = get_local_file_text("test.py")
        assert_that(result).is_equal_to("file content")
        mock_exists.assert_called_once_with("test.py")
        mock_file.assert_called_once_with("test.py", "r")

    @patch("os.path.exists")
    def test_get_local_file_text_file_not_found(self, mock_exists):
        mock_exists.return_value = False
        with pytest.raises(ValueError) as excinfo:
            get_local_file_text("nonexistent.py")
        assert_that(str(excinfo.value)).contains("User source file expected at path")


class TestGetGitFileText:
    @patch("git.Repo.clone_from")
    @patch("os.walk")
    @patch("builtins.open", new_callable=mock_open, read_data="git file content")
    def test_get_git_file_text_success(self, mock_file, mock_walk, mock_clone):
        mock_repo = mock_clone.return_value
        mock_walk.return_value = [
            ("/tmp/repo/SecretsManagerRotationTemplate", [], ["lambda_function.py"])
        ]

        result = get_git_file_text(
            "https://example.com/repo.git",
            "SecretsManagerRotationTemplate",
            "lambda_function.py",
            "commit123"
        )

        assert_that(result).is_equal_to("git file content")
        mock_clone.assert_called_once()
        mock_repo.git.checkout.assert_called_once_with("commit123")
        mock_walk.assert_called_once()
        mock_file.assert_called_once()

    @patch("git.Repo.clone_from")
    @patch("os.walk")
    def test_get_git_file_text_file_not_found(self, mock_walk, mock_clone):
        mock_walk.return_value = [("/tmp/repo", [], ["other_file.py"])]

        with pytest.raises(RuntimeError) as excinfo:
            get_git_file_text(
                "https://example.com/repo.git",
                "NonexistentDirectory",
                "nonexistent_file.py"
            )

        assert_that(str(excinfo.value)).contains("Cannot locate file")
