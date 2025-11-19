#!/bin/bash
PROJECT_DIR="/Users/shaamsarath/Devstudio/projects/page1"
DATA_DIR="$PROJECT_DIR/data/mongodb"
LOG_FILE="$DATA_DIR/mongod.log"

mkdir -p "$DATA_DIR"

# Check if MongoDB is already running
if lsof -Pi :27017 -sTCP:LISTEN -t >/dev/null ; then
    echo "MongoDB is already running on port 27017"
    exit 1
fi

# Start MongoDB in background
nohup mongod --dbpath "$DATA_DIR" --port 27017 --logpath "$LOG_FILE" > /dev/null 2>&1 &

echo "MongoDB started with data directory: $DATA_DIR"
echo "Log file: $LOG_FILE"
echo "To stop: ./stop-mongodb.sh or pkill -f 'mongod --dbpath'"