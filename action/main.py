import os
import sys
import typing


def main(args: typing.List[str]) -> None:
    """main function

    Args:
        args: STDIN arguments
    """
    # GITHUB_REPOSITORY : octocat/Hello-World
    project_name = os.environ.get("GITHUB_REPOSITORY").split("/")[1]
    branch_name = os.environ.get("GITHUB_HEAD_REF")
    username = os.environ.get("INPUT_REMOTE_USER")
    password = os.environ.get("INPUT_REMOTE_PASSWORD")
    host = os.environ.get("INPUT_REMOTE_HOST")
    port = os.environ.get("INPUT_PORT") or 22
    deployment_domain = os.environ.get("INPUT_DEPLOYMENT_DOMAIN")


if __name__ == "__main__":
    main(sys.argv)
