#!/bin/bash
PROJECT_DIR="/Users/shaamsarath/Devstudio/projects/page1"

# Stop MongoDB
pkill -f "mongod --dbpath $PROJECT_DIR"

if [ $? -eq 0 ]; then
    echo "MongoDB stopped"
else
    echo "MongoDB was not running"
fi