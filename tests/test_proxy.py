"""Tests for the proxy abstraction layer."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from server.proxy import (
    BaseProxyHelper,
    CaddyProxyHelper,
    NginxProxyHelper,
    get_proxy_helper,
)
from server.utils import DeploymentConfig


@pytest.fixture
def deployment_config():
    """Create a sample deployment configuration."""
    config = DeploymentConfig(
        project_name="/test/repo",
        branch_name="feature-branch",
        project_git_url="https://github.com/test/repo.git",
        gh_token=None,
    )
    return config


@pytest.fixture
def nginx_helper(deployment_config, tmp_path):
    """Create an NginxProxyHelper instance."""
    outer_conf_path = str(tmp_path / "nginx-confs")
    deployment_path = str(tmp_path / "deployment")
    os.makedirs(outer_conf_path, exist_ok=True)
    os.makedirs(deployment_path, exist_ok=True)
    return NginxProxyHelper(deployment_config, outer_conf_path, deployment_path)


@pytest.fixture
def caddy_helper(deployment_config, tmp_path):
    """Create a CaddyProxyHelper instance."""
    outer_conf_path = str(tmp_path / "caddy-confs")
    deployment_path = str(tmp_path / "deployment")
    os.makedirs(outer_conf_path, exist_ok=True)
    os.makedirs(deployment_path, exist_ok=True)
    return CaddyProxyHelper(deployment_config, outer_conf_path, deployment_path)


def test_get_proxy_helper_default(deployment_config, tmp_path):
    """Test that get_proxy_helper returns NginxProxyHelper by default."""
    outer_conf_path = str(tmp_path / "confs")
    deployment_path = str(tmp_path / "deployment")
    os.makedirs(outer_conf_path, exist_ok=True)
    os.makedirs(deployment_path, exist_ok=True)
    
    helper = get_proxy_helper(deployment_config, outer_conf_path, deployment_path)
    assert isinstance(helper, NginxProxyHelper)


def test_get_proxy_helper_nginx(deployment_config, tmp_path):
    """Test that get_proxy_helper returns NginxProxyHelper when PROXY_TYPE=nginx."""
    outer_conf_path = str(tmp_path / "confs")
    deployment_path = str(tmp_path / "deployment")
    os.makedirs(outer_conf_path, exist_ok=True)
    os.makedirs(deployment_path, exist_ok=True)
    
    with patch.dict(os.environ, {"PROXY_TYPE": "nginx"}):
        helper = get_proxy_helper(deployment_config, outer_conf_path, deployment_path)
        assert isinstance(helper, NginxProxyHelper)


def test_get_proxy_helper_caddy(deployment_config, tmp_path):
    """Test that get_proxy_helper returns CaddyProxyHelper when PROXY_TYPE=caddy."""
    outer_conf_path = str(tmp_path / "confs")
    deployment_path = str(tmp_path / "deployment")
    os.makedirs(outer_conf_path, exist_ok=True)
    os.makedirs(deployment_path, exist_ok=True)
    
    with patch.dict(os.environ, {"PROXY_TYPE": "caddy"}):
        helper = get_proxy_helper(deployment_config, outer_conf_path, deployment_path)
        assert isinstance(helper, CaddyProxyHelper)


def test_nginx_conf_file_name(nginx_helper):
    """Test that NginxProxyHelper generates correct config file name."""
    conf_name = nginx_helper.get_conf_file_name()
    assert conf_name.endswith(".conf")
    assert "testrepo" in conf_name  # project name is truncated/sanitized


def test_caddy_conf_file_name(caddy_helper):
    """Test that CaddyProxyHelper generates correct config file name."""
    conf_name = caddy_helper.get_conf_file_name()
    assert conf_name.endswith(".caddy")
    assert "testrepo" in conf_name  # project name is truncated/sanitized


def test_nginx_generate_project_proxy_conf(nginx_helper):
    """Test Nginx project proxy configuration generation."""
    services = {
        "web": [(3000, 3000)],
        "api": [(5000, 5000)],
    }
    
    conf_path, urls = nginx_helper.generate_project_proxy_conf_file(services)
    
    assert conf_path is not None
    assert len(urls) == 2
    assert all(url.startswith("http://") for url in urls)
    
    # Check that config file was created
    assert os.path.exists(conf_path)
    
    # Check config content
    with open(conf_path) as f:
        content = f.read()
        assert "server {" in content
        assert "listen 80;" in content
        assert "proxy_pass" in content


def test_caddy_generate_project_proxy_conf(caddy_helper):
    """Test Caddy project proxy configuration generation."""
    services = {
        "web": [(3000, 3000)],
        "api": [(5000, 5000)],
    }
    
    conf_path, urls = caddy_helper.generate_project_proxy_conf_file(services)
    
    assert conf_path is not None
    assert len(urls) == 2
    assert all(url.startswith("https://") for url in urls)  # Caddy uses HTTPS
    
    # Check that config file was created
    assert os.path.exists(conf_path)
    
    # Check config content
    with open(conf_path) as f:
        content = f.read()
        assert "reverse_proxy" in content
        assert "{" in content  # Caddyfile block syntax


def test_nginx_generate_outer_proxy_conf(nginx_helper):
    """Test Nginx outer proxy configuration generation."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        
        conf = nginx_helper.generate_outer_proxy_conf_file("8080")
        
        assert "server {" in conf
        assert "listen 80;" in conf
        assert "8080" in conf
        assert "proxy_pass" in conf


def test_caddy_generate_outer_proxy_conf(caddy_helper):
    """Test Caddy outer proxy configuration generation."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        
        conf = caddy_helper.generate_outer_proxy_conf_file("8080")
        
        assert "reverse_proxy" in conf
        assert "8080" in conf


def test_nginx_find_free_port(nginx_helper):
    """Test finding a free port with NginxProxyHelper."""
    with patch.dict(os.environ, {"DEPLOYMENT_HOST": "localhost"}):
        nginx_helper._host_name = "localhost"
        port = nginx_helper.find_free_port()
        assert port is not None
        assert isinstance(port, str)
        assert int(port) > 0


def test_caddy_find_free_port(caddy_helper):
    """Test finding a free port with CaddyProxyHelper."""
    with patch.dict(os.environ, {"DEPLOYMENT_HOST": "localhost"}):
        caddy_helper._host_name = "localhost"
        port = caddy_helper.find_free_port()
        assert port is not None
        assert isinstance(port, str)
        assert int(port) > 0


def test_nginx_remove_outer_proxy(nginx_helper):
    """Test removing outer proxy configuration for Nginx."""
    # Create a dummy config file
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        nginx_helper.generate_outer_proxy_conf_file("8080")
    
    # Remove it
    nginx_helper.remove_outer_proxy()
    
    # Verify it's gone
    outer_path = nginx_helper._outer_proxy_path
    assert not os.path.exists(outer_path)


def test_caddy_remove_outer_proxy(caddy_helper):
    """Test removing outer proxy configuration for Caddy."""
    # Create a dummy config file
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        caddy_helper.generate_outer_proxy_conf_file("8080")
    
    # Remove it
    caddy_helper.remove_outer_proxy()
    
    # Verify it's gone
    outer_path = caddy_helper._outer_proxy_path
    assert not os.path.exists(outer_path)


def test_nginx_reload_proxy(nginx_helper):
    """Test reloading Nginx proxy."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        
        nginx_helper.reload_proxy()
        
        # Verify subprocess was called
        assert mock_run.call_count >= 1


def test_caddy_reload_proxy(caddy_helper):
    """Test reloading Caddy proxy."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        
        caddy_helper.reload_proxy()
        
        # Verify subprocess was called
        assert mock_run.call_count >= 1


def test_base_proxy_helper_is_abstract():
    """Test that BaseProxyHelper cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseProxyHelper(None, None, None)
