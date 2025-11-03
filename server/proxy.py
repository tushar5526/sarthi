"""
Proxy abstraction layer for supporting multiple reverse proxy types.
This module provides base classes and implementations for different proxy servers.
"""

import logging
import os
import socket
import subprocess
import typing
from abc import ABC, abstractmethod

from fastapi import HTTPException

import server.constants as constants
from .utils import DeploymentConfig

logger = logging.getLogger(__name__)


class BaseProxyHelper(ABC):
    """Abstract base class for reverse proxy helpers."""

    def __init__(
        self,
        config: DeploymentConfig,
        outer_conf_base_path: str,
        deployment_project_path: str,
    ):
        # Sub domains can be of certain length - we can't use the whole project and branch name
        self._project_name = (
            config.project_name[:10]
            if len(config.project_name) > 10
            else config.project_name
        )

        self._branch_name = (
            config.branch_name[:20]
            if len(config.branch_name) > 20
            else config.branch_name
        )

        self._project_hash = config.get_project_hash()
        self._port = None
        self._host_name = (
            os.environ.get("DEPLOYMENT_HOST") or constants.DOCKER_HOST_NETWORK_DOMAIN
        )
        self._start_port = int(
            os.environ.get("DEPLOYMENT_PORT_START")
            or constants.DEFAULT_DEPLOYMENT_PORT_START
        )
        self._end_port = int(
            os.environ.get("DEPLOYMENT_PORT_END")
            or constants.DEFAULT_DEPLOYMENT_PORT_END
        )
        self._DOMAIN_NAME = os.environ.get("DOMAIN_NAME") or constants.LOCALHOST
        self._DOCKER_INTERNAL_HOSTNAME: typing.Final[
            str
        ] = constants.DOCKER_HOST_NETWORK_DOMAIN
        self._outer_conf_base_path = outer_conf_base_path
        self._deployment_project_path = deployment_project_path

    @abstractmethod
    def generate_outer_proxy_conf_file(self, port: str) -> str:
        """Generate the outer proxy configuration file."""
        pass

    @abstractmethod
    def generate_project_proxy_conf_file(
        self,
        services: typing.Dict[str, typing.List[typing.Tuple[int, int]]],
    ) -> typing.Tuple[str, typing.List[str]]:
        """Generate the project-specific proxy configuration file."""
        pass

    @abstractmethod
    def reload_proxy(self):
        """Reload the proxy configuration."""
        pass

    @abstractmethod
    def remove_outer_proxy(self):
        """Remove the outer proxy configuration."""
        pass

    def find_free_port(self) -> str:
        """Find a free port for the deployment."""
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

        logger.error("Could not find a free port in the specified range")
        raise HTTPException(500, "Could not find a free port in the specified range")

    @abstractmethod
    def get_conf_file_name(self) -> str:
        """Get the configuration file name."""
        pass

    @abstractmethod
    def get_deployment_proxy_path(self) -> str:
        """Get the path to the deployment proxy configuration."""
        pass


class NginxProxyHelper(BaseProxyHelper):
    """Nginx-specific proxy helper implementation."""

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
        super().__init__(config, outer_conf_base_path, deployment_project_path)
        self._conf_file_name = f"{self._project_name}-{self._project_hash}.conf"
        self._outer_proxy_path = os.path.join(
            self._outer_conf_base_path, self._conf_file_name
        )
        self._deployment_proxy_path = os.path.join(
            self._deployment_project_path, self._conf_file_name
        )

    def get_conf_file_name(self) -> str:
        return self._conf_file_name

    def get_deployment_proxy_path(self) -> str:
        return self._deployment_proxy_path

    def generate_outer_proxy_conf_file(self, port: str) -> str:
        port = port or self._port
        server_name_regex = f"~{self._project_hash}.{self._DOMAIN_NAME}"
        conf = NginxProxyHelper.PROJECT_BLOCK_TEMPLATE % (
            server_name_regex,
            self._DOCKER_INTERNAL_HOSTNAME,
            port,
        )

        with open(self._outer_proxy_path, "w") as file:
            file.write(conf)

        if not self._test_nginx_config():
            os.remove(self._outer_proxy_path)
            logger.error("Failed creating outer_proxy_conf_file. Check with admin")
            raise HTTPException(
                500, "Failed creating outer_proxy_conf_file. Check with admin"
            )
        return conf

    def generate_project_proxy_conf_file(
        self,
        services: typing.Dict[str, typing.List[typing.Tuple[int, int]]],
    ) -> typing.Tuple[str, typing.List[str]]:
        urls: typing.List[str] = []
        routes = ""
        for service, ports_mappings in services.items():
            for ports in ports_mappings:
                routes_block = NginxProxyHelper.ROUTES_BLOCK_TEMPLATE % (
                    service,
                    ports[1],
                )

                service_url = f"{self._project_name}-{self._branch_name}-{ports[0]}-{self._project_hash}.{self._DOMAIN_NAME}"
                server_name_regex = f"~{service_url}"
                urls.append(f"http://{service_url}")

                server_block = NginxProxyHelper.SERVER_BLOCK_TEMPLATE % (
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
            raise HTTPException(
                500,
                "Error in generated Nginx configs. Check with Sarthi Admin or see logs.",
            )
        except Exception as e:
            logger.error(f"Error testing Nginx configuration: {e}")
            raise HTTPException(500, "Internal Server Error")

    def reload_proxy(self):
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


class CaddyProxyHelper(BaseProxyHelper):
    """Caddy-specific proxy helper implementation with automatic SSL support."""

    def __init__(
        self,
        config: DeploymentConfig,
        outer_conf_base_path: str,
        deployment_project_path: str,
    ):
        super().__init__(config, outer_conf_base_path, deployment_project_path)
        self._conf_file_name = f"{self._project_name}-{self._project_hash}.caddy"
        self._outer_proxy_path = os.path.join(
            self._outer_conf_base_path, self._conf_file_name
        )
        self._deployment_proxy_path = os.path.join(
            self._deployment_project_path, self._conf_file_name
        )

    def get_conf_file_name(self) -> str:
        return self._conf_file_name

    def get_deployment_proxy_path(self) -> str:
        return self._deployment_proxy_path

    def generate_outer_proxy_conf_file(self, port: str) -> str:
        """Generate Caddyfile configuration for outer proxy with automatic SSL."""
        port = port or self._port
        # Caddy uses simple domain matching, wildcard subdomain
        domain_pattern = f"*.{self._project_hash}.{self._DOMAIN_NAME}"

        # Caddyfile configuration with automatic HTTPS
        conf = f"""# Outer proxy configuration for {self._project_name}
{domain_pattern} {{
    reverse_proxy {self._DOCKER_INTERNAL_HOSTNAME}:{port}
}}
"""

        with open(self._outer_proxy_path, "w") as file:
            file.write(conf)

        if not self._test_caddy_config():
            os.remove(self._outer_proxy_path)
            logger.error("Failed creating outer_proxy_conf_file. Check with admin")
            raise HTTPException(
                500, "Failed creating outer_proxy_conf_file. Check with admin"
            )
        return conf

    def generate_project_proxy_conf_file(
        self,
        services: typing.Dict[str, typing.List[typing.Tuple[int, int]]],
    ) -> typing.Tuple[str, typing.List[str]]:
        """Generate Caddyfile configuration for project services."""
        urls: typing.List[str] = []
        routes = "# Project proxy configuration\n\n"

        for service, ports_mappings in services.items():
            for ports in ports_mappings:
                service_url = f"{self._project_name}-{self._branch_name}-{ports[0]}-{self._project_hash}.{self._DOMAIN_NAME}"
                urls.append(f"https://{service_url}")

                # Caddyfile block for each service
                routes += f"""{service_url} {{
    reverse_proxy {service}:{ports[1]}
}}

"""

        with open(self._deployment_proxy_path, "w") as file:
            file.write(routes)

        return str(self._deployment_proxy_path), urls

    def _test_caddy_config(self):
        """Test Caddy configuration."""
        try:
            subprocess.run(
                ["docker", "exec", "sarthi_caddy", "caddy", "validate", "--config", "/etc/caddy/Caddyfile"],
                check=True,
                capture_output=True,
                text=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error testing Caddy configuration: {e}")
            raise HTTPException(
                500,
                "Error in generated Caddy configs. Check with Sarthi Admin or see logs.",
            )
        except Exception as e:
            logger.error(f"Error testing Caddy configuration: {e}")
            raise HTTPException(500, "Internal Server Error")

    def reload_proxy(self):
        """Reload Caddy configuration."""
        self._test_caddy_config()
        try:
            subprocess.run(
                ["docker", "exec", "sarthi_caddy", "caddy", "reload", "--config", "/etc/caddy/Caddyfile"],
                check=True,
            )
        except Exception as e:
            logger.error(e)
            raise HTTPException(500, "Failed to reload Caddy for the deployment")
        logger.info("Caddy reloaded successfully.")

    def remove_outer_proxy(self):
        """Remove outer proxy configuration."""
        if not os.path.exists(self._outer_proxy_path):
            logger.info(f"{self._outer_proxy_path} already deleted!")
            return
        try:
            os.remove(self._outer_proxy_path)
        except Exception as e:
            logger.debug(f"Exception removing outer proxy {e}")


def get_proxy_helper(
    config: DeploymentConfig,
    outer_conf_base_path: str,
    deployment_project_path: str,
) -> BaseProxyHelper:
    """
    Factory function to get the appropriate proxy helper based on configuration.
    
    Args:
        config: Deployment configuration
        outer_conf_base_path: Path to outer proxy configuration directory
        deployment_project_path: Path to deployment project directory
        
    Returns:
        Instance of appropriate proxy helper (Nginx or Caddy)
    """
    proxy_type = os.environ.get("PROXY_TYPE", "nginx").lower()
    
    if proxy_type == "caddy":
        logger.info("Using Caddy proxy helper")
        return CaddyProxyHelper(config, outer_conf_base_path, deployment_project_path)
    else:
        logger.info("Using Nginx proxy helper")
        return NginxProxyHelper(config, outer_conf_base_path, deployment_project_path)
