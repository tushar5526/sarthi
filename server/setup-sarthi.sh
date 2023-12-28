#!/bin/bash

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Emojis
CHECK_MARK='✔️'
CROSS_MARK='❌'
WARNING='⚠️'
DOCKER='🐳'

# Check if script is run as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}${CROSS_MARK} Please run as root.${NC}" >&2
    exit 1
fi

# Update package index
echo -e "${YELLOW}${WARNING} Updating package index...${NC}"
apt update

# Install prerequisites
echo -e "${YELLOW}${WARNING} Installing prerequisites...${NC}"
apt install -y apt-transport-https ca-certificates curl software-properties-common

# Install Docker
echo -e "${YELLOW}${WARNING} Installing Docker...${NC}"
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh

# Add user to docker group
echo -e "${YELLOW}${WARNING} Adding user to the docker group...${NC}"
usermod -aG docker $USER
newgrp docker


# Install Docker Compose
echo -e "${YELLOW}${WARNING} Installing Docker Compose...${NC}"
curl -sSL https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Display success message
echo -e "${GREEN}${CHECK_MARK} Docker and Docker Compose installed successfully.${NC}"
echo -e "${DOCKER} ${YELLOW}You may need to restart your shell or log out and log back in to apply the changes.${NC}"
