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
 newgrp docker

 # Install Docker Compose
 echo -e "${YELLOW}${POINT} Installing Docker Compose...${NC}"
 curl -sSL https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/bin/docker-compose
 chmod +x /usr/local/bin/docker-compose

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
docker-compose up -d nginx sarthi

# Display success message
echo -e "${GREEN}${CHECK_MARK} Docker, Docker Compose, and Loki Docker Driver installed and configured successfully.${NC}"
echo -e "${DOCKER} ${YELLOW}You may need to restart your shell or log out and log back in to apply the changes.${NC}"
