import hashlib
import json
import logging
import os
import pathlib
import re
import socket
import subprocess
import typing
from dataclasses import dataclass

import requests
import yaml
from dotenv import dotenv_values
from fastapi import HTTPException

import server.constants as constants

logger = logging.getLogger(__name__)


@dataclass
class DeploymentConfig:
    project_name: str
    branch_name: str
    project_git_url: str
    compose_file_location: str = constants.COMPOSE_FILE
    rest_action: str = constants.POST

    def __post_init__(self):
        self.branch_name_raw = self.branch_name
        self.project_name_raw = self.project_name

        self.project_name = re.sub(r"[^a-zA-Z]", "", self.project_name.lower())
        self.project_name = (
            self.project_name[:10] if len(self.project_name) > 10 else self.project_name
        )
        self.branch_name = re.sub(r"[^a-zA-Z]", "", self.branch_name.lower())
        self.branch_name = (
            self.branch_name[:20] if len(self.branch_name) > 20 else self.branch_name
        )

    def get_project_hash(self):
        return get_random_stub(f"{self.project_name}:{self.branch_name}", 10)

    def __repr__(self):
        return (
            f"DeploymentConfig({self.project_name_raw=!r}, {self.branch_name_raw=!r}, {self.project_git_url=!r}, "
            f"{self.compose_file_location=!r}, {self.rest_action=!r})"
        )


class ComposeHelper:
    NGINX_SERVICE_TEMPLATE: typing.Final[
        str
    ] = """
services:
    nginx:
        image: nginx
        restart: always
        ports:
            - '%s:80'
        volumes:
            - %s:/etc/nginx/conf.d/default.conf
        networks:
            - default
    """

    def __init__(self, compose_file_location: str, load_compose_file=True):
        self._compose_file_location = compose_file_location
        self._compose = (
            load_yaml_file(self._compose_file_location) if load_compose_file else None
        )

    def start_services(
        self, nginx_port: str, conf_file_path: str, deployment_namespace: str
    ):
        try:
            self._generate_processed_compose_file(
                nginx_port, conf_file_path, deployment_namespace
            )
        except Exception as e:
            logger.error(f"Error generating processed compose file: {e}")
            raise HTTPException(500, e)

        command = ["docker-compose", "up", "-d", "--build"]
        project_dir = pathlib.Path(self._compose_file_location).parent

        try:
            subprocess.run(command, check=True, cwd=project_dir)
            logger.info("Docker Compose up -d --build executed successfully.")
        except Exception as e:
            msg = f"An unexpected error occurred while starting services: {e}"
            logger.error(msg)
            raise HTTPException(500, msg)

    def remove_services(self):
        if not os.path.exists(pathlib.Path(self._compose_file_location).parent):
            logger.info(f"{self._compose_file_location} is already deleted!")
            return
        command = ["docker-compose", "down", "-v"]
        project_dir = pathlib.Path(self._compose_file_location).parent
        try:
            subprocess.run(command, check=True, cwd=project_dir)
            logger.info("Docker Compose down -v executed successfully.")
        except Exception as e:
            msg = f"An unexpected error occurred while starting services: {e}"
            logger.error(msg)
            raise HTTPException(500, msg)

    def _generate_processed_compose_file(
        self, nginx_port: str, conf_file_path: str, deployment_namespace: str
    ):
        """
        This should ideally be called after get_service_ports_config as it will overwrite the compose file
        1. Remove ports mapping
        2. Add in a nginx config
        """
        for service in self._compose["services"]:
            if "ports" in self._compose["services"][service]:
                del self._compose["services"][service]["ports"]

            if "container_name" in self._compose["services"][service]:
                del self._compose["services"][service]["container_name"]

            self._compose["services"][service]["restart"] = "always"

        service_proxy_template = ComposeHelper.NGINX_SERVICE_TEMPLATE % (
            nginx_port,
            conf_file_path,
        )
        proxy_yaml = yaml.safe_load(service_proxy_template)

        # Add the proxy nginx to all networks, along with default
        if "networks" in self._compose:
            proxy_yaml["services"]["nginx"]["networks"].extend(
                self._compose["networks"]
            )

        self._compose["services"][f"nginx_{deployment_namespace}"] = proxy_yaml[
            "services"
        ]["nginx"]

        self._write_compose_file()

    def _write_compose_file(self):
        with open(self._compose_file_location, "w") as yaml_file:
            # Dump the data to the YAML file
            yaml.dump(self._compose, yaml_file, default_flow_style=False)

        logger.info(f"YAML data written to {self._compose_file_location} successfully.")

    def get_service_ports_config(
        self,
    ) -> typing.Dict[str, typing.List[typing.Tuple[int, int]]]:
        services = {}
        for service in self._compose["services"]:
            if service not in services:
                services[service] = []

            port_mappings = []

            if "ports" in self._compose["services"][service]:
                port_mappings = self._compose["services"][service]["ports"]

            for port_mapping in port_mappings:
                ports = port_mapping.split(":")
                services[service].append((ports[-2], ports[-1]))
        return services


class NginxHelper:
    SERVER_BLOCK_TEMPLATE: typing.Final[
        str
    ] = """
    server {
        listen 80;
        server_name %s;
        %s
    }
    """

    ROUTES_BLOCK_TEMPLATE: typing.Final[
        str
    ] = """
            location / {
                proxy_pass http://%s:%s;
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
            }
    """

    PROJECT_BLOCK_TEMPLATE: typing.Final[
        str
    ] = """
    server {
        listen 80;
        server_name %s;

        location / {
            proxy_pass http://%s:%s;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
    """

    def __init__(
        self,
        config: DeploymentConfig,
        outer_conf_base_path: str,
        deployment_project_path: str,
    ):
        self._project_name = config.project_name
        self._branch_name = config.branch_name
        self._project_hash = config.get_project_hash()
        self._port = None
        self._host_name = (
            os.environ.get("DEPLOYMENT_HOST") or constants.DOCKER_HOST_NETWORK_DOMAIN
        )
        self._start_port = (
            os.environ.get("DEPLOYMENT_PORT_START")
            or constants.DEFAULT_DEPLOYMENT_PORT_START
        )
        self._end_port = (
            os.environ.get("DEPLOYMENT_PORT_END")
            or constants.DEFAULT_DEPLOYMENT_PORT_END
        )
        self._DOMAIN_NAME = os.environ.get("DOMAIN_NAME") or constants.LOCALHOST
        self._DOCKER_INTERNAL_HOSTNAME: typing.Final[
            str
        ] = constants.DOCKER_HOST_NETWORK_DOMAIN
        self._outer_conf_base_path = outer_conf_base_path
        self._deployment_project_path = deployment_project_path
        self._conf_file_name = f"{self._project_name}-{self._project_hash}.conf"
        self._outer_proxy_path = os.path.join(
            self._outer_conf_base_path, self._conf_file_name
        )
        self._deployment_proxy_path = os.path.join(
            self._deployment_project_path, self._conf_file_name
        )

    def find_free_port(self) -> str:
        current_port = self._start_port

        while current_port <= self._end_port:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.connect((self._host_name, current_port))
                    s.close()
                    current_port += 1
                except ConnectionRefusedError:
                    self._port = current_port
                    return str(current_port)

        raise HTTPException(500, "Could not find a free port in the specified range")

    def generate_outer_proxy_conf_file(self, port: str) -> str:
        port = port or self._port
        server_name_regex = f"~{self._project_hash}.{self._DOMAIN_NAME}"
        conf = NginxHelper.PROJECT_BLOCK_TEMPLATE % (
            server_name_regex,
            self._DOCKER_INTERNAL_HOSTNAME,
            port,
        )

        with open(self._outer_proxy_path, "w") as file:
            file.write(conf)

        if not self._test_nginx_config():
            os.remove(self._outer_proxy_path)
            raise Exception("Failed creating outer_proxy_conf_file", conf)
        return conf

    def generate_project_proxy_conf_file(
        self,
        services: typing.Dict[str, typing.List[typing.Tuple[int, int]]],
    ) -> typing.Tuple[str, typing.List[str]]:
        urls: typing.List[str] = []
        routes = ""
        for service, ports_mappings in services.items():
            for ports in ports_mappings:
                routes_block = NginxHelper.ROUTES_BLOCK_TEMPLATE % (
                    service,
                    ports[1],
                )

                service_url = f"{self._project_name}-{self._branch_name}-{ports[0]}-{self._project_hash}.{self._DOMAIN_NAME}"
                server_name_regex = f"~{service_url}"
                urls.append(f"http://{service_url}")

                server_block = NginxHelper.SERVER_BLOCK_TEMPLATE % (
                    server_name_regex,
                    routes_block,
                )
                routes += server_block

        with open(self._deployment_proxy_path, "w") as file:
            file.write(routes)

        return str(self._deployment_proxy_path), urls

    def _test_nginx_config(self):
        try:
            subprocess.run(
                ["docker", "exec", "sarthi_nginx", "nginx", "-t"],
                check=True,
                capture_output=True,
                text=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error testing Nginx configuration: {e}")
            raise Exception(f"Nginx configs error {e}")

    def reload_nginx(self):
        self._test_nginx_config()
        try:
            subprocess.run(
                ["docker", "exec", "sarthi_nginx", "nginx", "-s", "reload"],
                check=True,
            )
        except Exception as e:
            logger.error(e)
            raise HTTPException(500, "Failed to reload Nginx for the deployment")
        logger.info("Nginx reloaded successfully.")

    def remove_outer_proxy(self):
        if not os.path.exists(self._outer_proxy_path):
            logger.info(f"{self._outer_proxy_path} already deleted!")
            return
        try:
            os.remove(self._outer_proxy_path)
        except Exception as e:
            logger.debug(f"Exception removing outer proxy {e}")


class SecretsHelper:
    def __init__(self, project_name, branch_name, project_path):
        vault_url = os.environ.get("VAULT_BASE_URL")
        vault_token = os.environ.get("VAULT_TOKEN")
        if not vault_url or not vault_token:
            raise HTTPException(500, "Vault is down or not configured correctly.")
        self._project_path = project_path
        self._secrets_namespace = f"{project_name}/{branch_name}"
        self._secret_url = f"{vault_url}/v1/kv/data/{self._secrets_namespace}"
        self._secret_metadata_url = (
            f"{vault_url}/v1/kv/metadata/{self._secrets_namespace}"
        )
        self._headers = {"X-Vault-Token": vault_token}

    def _create_env_placeholder(self):
        sample_envs = {"key": "secret-value"}
        # check for .env.sample in folder and load those sample .env vars in vault
        for sample_env_filename in constants.SAMPLE_ENV_FILENAMES:
            sample_env_path = os.path.join(self._project_path, sample_env_filename)
            if os.path.exists(sample_env_path):
                sample_envs = dotenv_values(sample_env_path)
                break

        try:
            response = requests.post(
                url=self._secret_url,
                headers=self._headers,
                data=json.dumps(
                    {"data": {key: value for key, value in sample_envs.items()}}
                ),
            )
            response.raise_for_status()
        except requests.HTTPError as e:
            logger.error(e)
            raise HTTPException(500, e)

        logger.debug(f"Successfully loaded sample env vars in value {response.json()}")

    def inject_env_variables(self, project_path):
        response = requests.get(url=self._secret_url, headers=self._headers)

        if response.status_code != 200:
            logger.info(f"No secrets found in vault for {self._secrets_namespace}")
            self._create_env_placeholder()
            return

        logger.info(f"Found secrets for {self._secrets_namespace}")
        secret_data = response.json()
        with open(os.path.join(project_path, ".env"), "w") as file:
            for key, value in secret_data["data"]["data"].items():
                file.write(f'{key}="{value}"\n')

    def cleanup_deployment_variables(self):
        try:
            response = requests.delete(
                url=self._secret_metadata_url, headers=self._headers
            )
            logger.debug(
                f"Tried Removing Deployment variables from Vault {response.status_code}"
            )
            response.raise_for_status()
        except requests.HTTPError as e:
            logger.error(f"Error removing deployment secrets {e}")


def get_random_stub(project_name: str, length: int = 64) -> str:
    hash_string = hashlib.md5(project_name.encode()).hexdigest()
    return hash_string[:length] if length else hash_string


def load_yaml_file(filename: str):
    try:
        with open(filename) as file:
            return yaml.safe_load(file)
    except FileNotFoundError as e:
        logging.error(f"File not found: {filename}. Error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"File not found: {filename}. Please provie valid compose file location in config",
        )
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML file: {filename}. Error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Error parsing YAML file: {filename}",
        )
