import pathlib

from server.utils import ComposeHelper, DeploymentConfig


def test_verify_project_hash_format():
    # Given
    config = DeploymentConfig(
        project_name="test-project-name",
        branch_name="test-branch-name",
        project_git_url="https://github.com/tushar5526/test-project-name.git",
    )
    # When
    project_hash = config.get_project_hash()

    # Then
    assert type(project_hash) == str
    assert len(project_hash) == 16


def test_dont_load_compose_file_in_compose_helper():
    compose_helper = ComposeHelper("random-compose.yml", load_compose_file=False)
    assert getattr(compose_helper, "_compose") is None


def test_start_services(compose_helper, mocker):
    # Given
    mocked_run = mocker.patch("subprocess.run")

    conf_file_path = "conf-file-path/some-nginx.conf"
    deployment_namespace = "deployment-namespace"

    # When
    compose_helper.start_services(5000, conf_file_path, deployment_namespace)

    # Then
    # Processed compose file should be updated with following rules
    # - No ports
    # - No container_name
    # - Restart should be present in each service
    for service in compose_helper._compose["services"]:
        if (
            "ports" in compose_helper._compose["services"][service]
            and service != f"nginx_{deployment_namespace}"
        ):
            assert False, "Ports mapping present in processed compose file"
        if "container_name" in compose_helper._compose["services"][service]:
            assert False, "Container Name present in processed compose file"
        if "restart" not in compose_helper._compose["services"][service]:
            assert False, "Restart clause missing in processed compose file"
        assert compose_helper._compose["services"][service]["restart"] == "always"

    mocked_run.assert_called_once_with(
        ["docker-compose", "up", "-d", "--build"], check=True, cwd=pathlib.Path(".")
    )


def test_remove_services(compose_helper, mocker):
    mocked_run = mocker.patch("subprocess.run")
    compose_helper.remove_services()
    mocked_run.assert_called_once_with(
        ["docker-compose", "down", "-v"], check=True, cwd=pathlib.Path(".")
    )


def test_get_service_ports_config(compose_helper):
    service_config = {
        "webapp": [("8080", "80")],
        "database": [],
        "redis": [("6379", "6379")],
        "messaging": [("5672", "5672"), ("15672", "15672")],
        "api": [("3000", "3000")],
        "python_app": [],
        "mongo_db": [("27017", "27017")],
    }
    assert compose_helper.get_service_ports_config() == service_config
