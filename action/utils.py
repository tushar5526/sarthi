import requests
import os
import json
import jwt
import datetime

GITHUB_API_URL = os.environ.get('GITHUB_API_URL')


def comment_on_gh_pr(comment):
    pass


def _generate_bearer_token(secret) -> str:
    payload = {
        'sub': 'sarthi',
        'iat': datetime.datetime.utcnow(),  # Issued at time
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=1)  # Expiration time
    }

    token = jwt.encode(payload, secret, algorithm='HS256')
    return f'Bearer {token.decode("utf-8")}'


def deploy(project_git_url, branch, sarthi_secret, sarthi_server_url):
    headers = {"Authorization": _generate_bearer_token(sarthi_secret)}
    body = {
        "project_git_url": project_git_url,
        "branch": branch,
    }
    response = requests.post(url=sarthi_server_url, headers=headers, data=json.dumps(body))
    response.raise_for_status()
    service_urls = response.json()
    return service_urls


