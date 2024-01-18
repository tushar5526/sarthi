#!/bin/bash

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Emojis
CHECK_MARK='✔️'
CROSS_MARK='❌'
POINT='👉'
DOCKER='🐳'

# Check if script is run as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}${CROSS_MARK} Please run as root or sudo.${NC}" >&2
    exit 1
fi

# Update package index
echo -e "${YELLOW}${POINT} Updating package index...${NC}"
apt update

# Install prerequisites
echo -e "${YELLOW}${POINT} Installing prerequisites...${NC}"
apt install -y apt-transport-https ca-certificates curl software-properties-common

# Install Docker
echo -e "${YELLOW}${POINT} Installing Docker...${NC}"
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh

# Add user to docker group
echo -e "${YELLOW}${POINT} Adding user to the docker group...${NC}"
usermod -aG docker $USER

# Install Docker Compose
echo -e "${YELLOW}${POINT} Installing Docker Compose...${NC}"
curl -sSL https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Creating .env file
echo -e "${YELLOW}${POINT} Creating .env file${NC}"

echo -e "DEPLOYMENTS_MOUNT_DIR='$PWD/deployments' # DO NOT EDIT THIS" >> .env
echo -e "NGINX_PROXY_CONF_LOCATION='$PWD/nginx-confs' # DO NOT EDIT THIS" >> .env

# Prompt user for ENV variable
read -p "Enter ENV (default: local (local will set logging to ALL)): " ENV
ENV=${ENV:-local}

# Prompt user for DOMAIN_NAME variable
read -p "Enter DOMAIN_NAME (default: localhost | example: sarthi.youcompany.io | 👋 Make sure to have a wildcard domain name on the public IP): " DOMAIN_NAME
DOMAIN_NAME=${DOMAIN_NAME:-localhost}

read -p "Enter SECRET_TEXT (or press Enter to generate a random secret): " SECRET_TEXT

# Check if the user entered anything
if [ -z "$SECRET_TEXT" ]; then
    # Generate a random secret text if not specified
    SECRET_TEXT=$(openssl rand -base64 32)
    echo "🚀 Default secret text generated: $SECRET_TEXT"
    echo "Please specify this secret in your Github Actions 👆"
fi

# Create or update .env file
echo "ENV='$ENV'" >> .env
echo "DOMAIN_NAME='$DOMAIN_NAME'" >> .env
echo "SECRET_TEXT='$SECRET_TEXT'" >> .env

sed "s/domain_name/$DOMAIN_NAME/g" "sarthi.conf.template" > "sarthi.conf"

# Start Grafaa + Loki services
echo -e "${YELLOW}${POINT} Starting Loki + Grafana to export logs ${NC}"
docker-compose up -d promtail loki grafana

# Install Loki Docker Driver
echo -e "${YELLOW}${POINT} Installing Loki Docker Driver...${NC}"
docker plugin install grafana/loki-docker-driver:2.9.1 --alias loki --grant-all-permissions

# Configure Docker Daemon for Loki Logging
echo -e "${YELLOW}${POINT} Configuring Docker Daemon for Loki Logging...${NC}"
cat <<EOF > /etc/docker/daemon.json
{
    "debug" : true,
    "log-driver": "loki",
    "log-opts": {
        "loki-url": "http://localhost:3100/loki/api/v1/push",
        "loki-batch-size": "400",
        "loki-retries": "1",
        "loki-max-backoff": "500ms",
        "loki-timeout": "1s",
        "keep-file": "true"
    }
}
EOF

# Restart Docker Daemon
echo -e "${YELLOW}${POINT} Restarting Docker Daemon...${NC}"
systemctl restart docker

echo -e "${YELLOW}${POINT} Setup Hashicorp Vault and secrets ${NC}"
bash setup-vault.sh


echo -e "${YELLOW}${POINT} Start Sarthi 😎 ${NC}"
docker-compose up -d sarthi portainer nginx

# Display success message
echo -e "${GREEN}${CHECK_MARK} Docker, Docker Compose, and Loki Docker Driver installed and configured successfully.${NC}"
echo -e "${DOCKER} ${YELLOW}You may need to restart your shell or log out and log back in to apply the changes.${NC}"

echo " 🚀 The following services are activated at the following URLs:"
echo " 🔐 vault     : http://vault.${DOMAIN_NAME}"
echo " 🐳 portainer : http://portainer.${DOMAIN_NAME} : 🔴 👉 Go to the URL to create a login before portainer times out and locks out!"
echo " 🚗 sarthi    : http://api.${DOMAIN_NAME} : 💡 Sarthi Server URL to be specified in GitHub Action"
echo " 📊 grafana   : http://grafana.${DOMAIN_NAME} : 🔴 👉 Go to the URL to create the admin user!"
