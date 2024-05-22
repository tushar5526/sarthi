import pathlib
from unittest.mock import MagicMock, call, patch

import pytest
import requests
from fastapi import HTTPException

from server import constants
from server.utils import ComposeHelper, DeploymentConfig


# Compose Helper Tests
def test_verify_project_hash_format(deployment_config):
    # When
    project_hash = deployment_config.get_project_hash()

    # Then
    assert type(project_hash) == str
    assert len(project_hash) == 10


def test_dont_load_compose_file_in_compose_helper():
    compose_helper = ComposeHelper("random-compose.yml", load_compose_file=False)
    assert getattr(compose_helper, "_compose") is None


def test_start_services_success(compose_helper, mocker):
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
        ["docker", "compose", "up", "-d", "--build"], check=True, cwd=pathlib.Path(".")
    )


def test_start_services_failure_on_processing_compose_file(compose_helper, mocker):
    # Given
    exception_msg = "Random Exception Occurred"
    mock_generate_processed_compose_file = mocker.patch.object(
        compose_helper, "_generate_processed_compose_file"
    )
    mock_generate_processed_compose_file.side_effect = Exception(exception_msg)
    conf_file_path = "conf-file-path/some-nginx.conf"
    deployment_namespace = "deployment-namespace"

    # When / Then
    with pytest.raises(HTTPException, match=exception_msg):
        compose_helper.start_services(5000, conf_file_path, deployment_namespace)


def test_start_services_failure_on_docker_compose_up(compose_helper, mocker):
    # Given
    mocked_run = mocker.patch("subprocess.run")
    mocked_run.side_effect = Exception("Random error")

    conf_file_path = "conf-file-path/some-nginx.conf"
    deployment_namespace = "deployment-namespace"

    # When
    with pytest.raises(HTTPException):
        compose_helper.start_services(5000, conf_file_path, deployment_namespace)


def test_remove_services_success(compose_helper, mocker):
    # Given
    mocked_run = mocker.patch("subprocess.run")

    # When
    compose_helper.remove_services()

    # Then
    mocked_run.assert_called_once_with(
        ["docker", "compose", "down", "-v"], check=True, cwd=pathlib.Path(".")
    )


def test_remove_services_docker_compose_failure(compose_helper, mocker):
    # Given
    mocked_run = mocker.patch("subprocess.run")
    mocked_run.side_effect = Exception("Random Exception")

    # Then
    with pytest.raises(HTTPException):
        # When
        compose_helper.remove_services()


def test_remove_deleted_deployment(compose_helper):
    compose_helper._compose_file_location = "/random/random-file-location"
    msg = compose_helper.remove_services()
    assert msg


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
        HTTPException,
        match="Could not find a free port in the specified range",
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
        server_name ~5022fe75f1.localhost;

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
    mock_open.assert_called_with("/path/to/outer/conf/testprojec-5022fe75f1.conf", "w")


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
    assert proxy_conf_path == "/path/to/deployment/project/testprojec-5022fe75f1.conf"
    assert urls == [
        "http://testprojec-testbranchname-1000-5022fe75f1.localhost",
        "http://testprojec-testbranchname-2000-5022fe75f1.localhost",
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


def test_reload_nginx_success(nginx_helper, mocker):
    # Given
    mocked_run = mocker.patch("subprocess.run")

    # When
    nginx_helper.reload_nginx()

    # Then
    mocked_run.assert_called_with(
        ["docker", "exec", "sarthi_nginx", "nginx", "-s", "reload"], check=True
    )


def test_reload_nginx_failure(nginx_helper, mocker):
    # Given
    mocked_run = mocker.patch("subprocess.run")
    mocked_run.side_effect = Exception("Random Error")

    # Then
    with pytest.raises(HTTPException):
        # When
        nginx_helper.reload_nginx()

    mocked__test_nginx_config = mocker.patch.object(nginx_helper, "_test_nginx_config")
    mocked__test_nginx_config.return_value = True

    with pytest.raises(HTTPException):
        # When
        nginx_helper.reload_nginx()


def test_remove_outer_proxy(nginx_helper, mocker):
    # Given
    mocker.patch("os.path.exists", return_value=True)
    mock_remove = mocker.patch("os.remove")

    # When
    nginx_helper.remove_outer_proxy()

    # Then
    mock_remove.assert_called_with("/path/to/outer/conf/testprojec-5022fe75f1.conf")


def test_remove_outer_proxy_when_file_is_deleted_already(nginx_helper, mocker):
    mocker.patch("os.path.exists", return_value=False)
    mocker.patch("os.remove", side_effect=FileNotFoundError)

    # When
    nginx_helper.remove_outer_proxy()

    # Then No error should be raised


def test_deployment_config_repr(deployment_config):
    expected_repr = (
        "DeploymentConfig('test-project-name', 'test-branch-name', "
        "'https://github.com/tushar5526/test-project-name.git', 'docker-compose.yml', 'POST')"
    )
    assert repr(deployment_config) == expected_repr


def test_create_deployment_config_with_reserved_branch_name():
    deployment_config = DeploymentConfig(
        project_name="test-project-name",
        branch_name=constants.DEFAULT_SECRETS_PATH,
        project_git_url="https://github.com/tushar5526/test-project-name.git",
        rest_action="POST",
    )
    assert deployment_config.branch_name == "defaultdevsecrets"


def test_create_deployment_config_for_private_repos():
    deployment_config = DeploymentConfig(
        project_name="test-project-name",
        branch_name=constants.DEFAULT_SECRETS_PATH,
        project_git_url="https://github.com/tushar5526/test-project-name.git",
        rest_action="POST",
        gh_token="random-pat-token",
    )
    assert (
        deployment_config.project_git_url
        == "https://random-pat-token:@github.com/tushar5526/test-project-name.git"
    )


@patch("server.utils.os")
@patch("server.utils.requests")
def test_create_env_placeholder_with_sample_env_file(
    mock_requests, mock_os, secrets_helper_instance
):
    # Mocking necessary dependencies
    mock_os.path.exists.return_value = True
    mock_dotenv_values = MagicMock(return_value={"key": "secret-value"})
    with patch("server.utils.dotenv_values", mock_dotenv_values):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_requests.post.return_value = mock_response

        # Calling the method under test
        secrets_helper_instance._create_env_placeholder()

        # Assertions
        assert mock_requests.post.call_args_list == [
            call(
                url="http://vault:8200/v1/kv/data/project_name/default-dev-secrets",
                headers={"X-Vault-Token": "hvs.randomToken"},
                data='{"data": {"key": "secret-value"}}',
            ),
            call(
                url="http://vault:8200/v1/kv/data/project_name/branch_name",
                headers={"X-Vault-Token": "hvs.randomToken"},
                data='{"data": {"key": "secret-value"}}',
            ),
        ]
        mock_dotenv_values.assert_called()


@patch("server.utils.os")
@patch("server.utils.requests")
def test_create_env_placeholder_with_sample_env_file_missing(
    mock_requests, mock_os, secrets_helper_instance
):
    # Mocking necessary dependencies
    mock_os.path.join.return_value = "/path/to/project/.env.sample"
    mock_os.path.exists.return_value = False

    # Calling the method under test
    secrets_helper_instance._create_env_placeholder()

    # Assertions
    mock_os.path.exists.assert_called_with("/path/to/project/.env.sample")
    mock_requests.post.assert_called_with(
        url="http://vault:8200/v1/kv/data/project_name/branch_name",
        headers={"X-Vault-Token": "hvs.randomToken"},
        data='{"data": {"key": "secret-value"}}',
    )


@patch("server.utils.os")
@patch("server.utils.requests")
def test_inject_env_variables_with_secrets_found(
    mock_requests, mock_os, secrets_helper_instance
):
    # Mocking necessary dependencies
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"data": {"key": "secret-value"}}}
    mock_requests.get.return_value = mock_response
    mock_open = MagicMock()
    mock_os.path.join.return_value = "/path/to/project/.env"
    with patch("builtins.open", mock_open):
        # Calling the method under test
        secrets_helper_instance.inject_env_variables("/path/to/project")

        # Assertions
        mock_requests.get.assert_called_once_with(
            url="http://vault:8200/v1/kv/data/project_name/branch_name",
            headers={"X-Vault-Token": "hvs.randomToken"},
        )
        mock_open.assert_called_once_with("/path/to/project/.env", "w")
        # TODO: Add check for what is written
        # mock_open().write.assert_called_once_with('key="secret-value"\n')


@patch("server.utils.os")
@patch("server.utils.requests")
def test_inject_env_variables_with_no_secrets(
    mock_requests, mock_os, secrets_helper_instance
):
    # Mocking necessary dependencies
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_requests.get.return_value = mock_response
    mock_create_env_placeholder = MagicMock()
    mock_create_env_placeholder.return_value = {"key": "test"}

    with patch.object(
        secrets_helper_instance, "_create_env_placeholder", mock_create_env_placeholder
    ):
        mock_open = MagicMock()
        mock_os.path.join.return_value = "/path/to/project/.env"
        with patch("builtins.open", mock_open):
            # Calling the method under test
            secrets_helper_instance.inject_env_variables("/path/to/project")

            # Assertions
            mock_requests.get.assert_called_once_with(
                url="http://vault:8200/v1/kv/data/project_name/branch_name",
                headers={"X-Vault-Token": "hvs.randomToken"},
            )
            mock_create_env_placeholder.assert_called_once()
            mock_open.assert_called_once_with("/path/to/project/.env", "w")


@patch("server.utils.requests.delete", autospec=True)
def test_cleanup_deployment_variables_success(
    mock_requests_delete, secrets_helper_instance
):
    # Mocking necessary dependencies
    mock_response = MagicMock()
    mock_response.status_code = 204
    mock_requests_delete.return_value = mock_response

    # Calling the method under test
    result = secrets_helper_instance.cleanup_deployment_variables()

    # Assertions
    mock_requests_delete.assert_called_once_with(
        url="http://vault:8200/v1/kv/metadata/project_name/branch_name",
        headers={"X-Vault-Token": "hvs.randomToken"},
    )
    assert result.status_code == 204


@patch("server.utils.requests.delete", autospec=True)
def test_cleanup_deployment_variables_failure(
    mock_requests_delete, secrets_helper_instance
):
    # Mocking necessary dependencies
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = requests.HTTPError(
        "Internal Server Error"
    )
    mock_requests_delete.return_value = mock_response

    # Calling the method under test
    secrets_helper_instance.cleanup_deployment_variables()

    # Assertions
    mock_requests_delete.assert_called_once_with(
        url="http://vault:8200/v1/kv/metadata/project_name/branch_name",
        headers={"X-Vault-Token": "hvs.randomToken"},
    )
