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
    services = compose_helper._compose["services"]

    # Deployment Proxy should be added in compose file
    is_deployment_proxy_service = False

    for service_name, service_config in services.items():
        is_deployment_proxy_service = (
            is_deployment_proxy_service
            or service_name == f"nginx_{deployment_namespace}"
        )

        assert (
            "ports" not in service_config or is_deployment_proxy_service
        ), f"Ports mapping should not be present in {service_name}"

        assert (
            "container_name" not in service_config
        ), f"Container Name should not be present in {service_name}"

        assert "restart" in service_config, f"Restart clause missing in {service_name}"

        assert (
            service_config["restart"] == "always"
        ), f"Incorrect restart policy in {service_name}"

    assert (
        is_deployment_proxy_service
    ), "Deployment (Nginx) Proxy is missing in processed services"

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


def test_write_compose_file(compose_helper, mocker):
    # Given
    conf_file_path = "conf-file-path/some-nginx.conf"
    deployment_namespace = "deployment-namespace"
    mocker.patch("subprocess.run")
    mock_yaml_dump = mocker.patch("server.utils.yaml.dump")

    # When
    compose_helper.start_services(5000, conf_file_path, deployment_namespace)

    # Then
    assert mock_yaml_dump.called_once()
