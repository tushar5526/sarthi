import logging
import os
import shutil
import subprocess
import typing

import filelock

from .utils import ComposeHelper, DeploymentConfig, NginxHelper, SecretsHelper

logger = logging.getLogger(__name__)


class Deployer:
    def __init__(self, config: DeploymentConfig):
        self._config = config
        self._DEPLOYMENTS_MOUNT_DIR: typing.Final[str] = os.environ.get(
            "DEPLOYMENTS_MOUNT_DIR"
        )
        self._deployment_namespace = f"{self._config.project_name}_{self._config.branch_name}_{config.get_project_hash()}"
        self._lock_file_path = os.path.join(
            os.environ.get("LOCK_FILE_BASE_PATH") or "/tmp",
            f"{self._deployment_namespace}.lock",
        )
        self._lock = filelock.FileLock(self._lock_file_path)
        self._project_path: typing.Final[str] = os.path.join(
            self._DEPLOYMENTS_MOUNT_DIR, self._deployment_namespace
        )

        with self._lock:
            if config.rest_action != "DELETE":
                self._setup_project()

            self._compose_helper = ComposeHelper(
                os.path.join(self._project_path, config.compose_file_location),
                config.rest_action != "DELETE",
            )
            self._secrets_helper = SecretsHelper(
                self._config.project_name, self._config.branch_name, self._project_path
            )
            self._outer_proxy_conf_location = (
                os.environ.get("NGINX_PROXY_CONF_LOCATION") or "/etc/nginx/conf.d"
            )
            self._nginx_helper = NginxHelper(
                config, self._outer_proxy_conf_location, self._project_path
            )

    def _clone_project(self):
        process = subprocess.Popen(
            [
                "git",
                "clone",
                "-b",
                self._config.branch_name,
                self._config.project_git_url,
                self._project_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            stdout, stderr = process.communicate()
        except subprocess.TimeoutExpired as e:
            logger.error(f"Error cloning the repo {self._config} with {e}")
            raise
        if process.returncode == 0:
            logger.info("Git clone successful.")
        else:
            logger.error(f"Git clone failed. Return code: {process.returncode}")
            logger.error(f"Standard Output: {stdout.decode()}")
            logger.error(f"Standard Error: {stderr.decode()}")
            raise Exception(f"Cloning the Git repo failed {self._config}")

    def _setup_project(self):
        if os.path.exists(self._project_path):
            # TODO: Run docker compose down -v
            logger.debug(f"Removing older project path {self._project_path}")
            shutil.rmtree(self._project_path)
        self._clone_project()

    def _configure_outer_proxy(self):
        if not self._project_nginx_port:
            raise Exception("Project Proxy not deployed, project_nginx_port is None")
        self._nginx_helper.generate_outer_proxy_conf_file(self._project_nginx_port)
        self._nginx_helper.reload_nginx()

    def _deploy_project(self):
        services = self._compose_helper.get_service_ports_config()
        conf_file_path, urls = self._nginx_helper.generate_project_proxy_conf_file(
            services
        )
        # TODO: Keep retrying finding a new port for race conditions
        self._project_nginx_port = self._nginx_helper.find_free_port()
        self._secrets_helper.inject_env_variables(self._project_path)
        self._compose_helper.start_services(
            self._project_nginx_port, conf_file_path, self._deployment_namespace
        )
        return urls

    def _delete_deployment_files(self):
        if not os.path.exists(self._project_path):
            print(f"{self._project_path} already deleted!")
            return
        try:
            shutil.rmtree(self._project_path)
        except Exception as e:
            logger.debug(f"Error removing deployment files {e}")

    def deploy_preview_environment(self):
        with self._lock:
            urls = self._deploy_project()
            self._configure_outer_proxy()
        return urls

    def delete_preview_environment(self):
        with self._lock:
            self._compose_helper.remove_services()
            self._nginx_helper.remove_outer_proxy()
            self._nginx_helper.reload_nginx()
            self._delete_deployment_files()
            self._secrets_helper.cleanup_deployment_variables()
