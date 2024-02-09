import logging
import os
from urllib.parse import urlparse

import jwt
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_httpauth import HTTPTokenAuth

from server.deployer import Deployer, DeploymentConfig

load_dotenv()

if (os.environ.get("ENV") or "local").lower() == "local":
    logging.basicConfig(level=logging.NOTSET)


app = Flask(__name__)
auth = HTTPTokenAuth("Bearer")
app.config["SECRET_TEXT"] = os.environ.get("SECRET_TEXT")


@auth.verify_token
def verify_token(token):
    try:
        data = jwt.decode(token, app.config["SECRET_TEXT"], algorithms=["HS256"])
        logging.debug(f"Authenticated successfully {data}")
    except Exception as e:  # noqa: E722
        logging.debug(f"Error while authenticating {e}")
        return False
    return True


# Your deployment endpoint
@app.route("/deploy", methods=["POST", "DELETE"])
def deploy():
    data = request.get_json()

    # Create DeploymentConfig object
    project_name = urlparse(data.get("project_git_url")).path[
        :-4
    ]  # remove .git from the end
    config = DeploymentConfig(
        project_name=project_name,
        branch_name=data.get("branch"),
        project_git_url=data.get("project_git_url"),
        compose_file_location=data.get("compose_file_location") or "docker-compose.yml",
        rest_action=request.method,
    )

    deployer = Deployer(config)
    if request.method == "POST":
        urls = deployer.deploy_preview_environment()
        return jsonify(urls)
    elif request.method == "DELETE":
        deployer.delete_preview_environment()
        return (
            jsonify({"message": "Removed preview environment"}),
            200,
        )
    else:
        return (
            jsonify({"error": "Invalid HTTP method. Supported methods: POST, DELETE"}),
            405,
        )


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
