import ast
import spinning_wheel.ast_extensions as ast_ext
import os
import git
from tempfile import TemporaryDirectory

_TEMPLATE_REPO_URL = (
    "https://github.com/aws-samples/aws-secrets-manager-rotation-lambdas.git"
)
_EXPECTED_DIRECTORY = "SecretsManagerRotationTemplate"
_EXPECTED_FILE = "lambda_function.py"


def spinning_wheel_entrypoint(user_source_path: str, desired_output_path: str):
    """
    Entrypoint for spinning wheel lambda secret rotation template merger.

    Provided a source path of a user's module which has methods set_secret and test_secret
    defined with the business logic for a specific secret use case, spinning wheel merges
    this module with the standard amazon template boilerplate code for a secret rotation lambda function.

    Args:
        desired_output_path: Desired output path for transformed and merged module.
        user_source_path: Source path of user supplied module

    Returns:

    """
    user_source_contents = get_local_file_text(user_source_path)
    user_module = ast.parse(user_source_contents)

    lambda_template_source_contents = get_git_file_text(
        _TEMPLATE_REPO_URL, _EXPECTED_DIRECTORY, _EXPECTED_FILE
    )
    lambda_template_module = ast.parse(lambda_template_source_contents)

    unioned_module = ast_ext.union_and_deconflict_modules(user_module, lambda_template_module)

    with open(desired_output_path, "w") as output_file:
        output_file.write(ast.unparse(unioned_module))


def get_local_file_text(file_path: str) -> str:
    """
    Get the text contents of a local file - checking first if the file exists.

    Args:
        file_path (str): Expected local file path

    Returns:
        str: Text contents of local file
    """
    if not os.path.exists(file_path):
        raise ValueError(
            f"User source file expected at path {file_path} but not found."
        )

    with open(file_path, "r") as user_source_file:
        return user_source_file.read()


def get_git_file_text(
    repo_url: str, expected_directory: str, expected_file: str
) -> str:
    """
    Get the text of a file under a specified directory in a git repository.
    Clones the repository first and uses this as a reference.

    Args:
        repo_url (str): URL for git repository to target
        expected_directory (str): Expected directory in repository
        expected_file (str): Expected file in respository to find

    Raises:
        RuntimeError: If file cannot be found in the repository

    Returns:
        str: Text contents of file
    """
    with TemporaryDirectory() as temporary_directory:
        git.Repo.clone_from(repo_url, temporary_directory)

        for root, _, files in os.walk(temporary_directory):
            if (expected_directory in root) and (expected_file in files):
                template_path = os.path.join(
                    os.path.join(temporary_directory, root), expected_file
                )

        if template_path is None:
            raise RuntimeError(
                f"Cannot locate file {expected_file} in git repository {repo_url},"
                + " expected under directory {expected_directory}"
            )

        with open(template_path, "r") as template_file:
            return template_file.read()
