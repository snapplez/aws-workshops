#!/bin/bash

# source ~/environment/workshop/setup.sh

# install caddy
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy

# install python3 modules
pip install boto3
pip install dnspython
pip install pika

# clear screen
clear

# execute python setup
python /home/ubuntu/environment/workshop/setup.py
