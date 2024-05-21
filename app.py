import logging
import os
from urllib.parse import urlparse

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import server.constants as constants
from server.deployer import Deployer, DeploymentConfig

load_dotenv()

app = FastAPI()
security = HTTPBearer()
app.config = {"SECRET_TEXT": os.environ.get("SECRET_TEXT")}

env = os.environ.get("ENV").upper() == constants.LOCAL
logging.basicConfig(level=logging.DEBUG if env else logging.INFO)


async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        data = jwt.decode(token, app.config["SECRET_TEXT"], algorithms=["HS256"])
        logging.debug(f"Authenticated successfully {data}")
    except Exception as e:
        logging.info(f"Error while authenticating {e}")
        raise HTTPException(status_code=401, detail="Invalid token")
    return data


@app.post("/deploy")
@app.delete("/deploy")
async def deploy(request: Request, token: dict = Depends(verify_token)):
    data = await request.json()

    try:
        project_git_url = urlparse(data.get("project_git_url")).path
    except Exception as e:
        logging.error(e)
        return JSONResponse(
            status_code=400,
            content={"message": f"Bad Project Git URL: {str(e)}"},
        )

    if not project_git_url or not project_git_url.endswith(".git"):
        return JSONResponse(
            status_code=400,
            content={"message": "Project URL should not be empty and end with .git"},
        )

    project_name = project_git_url[:-4]  # remove .git from the end
    config = DeploymentConfig(
        project_name=project_name,
        branch_name=data.get("branch"),
        project_git_url=data.get("project_git_url"),
        compose_file_location=data.get("compose_file_location"),
        rest_action=request.method,
    )
    deployer = Deployer(config)

    if request.method == constants.POST:
        urls = deployer.deploy_preview_environment()
        return JSONResponse(content=urls)
    elif request.method == constants.DELETE:
        deployer.delete_preview_environment()
        return JSONResponse(
            status_code=200,
            content={"message": "Removed preview environment"},
        )
    else:
        return JSONResponse(
            status_code=405,
            content={"error": "Invalid HTTP method. Supported methods: POST, DELETE"},
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5000,
    )
