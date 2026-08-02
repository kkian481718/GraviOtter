#!/bin/bash
echo "Installing dependencies..."
sudo npm install -g pm2
pip install -r requirements.txt
echo "Initialization complete!"
