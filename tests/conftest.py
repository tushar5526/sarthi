import pytest

from server.utils import ComposeHelper, DeploymentConfig, NginxHelper


@pytest.fixture
def compose_helper(mocker):
    test_compose_file = """
# Test Docker compose to be used in tests

version: '3'

services:
  webapp:
    image: nginx:alpine
    ports:
      - "8080:80"

  database:
    image: postgres:latest
    environment:
      POSTGRES_DB: testdb
      POSTGRES_USER: testuser
      POSTGRES_PASSWORD: testpassword

  redis:
    image: redis:alpine
    ports:
      - "6379:6379"

  messaging:
    image: rabbitmq:management
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest

  api:
    image: node:14
    working_dir: /app
    volumes:
      - ./api:/app
    command: npm start
    ports:
      - "3000:3000"
    environment:
      NODE_ENV: development

  python_app:
    image: python:3.8
    volumes:
      - ./python_app:/app
    command: python app.py
    environment:
      PYTHON_ENV: testing

  mongo_db:
    image: mongo:latest
    ports:
      - "27017:27017"
    environment:
      MONGO_INITDB_DATABASE: testdb
      MONGO_INITDB_ROOT_USERNAME: root
      MONGO_INITDB_ROOT_PASSWORD: rootpassword

    """
    mocker.patch("builtins.open", mocker.mock_open(read_data=test_compose_file))
    compose_helper = ComposeHelper("test-docker-compose.yml")
    return compose_helper


@pytest.fixture
def deployment_config():
    return DeploymentConfig(
        project_name="test-project-name",
        branch_name="test-branch-name",
        project_git_url="https://github.com/tushar5526/test-project-name.git",
        rest_action="POST",
    )


@pytest.fixture
def nginx_helper(deployment_config):
    outer_conf_base_path = "/path/to/outer/conf"
    deployment_project_path = "/path/to/deployment/project"
    return NginxHelper(deployment_config, outer_conf_base_path, deployment_project_path)
