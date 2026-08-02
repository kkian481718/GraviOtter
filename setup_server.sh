#!/bin/bash
sudo apt update
sudo apt install -y python3-pip python3-venv npm tmux
sudo npm install -g pm2
cd ~/GraviOtter
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
