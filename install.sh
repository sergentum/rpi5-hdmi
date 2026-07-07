#!/bin/bash

set -e

echo "Updating system..."
sudo apt update
sudo apt upgrade -y

echo "Installing base packages..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-evdev \
    git \
    curl \
    wget \
    build-essential \
    pkg-config \
    cmake \
    libevdev-dev \
    libudev-dev \
    x11-xserver-utils

echo "Installing CEC tools..."
sudo apt install -y cec-utils

echo "Installing Moonlight (Qt)..."
curl -1sLf 'https://dl.cloudsmith.io/public/moonlight-game-streaming/moonlight-qt/setup.deb.sh' | distro=raspbian codename=$(lsb_release -cs) sudo -E bash
sudo apt install -y moonlight-qt

echo "Installing Docker..."

# remove old versions if exist
sudo apt remove -y docker docker-engine docker.io containerd runc || true

# install dependencies
sudo apt install -y ca-certificates gnupg lsb-release

# add docker GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --batch --no-tty --dearmor -o /etc/apt/keyrings/docker.gpg

# add repo
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update

sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "Adding user to docker group..."
sudo usermod -aG docker $USER

echo "Enabling docker service..."
sudo systemctl enable docker
sudo systemctl start docker

echo "Installing optional tools for debugging..."
sudo apt install -y htop iotop tmux

echo "Installing and configuring the systemd service..."

sudo cp controller.service /etc/systemd/system/

sudo systemctl daemon-reload

sudo systemctl enable controller.service

sudo systemctl start controller.service

echo "Checking the service status..."
sudo systemctl status controller.service
