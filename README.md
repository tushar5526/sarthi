# Sarthi

[![Open Source Love svg1](https://badges.frapsoft.com/os/v1/open-source.svg?v=103)](https://github.com/ellerbrock/open-source-badges/) [![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](http://makeapullrequest.com) ![contributions welcome](https://img.shields.io/static/v1.svg?label=Contributions&message=Welcome&color=0059b3&style=flat-square) ![GitHub contributors](https://img.shields.io/github/contributors-anon/tushar5526/sarthi)
[![codecov](https://codecov.io/gh/tushar5526/sarthi/graph/badge.svg?token=85RAG9BYA4)](https://codecov.io/gh/tushar5526/sarthi)![tests](https://github.com/tushar5526/sarthi/actions/workflows/test.yml/badge.svg)![lints](https://github.com/tushar5526/sarthi/actions/workflows/lint.yml/badge.svg)

### Vercel for Backend! Easily setup preview environments with just Docker 🐳

Self-host Ephemeral (Preview) Environments with ease and forget about server management.
Sarthi uses other open-source projects to export logs, enable monitoring, manage secrets and create preview environments. Let devs focus on building stuff in isolated environments rather than bashing heads together to manage conflicts.

It is meant to be used along with [sarthi-deploy](https://github.com/tushar5526/sarthi-deploy) GitHub Action for setting up preview environments in your project. Every time there is a new branch or a PR created, Sarthi GHA will create a preview environment for that. It also takes care of deleting preview environments when respective branches or PRs are merged.

PS: Service Developers can directly jump to the [Developer Guide](#developer-guide)

## Pre-requisites 🛠️

1. Dockerized projects with a `docker-compose`.
   - It is **MANDATORY** to have a `docker-compose` file at the root of the project's folder.
2. A public Linux machine (preferred Ubuntu 20+ LTS versions) and user with root access.
3. A wildcard subdomain pointing to the above machine `(\*.sarthi.your-domain.io)`

## General Flow

1. Create a public machine (preferred 4GB RAM, Ubuntu 20+ LTS versions) and map a [wildcard domain](https://docs.digitalocean.com/glossary/wildcard-record/) to it.
2. Set up the project using the [setup-sarthi.sh](https://github.com/tushar5526/sarthi/blob/main/setup-sarthi.sh) script present in the root folder.
3. Get the generated `SECRET_TEXT` and the deployed `SERVER_URL` after running the installation script.
4. Set up the [Sarthi GitHub Action](https://github.com/tushar5526/sarthi-deploy) in your projects (No external bots - all your data within your servers).
5. Environment secrets for preview deployments are fetched from the Vault and added in a `.env` file and placed along with your docker-compose file.
   - Sarthi searches for `.env.sample` or `sample.env` and adds your secrets to `project_name_branchname_hash` path in Vault.
6. On any new events (PR open, close) Sarthi by default creates a unique URL for every service that is exposed in the `docker-compose` of the project.
7. You are ready to roll 🚀. GitHub Actions will comment on the deployment status according to different events!

<img width="980" alt="Screenshot 2024-01-08 at 2 30 07 PM" src="https://github.com/tushar5526/sarthi/assets/30565750/94657a08-352b-4c2b-a8af-4af154f686e3">

<p align='center'><i>Sarthi-Deploy GHA will not clutter your PR with comments - it will keep updating its earlier comment</i></p>
<img width="937" alt="Screenshot 2024-01-08 at 2 31 14 PM" src="https://github.com/tushar5526/sarthi/assets/30565750/31697b06-fd67-40d5-84ce-c5d43dcdd2bf">

## Setup Instructions ⚙️

1. SSH into your server and clone the project.

```commandline
git clone https://github.com/tushar5526/sarthi.git
```

2. Run the setup script.

```commandline
chmod +x setup-sarthi.sh
chmod +x setup-vault.sh
sudo ./setup-sarthi.sh
```

3. Follow the prompts and specify the values, you will be requested to specify the wild card domain name created earlier.
   (using localhost is possible, but that would require setting up `dnsmaq`)

## Services Installed 🤖

The following services are exposed:

1. [Grafana](https://grafana.com/) + [Loki](https://grafana.com/oss/loki/) to export service logs from the deployed environments. [http://grafana.sarthi.your_domain.io](http://grafana.sarthi.your_domain.io)
   - A dashboard named `Service Logs` is pre-seeded in Grafana. You can use this to filter service logs based on deployments, containers etc.
   <p align="center"><img width="720" alt="Screenshot 2024-01-04 at 1 39 59 AM" src="https://github.com/tushar5526/sarthi/assets/30565750/a42db693-fcee-4a4d-8095-a1bdd2954f33"></p>
2. [Portainer](https://www.portainer.io/) for admin access to manage deployments if needed. [http://portainer.sarthi.your_domain.io](http://portainer.sarthi.your_domain.io)
<p align="center"><img width="720" alt="Screenshot 2024-01-04 at 1 42 56 AM" src="https://github.com/tushar5526/sarthi/assets/30565750/13429693-78a1-4349-9a9c-cc2d921b4ad1"></p>

3. [Hashicorp Vault](https://www.vaultproject.io/) to specify environment secrets. [http://hashicorp.sarthi.your_domain.io](http://hashicorp.sarthi.your_domain.io)

   - For each deployed branch/PR a path will be created by default in the vault where developers can specify branch-specific secrets.
   - 👉 PS: Hashicorp vault gets sealed on restarts. Unseal keys are generated by the setup script and stored in a `keys.txt` on the server. There is no RBAC yet and the root token is used to modify the env vars for different deployments. Root tokens can be found in `keys.txt`
   <p align="center"><img width="720" alt="Screenshot 2024-01-04 at 1 44 44 AM" src="https://github.com/tushar5526/sarthi/assets/30565750/842704b8-33b3-4aca-abae-6739878bae69"></p>

4. [Sarthi](https://github.com/tushar5526/sarthi) Backend for GHA. [http://api.sarthi.your_domain.io](http://api.sarthi.your_domain.io)

## Developer Guide

### Exposing services

1. Every service in `docker-compose` of which ports are exposed, is exposed to developers via a unique URL by Sarthi.
2. Sarthi currently only support fetching secrets from the vault and storing them in `.env` before deploying, so it's recommended to avoid `env_file` command or use it with `.env` files.

### Secrets Discovery and namespacing

1. For each PR, Sarthi creates a preview environment using the `docker-compose` specified.
2. Before Submitting a Pull Request, install pre-commit using `pip3 install pre-commit` and install the pre-commit git hooks: `pre-commit install`.
3. Sarthi finds the secret for the service as follows.
   - Check the vault under the `project/feature-branch` namespace and find secrets there.
   - There is a default namespace reserved for developers to specify default secrets for all the PS. Secrets defined under `project/default-dev-secrets` are used if `project/feature-branch` secret path is empty.
   - If the default namespace is not configured as well, Sarthi automatically tries to find `sample.env`, `env.sample`, `.env.sample` and similar sample env files in the root directory and loads those sample environment variables to both `default-dev-secrets` and `project/feature-branch`

### Tips 💡

1. Use `docker-compose's` service discovery to connect within the same services in your projects.

## Contributor's Guide

A `Makefile` is provided at the project's root that can be used to set up the local environment for Sarthi easily. It needs to have [docker](https://docs.docker.com/engine/install/) installed on your system. Supported dev environments are either Mac or Linux, I have not tested it on Windows. Read more about [Makefile](https://opensource.com/article/18/8/what-how-makefile).

### High-Level Architecture

![sarthi](https://github.com/tushar5526/sarthi/assets/30565750/d08cf07e-f235-457c-952d-2406920319cb)

### License 📄

This action is licensed under some specific terms. Check [here](LICENSE) for more information.
