#!/bin/bash

echo "=== Servo API Testing Script ==="
echo "Make sure the FastAPI server is running on localhost:8004"
echo ""

# 1. Check if API is running
echo "1. Checking API status..."
curl http://localhost:8004/
echo -e "\n"

# 2. List available servos
echo "2. Listing available servos..."
curl http://localhost:8004/servos
echo -e "\n"

# 3. Get current servo status
echo "3. Getting current servo status..."
curl http://localhost:8004/servos/status
echo -e "\n"

# 4. Move servo 1 to different positions
echo "4. Testing servo 1 movement..."
curl -X POST "http://localhost:8004/servos/1/move" -H "Content-Type: application/json" -d '{"angle": 0}'
echo -e "\n"
sleep 2
curl -X POST "http://localhost:8004/servos/1/move" -H "Content-Type: application/json" -d '{"angle": 90}'
echo -e "\n"
sleep 2
curl -X POST "http://localhost:8004/servos/1/move" -H "Content-Type: application/json" -d '{"angle": 180}'
echo -e "\n"

# 5. Move all servos to center
echo "5. Centering all servos..."
curl -X POST "http://localhost:8004/servos/center-all"
echo -e "\n"

# 6. Move all servos to a specific angle
echo "6. Moving all servos to 45 degrees..."
curl -X POST "http://localhost:8004/servos/move-all" -H "Content-Type: application/json" -d '{"angle": 45}'
echo -e "\n"

# 7. Center individual servo
echo "7. Centering servo 2..."
curl -X POST "http://localhost:8004/servos/2/center"
echo -e "\n"

echo "=== WebSocket Testing ==="
echo "For WebSocket testing:"
echo "1. Open websocket_test.html in your browser"
echo "2. Click 'Connect' to establish WebSocket connection"
echo "3. Use the API commands above while connected to see real-time updates"
echo "4. Or use a WebSocket client like wscat:"
echo "   npm install -g wscat"
echo "   wscat -c ws://localhost:8004/ws/servos/status"
echo ""
echo "WebSocket endpoint: ws://localhost:8004/ws/servos/status"
echo "Interactive API docs: http://localhost:8004/docs"
echo ""
echo "=== Testing Complete ==="