from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from gpiozero import Servo
from typing import Dict, List, Optional
import warnings
import time
import threading
import uvicorn

# Suppress gpiozero warnings for cleaner output
warnings.filterwarnings("ignore", category=UserWarning, module="gpiozero")

app = FastAPI(
    title="Servo Control API",
    description="REST API for controlling multiple servos on Raspberry Pi",
    version="1.0.0"
)

# GPIO pins array - add or remove pins as needed
gpio_pins = [13, 18, 19, 26]

# Global servo state tracking
servo_states = {}
servos = {}
servo_lock = threading.Lock()

# Pydantic models for request/response
class ServoMoveRequest(BaseModel):
    angle: int = Field(..., ge=0, le=180, description="Angle between 0 and 180 degrees")

class ServoMoveAllRequest(BaseModel):
    angle: int = Field(..., ge=0, le=180, description="Angle between 0 and 180 degrees")

class ServoStatus(BaseModel):
    servo_id: int
    gpio_pin: int
    current_angle: Optional[int]
    is_active: bool
    last_updated: Optional[str]

class ServoResponse(BaseModel):
    success: bool
    message: str
    servo_id: Optional[int] = None
    angle: Optional[int] = None

# Initialize servos
def initialize_servos():
    """Initialize all servos and set up state tracking"""
    global servos, servo_states
    
    print("Initializing servos for API...")
    for i, pin in enumerate(gpio_pins, 1):
        try:
            servos[i] = Servo(pin, min_pulse_width=0.5/1000, max_pulse_width=2.5/1000)
            servo_states[i] = {
                "gpio_pin": pin,
                "current_angle": 90,  # Default to center position
                "is_active": True,
                "last_updated": None
            }
            # Set initial position to center
            set_servo_angle(i, 90, update_state=False)
            print(f"  Servo {i} initialized on GPIO pin {pin}")
        except Exception as e:
            print(f"  Error initializing servo {i} on GPIO pin {pin}: {e}")
            servo_states[i] = {
                "gpio_pin": pin,
                "current_angle": None,
                "is_active": False,
                "last_updated": None
            }
    print("Servo initialization complete.\n")

def set_servo_angle(servo_id: int, angle: int, update_state: bool = True):
    """Set servo angle with state tracking"""
    if servo_id not in servos:
        raise ValueError(f"Servo {servo_id} not found")
    
    if not servo_states[servo_id]["is_active"]:
        raise ValueError(f"Servo {servo_id} is not active")
    
    # Convert 0–180° to -1..+1
    value = (angle - 90) / 90
    
    with servo_lock:
        servos[servo_id].value = value
        if update_state:
            servo_states[servo_id]["current_angle"] = angle
            servo_states[servo_id]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    time.sleep(0.5)  # Give servo time to reach target

# Initialize servos on startup
initialize_servos()

# API Endpoints

@app.get("/", summary="API Information")
async def root():
    """Get basic API information"""
    return {
        "message": "Servo Control API",
        "version": "1.0.0",
        "endpoints": {
            "status": "/servos/status",
            "move_servo": "/servos/{servo_id}/move",
            "move_all": "/servos/move-all",
            "list_servos": "/servos"
        }
    }

@app.get("/servos", summary="List All Servos")
async def list_servos() -> List[ServoStatus]:
    """Get list of all available servos"""
    servo_list = []
    for servo_id, state in servo_states.items():
        servo_list.append(ServoStatus(
            servo_id=servo_id,
            gpio_pin=state["gpio_pin"],
            current_angle=state["current_angle"],
            is_active=state["is_active"],
            last_updated=state["last_updated"]
        ))
    return servo_list

@app.get("/servos/status", summary="Get All Servo Status")
async def get_servo_status() -> Dict[str, ServoStatus]:
    """Get current status of all servos"""
    status_dict = {}
    for servo_id, state in servo_states.items():
        status_dict[f"servo_{servo_id}"] = ServoStatus(
            servo_id=servo_id,
            gpio_pin=state["gpio_pin"],
            current_angle=state["current_angle"],
            is_active=state["is_active"],
            last_updated=state["last_updated"]
        )
    return status_dict

@app.get("/servos/{servo_id}/status", summary="Get Single Servo Status")
async def get_single_servo_status(servo_id: int) -> ServoStatus:
    """Get status of a specific servo"""
    if servo_id not in servo_states:
        raise HTTPException(status_code=404, detail=f"Servo {servo_id} not found")
    
    state = servo_states[servo_id]
    return ServoStatus(
        servo_id=servo_id,
        gpio_pin=state["gpio_pin"],
        current_angle=state["current_angle"],
        is_active=state["is_active"],
        last_updated=state["last_updated"]
    )

@app.post("/servos/{servo_id}/move", summary="Move Single Servo")
async def move_servo(servo_id: int, request: ServoMoveRequest) -> ServoResponse:
    """Move a specific servo to the given angle"""
    if servo_id not in servos:
        raise HTTPException(status_code=404, detail=f"Servo {servo_id} not found")
    
    try:
        set_servo_angle(servo_id, request.angle)
        return ServoResponse(
            success=True,
            message=f"Servo {servo_id} moved to {request.angle}°",
            servo_id=servo_id,
            angle=request.angle
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error moving servo: {str(e)}")

@app.post("/servos/move-all", summary="Move All Servos")
async def move_all_servos(request: ServoMoveAllRequest) -> ServoResponse:
    """Move all active servos to the same angle"""
    moved_servos = []
    errors = []
    
    for servo_id in servos.keys():
        try:
            if servo_states[servo_id]["is_active"]:
                set_servo_angle(servo_id, request.angle)
                moved_servos.append(servo_id)
        except Exception as e:
            errors.append(f"Servo {servo_id}: {str(e)}")
    
    if errors:
        raise HTTPException(
            status_code=207,  # Multi-status
            detail=f"Partial success. Moved servos: {moved_servos}. Errors: {errors}"
        )
    
    return ServoResponse(
        success=True,
        message=f"All servos moved to {request.angle}°. Affected servos: {moved_servos}",
        angle=request.angle
    )

@app.post("/servos/{servo_id}/center", summary="Center Single Servo")
async def center_servo(servo_id: int) -> ServoResponse:
    """Move a specific servo to center position (90°)"""
    if servo_id not in servos:
        raise HTTPException(status_code=404, detail=f"Servo {servo_id} not found")
    
    try:
        set_servo_angle(servo_id, 90)
        return ServoResponse(
            success=True,
            message=f"Servo {servo_id} centered at 90°",
            servo_id=servo_id,
            angle=90
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error centering servo: {str(e)}")

@app.post("/servos/center-all", summary="Center All Servos")
async def center_all_servos() -> ServoResponse:
    """Move all active servos to center position (90°)"""
    moved_servos = []
    errors = []
    
    for servo_id in servos.keys():
        try:
            if servo_states[servo_id]["is_active"]:
                set_servo_angle(servo_id, 90)
                moved_servos.append(servo_id)
        except Exception as e:
            errors.append(f"Servo {servo_id}: {str(e)}")
    
    if errors:
        raise HTTPException(
            status_code=207,
            detail=f"Partial success. Centered servos: {moved_servos}. Errors: {errors}"
        )
    
    return ServoResponse(
        success=True,
        message=f"All servos centered at 90°. Affected servos: {moved_servos}",
        angle=90
    )

# Cleanup function
def cleanup_servos():
    """Cleanup all servos on shutdown"""
    print("Cleaning up servos...")
    for servo_id, servo in servos.items():
        try:
            servo.detach()
            print(f"Servo {servo_id} detached")
        except Exception as e:
            print(f"Error detaching servo {servo_id}: {e}")

# Register cleanup on app shutdown
@app.on_event("shutdown")
async def shutdown_event():
    cleanup_servos()

if __name__ == "__main__":
    try:
        print("Starting Servo Control API server...")
        print("API Documentation available at: http://localhost:8004/docs")
        print("Alternative docs at: http://localhost:8004/redoc")
        print("Press Ctrl+C to stop the server\n")
        
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8004,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\nShutting down server...")
        cleanup_servos()
    except Exception as e:
        print(f"Error starting server: {e}")
        cleanup_servos()