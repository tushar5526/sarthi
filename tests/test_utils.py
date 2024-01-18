import pathlib

import pytest

from server.utils import ComposeHelper


# Compose Helper Tests
def test_verify_project_hash_format(deployment_config):
    # When
    project_hash = deployment_config.get_project_hash()

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


# Nginx Helper Tests
def test_find_free_port_pass(nginx_helper, mocker):
    # Given
    mock_socket = mocker.patch("server.utils.socket.socket")
    mock_socket.return_value.__enter__.return_value.connect.side_effect = (
        ConnectionRefusedError
    )

    # When
    port = nginx_helper.find_free_port()

    # Then
    assert isinstance(port, str)


def test_find_free_port_fails(nginx_helper, mocker):
    # Given
    mocker.patch("server.utils.socket.socket")

    # Then
    with pytest.raises(
        RuntimeError, match="Could not find a free port in the specified range"
    ):
        # When
        nginx_helper.find_free_port()


def test_generate_outer_proxy_conf_file(nginx_helper, mocker):
    # Given
    port = "12345"
    mock_open = mocker.patch("builtins.open")
    mocker.patch.object(nginx_helper, "_test_nginx_config", return_value=True)

    # When
    conf = nginx_helper.generate_outer_proxy_conf_file(port)

    # Then
    assert (
        conf
        == """
    server {
        listen 80;
        server_name ~c7866191e5a92858.localhost;

        location / {
            proxy_pass http://host.docker.internal:12345;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
    """
    )
    mock_open.assert_called_with(
        "/path/to/outer/conf/test-project-name-c7866191e5a92858.conf", "w"
    )


def test_generate_project_proxy_conf_file(nginx_helper, mocker):
    # Given
    services = {
        "service1": [(1000, 2000)],
        "service2": [(2000, 3000)],
    }
    mocker.patch("builtins.open")

    # When
    proxy_conf_path, urls = nginx_helper.generate_project_proxy_conf_file(services)

    # Then
    assert (
        proxy_conf_path
        == "/path/to/deployment/project/test-project-name-c7866191e5a92858.conf"
    )
    assert urls == [
        "http://test-project-name-test-branch-name-1000-c7866191e5a92858.localhost",
        "http://test-project-name-test-branch-name-2000-c7866191e5a92858.localhost",
    ]


def test_test_nginx_config(nginx_helper, mocker):
    # Given
    mocked_run = mocker.patch("subprocess.run")

    # When
    nginx_helper._test_nginx_config()

    # Then
    mocked_run.assert_called_with(
        ["docker", "exec", "sarthi_nginx", "nginx", "-t"],
        check=True,
        capture_output=True,
        text=True,
    )


def test_reload_nginx(nginx_helper, mocker):
    # Given
    mocked_run = mocker.patch("subprocess.run")

    # When
    nginx_helper.reload_nginx()

    # Then
    mocked_run.assert_called_with(
        ["docker", "exec", "sarthi_nginx", "nginx", "-s", "reload"], check=True
    )


def test_remove_outer_proxy(nginx_helper, mocker):
    # Given
    mocker.patch("os.path.exists", return_value=True)
    mock_remove = mocker.patch("os.remove")

    # When
    nginx_helper.remove_outer_proxy()

    # Then
    mock_remove.assert_called_with(
        "/path/to/outer/conf/test-project-name-c7866191e5a92858.conf"
    )


def test_remove_outer_proxy_when_file_is_deleted_already(nginx_helper, mocker):
    mocker.patch("os.path.exists", return_value=False)
    mocker.patch("os.remove", side_effect=FileNotFoundError)

    # When
    nginx_helper.remove_outer_proxy()

    # Then No error should be raised
