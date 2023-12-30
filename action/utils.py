import datetime
import json
import os
import jwt
import requests


def comment_on_gh_pr(comment):
    GITHUB_API_URL = os.environ.get("GITHUB_API_URL")
    GITHUB_TOKEN = os.environ.get('INPUT_GITHUB_TOKEN')
    if not GITHUB_TOKEN:
        raise Exception("INVALID GITHUB TOKEN _ EMPTY")
    pr_number = os.environ.get("GITHUB_REF_NAME").split('/')[0]

    url = f"{GITHUB_API_URL}/repos/{os.environ.get('GITHUB_REPOSITORY')}/issues/{pr_number}/comments"

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Accept": "application/vnd.github+json"
    }

    data = {"body": comment}

    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()


def _generate_bearer_token(secret) -> str:
    payload = {
        "sub": "sarthi",
        "iat": datetime.datetime.utcnow(),  # Issued at time
        "exp": datetime.datetime.utcnow()
        + datetime.timedelta(minutes=1),  # Expiration time
    }

    token = jwt.encode(payload, secret, algorithm="HS256")
    return f'Bearer {token.decode("utf-8")}'


def deploy(project_git_url, branch, sarthi_secret, sarthi_server_url):
    headers = {"Authorization": _generate_bearer_token(sarthi_secret)}
    body = {
        "project_git_url": project_git_url,
        "branch": branch,
    }
    response = requests.post(
        url=sarthi_server_url, headers=headers, data=json.dumps(body)
    )
    response.raise_for_status()
    service_urls = response.json()
    return service_urls
