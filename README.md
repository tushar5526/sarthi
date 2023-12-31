# Sarthi

Sarthi allows you to quickly setup Ephemeral Preview Environments. Easy installation using a script and never touch your server again. 
Sarthi is build up on other OSS projects to exports logs, enable monitoring and create preview environments.

You can you use the [sarthi-deploy]() GitHub Action for setting up preview environments for your branches / PR.

Pre-requisites 🛠️
-------------------

1. Dockerized projects with a `docker-compose`.
   - It is MANDATORY to have a `docker-compose` file at the root of project's folder. 
2. A public Linux machine (preferred Ubuntu 20+ LTS versions) and user with root access. 
3. A wildcard subdomain pointing to the above machine (*.sarthi.your-domain.io)

Setup Instructions ⚙️
------------------------


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

Services Installed 🤖
---------------------

1. Grafana + Loki to export service logs from the deployed environments. 
2. Portainer for admin access to docker containers. 
3. Hashicorp Vault to specify environment secrets. 
   - For each deployed branch/PR a path will be created by default in the vault where users can specify their secrets.
   - Vault's secret token should be present in a keys.txt folder in the repo

Tips 💡
-------
1. Use docker-compose's service discovery to connect within same services in the project. 


### License 📄
This action is licensed under some specific terms. Check [here](LICENSE) for more information.
