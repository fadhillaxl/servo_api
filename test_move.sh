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

# 8. Get servo configuration (jitter reduction settings)
echo "8. Getting servo configuration..."
curl http://localhost:8004/servos/config
echo -e "\n"

# 9. Update servo configuration to reduce jitter
echo "9. Updating servo configuration (reduce hold time for faster detach)..."
curl -X POST "http://localhost:8004/servos/config" -H "Content-Type: application/json" -d '{"detach_enabled": true, "hold_time": 0.5}'
echo -e "\n"

# 10. Test movement with new configuration
echo "10. Testing movement with reduced jitter settings..."
curl -X POST "http://localhost:8004/servos/1/move" -H "Content-Type: application/json" -d '{"angle": 45}'
echo -e "\n"

echo "Testing pulse width configuration (fine-tuning for less jitter)..."
curl -X POST "http://localhost:8004/servos/config" \
     -H "Content-Type: application/json" \
     -d '{"detach_enabled": true, "hold_time": 0.3, "min_pulse_width": 0.0006, "max_pulse_width": 0.0024}'
echo -e "\n"

echo "Testing servo movement with fine-tuned pulse widths..."
curl -X POST "http://localhost:8000/servos/1/move" \
     -H "Content-Type: application/json" \
     -d '{"angle": 90}'
echo -e "\n"

echo "Testing hold mode configuration (always hold servos)..."
curl -X POST "http://localhost:8000/servos/config" \
     -H "Content-Type: application/json" \
     -d '{"detach_enabled": false, "hold_time": 1.0, "min_pulse_width": 0.0005, "max_pulse_width": 0.0025, "hold_mode": "hold"}'
echo -e "\n"

echo "Testing individual servo hold/release..."
curl -X POST "http://localhost:8000/servos/1/hold"
echo -e "\n"

curl -X POST "http://localhost:8000/servos/1/release"
echo -e "\n"

echo "Testing release mode configuration (always release servos)..."
curl -X POST "http://localhost:8000/servos/config" \
     -H "Content-Type: application/json" \
     -d '{"detach_enabled": false, "hold_time": 1.0, "min_pulse_width": 0.0005, "max_pulse_width": 0.0025, "hold_mode": "release"}'
echo -e "\n"

echo "Testing hold-all and release-all endpoints..."
curl -X POST "http://localhost:8000/servos/hold-all"
echo -e "\n"

curl -X POST "http://localhost:8000/servos/release-all"
echo -e "\n"

echo "Testing smooth movement configuration..."
curl -X POST "http://localhost:8000/servos/config" \
     -H "Content-Type: application/json" \
     -d '{"detach_enabled": true, "hold_time": 0.5, "min_pulse_width": 0.0005, "max_pulse_width": 0.0025, "hold_mode": "auto", "smooth_enabled": true, "smooth_steps": 15, "smooth_delay": 0.03}'
echo -e "\n"

echo "Testing smooth servo movement..."
curl -X POST "http://localhost:8000/servos/1/move" \
     -H "Content-Type: application/json" \
     -d '{"angle": 45}'
echo -e "\n"

sleep 2

echo "Testing smooth servo centering..."
curl -X POST "http://localhost:8000/servos/1/center"
echo -e "\n"

sleep 2

echo "Disabling smooth movement..."
curl -X POST "http://localhost:8000/servos/config" \
     -H "Content-Type: application/json" \
     -d '{"detach_enabled": true, "hold_time": 0.5, "min_pulse_width": 0.0005, "max_pulse_width": 0.0025, "hold_mode": "auto", "smooth_enabled": false, "smooth_steps": 10, "smooth_delay": 0.05}'
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