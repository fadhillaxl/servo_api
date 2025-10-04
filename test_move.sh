# 1. Check if API is running
curl http://localhost:8004/

# 2. List available servos
curl http://localhost:8004/servos

# 3. Move servo 1 to different positions
curl -X POST "http://localhost:8004/servos/1/move" -H "Content-Type: application/json" -d '{"angle": 0}'
sleep 2
curl -X POST "http://localhost:8004/servos/1/move" -H "Content-Type: application/json" -d '{"angle": 90}'
sleep 2
curl -X POST "http://localhost:8004/servos/1/move" -H "Content-Type: application/json" -d '{"angle": 180}'

# 4. Move all servos to center
curl -X POST "http://localhost:8004/servos/center-all"