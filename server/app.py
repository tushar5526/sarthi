import logging
import os

import jwt
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_httpauth import HTTPTokenAuth

from sarthi.deployer import Deployer, DeploymentConfig

load_dotenv()

if os.environ.get("ENV").lower() == "local":
    logging.basicConfig(level=logging.NOTSET)


app = Flask(__name__)
auth = HTTPTokenAuth("Bearer")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")


@auth.verify_token
def verify_token(token):
    try:
        data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
    except:  # noqa: E722
        return False
    return "root"


# Your deployment endpoint
@app.route("/deploy", methods=["POST"])
# @auth.login_required
def deploy():
    data = request.get_json()

    # Create DeploymentConfig object
    project_url_split = data.get("project_git_url").split('/')
    config = DeploymentConfig(
        project_name=f'{project_url_split[-2]}_{project_url_split[-1]}',
        branch_name=data.get("branch_name"),
        project_git_url=data.get("project_git_url"),
        compose_file_location=data.get("compose_file_location") or "docker-compose.yml",
    )

    deployer = Deployer(config)
    urls = deployer.deploy()
    return jsonify(urls)


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
