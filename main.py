from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from gpiozero import Servo
from typing import Dict, List, Optional
from contextlib import asynccontextmanager
import warnings
import time
import threading
import uvicorn
import json
import asyncio

# Suppress gpiozero warnings for cleaner output
warnings.filterwarnings("ignore", category=UserWarning, module="gpiozero")

# GPIO pins array - add or remove pins as needed
gpio_pins = [13, 6, 19, 26]

# Servo configuration
SERVO_HOLD_TIME = 1.0  # Time to hold position before detaching (seconds)
SERVO_DETACH_ENABLED = True  # Enable/disable auto-detach to reduce jitter
SERVO_MIN_PULSE_WIDTH = 0.5 / 1000  # Minimum pulse width in seconds (0.5ms)
SERVO_MAX_PULSE_WIDTH = 2.5 / 1000  # Maximum pulse width in seconds (2.5ms)
SERVO_HOLD_MODE = "auto"  # Servo hold mode: auto, hold, release
SERVO_SMOOTH_ENABLED = False  # Enable smooth movement
SERVO_SMOOTH_STEPS = 10  # Number of steps for smooth movement
SERVO_SMOOTH_DELAY = 0.05  # Delay between smooth movement steps

# Global state tracking
servo_states = {}
servos = {}
servo_lock = threading.Lock()
servo_timers = {}  # Timers for auto-detach functionality

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except:
            self.disconnect(websocket)

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                disconnected.append(connection)
        
        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

manager = ConnectionManager()

# Lifespan event handler for startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize servos
    initialize_servos()
    yield
    # Shutdown: Cleanup servos
    cleanup_servos()

# Create FastAPI app with lifespan handler
app = FastAPI(
    title="Servo Control API",
    description="REST API for controlling multiple servos on Raspberry Pi",
    version="1.0.0",
    lifespan=lifespan
)

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

class ServoStatusResponse(BaseModel):
    servo: Dict[str, ServoStatus]

class ServoConfig(BaseModel):
    detach_enabled: bool = Field(default=True, description="Enable auto-detach to reduce jitter")
    hold_time: float = Field(default=1.0, ge=0.1, le=10.0, description="Time to hold position before detaching (seconds)")
    min_pulse_width: float = Field(default=0.0001, ge=0.0001, le=0.002, description="Minimum pulse width in seconds (0.1ms to 2ms)")
    max_pulse_width: float = Field(default=0.0005, ge=0.002, le=0.003, description="Maximum pulse width in seconds (2ms to 3ms)")
    hold_mode: str = Field(default="auto", description="Servo hold mode: 'auto' (auto-detach), 'hold' (always powered), 'release' (always released)")
    smooth_enabled: bool = Field(default=False, description="Enable smooth movement with gradual position changes")
    smooth_steps: int = Field(default=10, ge=3, le=50, description="Number of steps for smooth movement")
    smooth_delay: float = Field(default=0.05, ge=0.01, le=0.2, description="Delay between smooth movement steps (seconds)")

class ServoConfigResponse(BaseModel):
    success: bool
    message: str
    config: ServoConfig

# Initialize servos
def initialize_servos():
    """Initialize all servos and set up state tracking"""
    global servos, servo_states
    
    # First cleanup any existing servos to prevent GPIO conflicts
    cleanup_servos()
    
    print("Initializing servos for API...")
    servos.clear()
    servo_states.clear()
    
    for i, pin in enumerate(gpio_pins, 1):
        try:
            servos[i] = Servo(pin, min_pulse_width=SERVO_MIN_PULSE_WIDTH, max_pulse_width=SERVO_MAX_PULSE_WIDTH)
            servo_states[i] = {
                "gpio_pin": pin,
                "current_angle": 90,  # Default to center position
                "is_active": True,
                "last_updated": None
            }
            # Set initial position to center
            set_servo_angle(i, 90, update_state=False)
            print(f"  Servo {i} initialized on GPIO pin {pin} (pulse: {SERVO_MIN_PULSE_WIDTH*1000:.1f}-{SERVO_MAX_PULSE_WIDTH*1000:.1f}ms)")
        except Exception as e:
            print(f"  Error initializing servo {i} on GPIO pin {pin}: {e}")
            servo_states[i] = {
                "gpio_pin": pin,
                "current_angle": None,
                "is_active": False,
                "last_updated": None
            }
    print("Servo initialization complete.\n")

def detach_servo(servo_id: int):
    """Detach servo to stop PWM signal and reduce jitter"""
    if servo_id in servos and SERVO_DETACH_ENABLED:
        try:
            servos[servo_id].detach()
            print(f"Servo {servo_id} detached to reduce jitter")
        except Exception as e:
            print(f"Error detaching servo {servo_id}: {e}")

def attach_servo(servo_id: int):
    """Re-attach servo for movement"""
    if servo_id in servos:
        try:
            # Re-create servo if it was detached
            pin = servo_states[servo_id]["gpio_pin"]
            servos[servo_id] = Servo(pin, min_pulse_width=SERVO_MIN_PULSE_WIDTH, max_pulse_width=SERVO_MAX_PULSE_WIDTH)
            print(f"Servo {servo_id} re-attached for movement")
        except Exception as e:
            print(f"Error re-attaching servo {servo_id}: {e}")

def schedule_servo_detach(servo_id: int):
    """Schedule servo detachment after hold time"""
    if not SERVO_DETACH_ENABLED:
        return
        
    # Cancel any existing timer
    if servo_id in servo_timers:
        servo_timers[servo_id].cancel()
    
    # Schedule new detachment
    timer = threading.Timer(SERVO_HOLD_TIME, detach_servo, args=[servo_id])
    servo_timers[servo_id] = timer
    timer.start()

async def set_servo_angle_smooth(servo_id: int, target_angle: int, update_state: bool = True):
    """Move servo smoothly to target angle with gradual steps"""
    if servo_id not in servos:
        raise ValueError(f"Servo {servo_id} not found")
    
    if not servo_states[servo_id]["is_active"]:
        raise ValueError(f"Servo {servo_id} is not active")
    
    # Handle servo attachment based on hold mode
    if SERVO_HOLD_MODE == "release":
        print(f"Servo {servo_id} in release mode - skipping movement")
        return
    elif SERVO_HOLD_MODE == "hold":
        attach_servo(servo_id)
    else:  # auto mode
        attach_servo(servo_id)
    
    # Get current angle
    current_angle = servo_states[servo_id]["current_angle"]
    if current_angle is None:
        current_angle = 90  # Default to center if unknown
    
    # Calculate step size
    angle_diff = target_angle - current_angle
    if abs(angle_diff) <= 1:
        # If difference is very small, just move directly
        servos[servo_id].angle = target_angle / 90.0 - 1.0
        if update_state:
            servo_states[servo_id]["current_angle"] = target_angle
            servo_states[servo_id]["last_updated"] = datetime.now().isoformat()
        await asyncio.sleep(0.1)
        return
    
    step_size = angle_diff / SERVO_SMOOTH_STEPS
    
    # Move in smooth steps
    for step in range(SERVO_SMOOTH_STEPS):
        intermediate_angle = current_angle + (step + 1) * step_size
        intermediate_angle = max(0, min(180, round(intermediate_angle)))  # Clamp to valid range
        
        # Convert to servo value (-1 to +1)
        servo_value = intermediate_angle / 90.0 - 1.0
        servos[servo_id].angle = servo_value
        
        # Update state for final step
        if step == SERVO_SMOOTH_STEPS - 1 and update_state:
            servo_states[servo_id]["current_angle"] = target_angle
            servo_states[servo_id]["last_updated"] = datetime.now().isoformat()
        
        await asyncio.sleep(SERVO_SMOOTH_DELAY)
    
    # Schedule detachment based on hold mode
    if SERVO_HOLD_MODE == "auto" and SERVO_DETACH_ENABLED:
        schedule_servo_detach(servo_id)
    elif SERVO_HOLD_MODE == "release":
        detach_servo(servo_id)

def set_servo_angle(servo_id: int, angle: int, update_state: bool = True):
    """Set servo angle with state tracking and jitter reduction"""
    if servo_id not in servos:
        raise ValueError(f"Servo {servo_id} not found")
    
    if not servo_states[servo_id]["is_active"]:
        raise ValueError(f"Servo {servo_id} is not active")
    
    # Handle servo attachment based on hold mode
    if SERVO_HOLD_MODE == "release":
        # In release mode, don't attach servo (keep it unpowered)
        print(f"Servo {servo_id} in release mode - skipping movement")
        return
    elif SERVO_HOLD_MODE == "hold":
        # In hold mode, attach servo and keep it powered
        attach_servo(servo_id)
    else:  # auto mode
        # Re-attach servo if it was detached
        attach_servo(servo_id)
    
    # Convert 0–180° to -1..+1
    value = (angle - 90) / 90
    
    with servo_lock:
        servos[servo_id].value = value
        if update_state:
            servo_states[servo_id]["current_angle"] = angle
            servo_states[servo_id]["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    time.sleep(0.5)  # Give servo time to reach target
    
    # Schedule detachment based on hold mode
    if SERVO_HOLD_MODE == "auto" and SERVO_DETACH_ENABLED:
        schedule_servo_detach(servo_id)
    elif SERVO_HOLD_MODE == "release":
        # Immediately detach in release mode
        detach_servo(servo_id)

async def broadcast_servo_status():
    """Broadcast current servo status to all connected WebSocket clients"""
    try:
        status_dict = {}
        for servo_id, state in servo_states.items():
            status_dict[str(servo_id)] = {
                "servo_id": servo_id,
                "gpio_pin": state["gpio_pin"],
                "current_angle": state["current_angle"],
                "is_active": state["is_active"],
                "last_updated": state["last_updated"]
            }
        
        message = json.dumps({
            "type": "servo_status_update",
            "data": {"servo": status_dict}
        })
        
        await manager.broadcast(message)
    except Exception as e:
        print(f"Error broadcasting servo status: {e}")

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
async def get_servo_status() -> ServoStatusResponse:
    """Get current status of all servos"""
    status_dict = {}
    for servo_id, state in servo_states.items():
        status_dict[str(servo_id)] = ServoStatus(
            servo_id=servo_id,
            gpio_pin=state["gpio_pin"],
            current_angle=state["current_angle"],
            is_active=state["is_active"],
            last_updated=state["last_updated"]
        )
    return ServoStatusResponse(servo=status_dict)

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
    """Move a specific servo to the specified angle"""
    if servo_id not in servos:
        raise HTTPException(status_code=404, detail=f"Servo {servo_id} not found")
    
    try:
        if SERVO_SMOOTH_ENABLED:
            await set_servo_angle_smooth(servo_id, request.angle)
        else:
            set_servo_angle(servo_id, request.angle)
        
        # Broadcast status update to WebSocket clients
        await broadcast_servo_status()
        
        movement_type = "smoothly moved" if SERVO_SMOOTH_ENABLED else "moved"
        return ServoResponse(
            success=True,
            message=f"Servo {servo_id} {movement_type} to {request.angle}°",
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
    
    # Broadcast status update to WebSocket clients
    await broadcast_servo_status()
    
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
        if SERVO_SMOOTH_ENABLED:
            await set_servo_angle_smooth(servo_id, 90)
        else:
            set_servo_angle(servo_id, 90)
        
        # Broadcast status update to WebSocket clients
        await broadcast_servo_status()
        
        movement_type = "smoothly centered" if SERVO_SMOOTH_ENABLED else "centered"
        return ServoResponse(
            success=True,
            message=f"Servo {servo_id} {movement_type} at 90°",
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
    
    # Broadcast status update to WebSocket clients
    await broadcast_servo_status()
    
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

@app.post("/servos/{servo_id}/hold", summary="Hold Single Servo")
async def hold_servo(servo_id: int) -> ServoResponse:
    """Attach and hold a specific servo in its current position"""
    if servo_id not in servos:
        raise HTTPException(status_code=404, detail=f"Servo {servo_id} not found")
    
    try:
        # Cancel any pending detach timer
        if servo_id in servo_timers:
            servo_timers[servo_id].cancel()
            del servo_timers[servo_id]
        
        # Attach servo to hold position
        attach_servo(servo_id)
        
        # Broadcast status update to WebSocket clients
        await broadcast_servo_status()
        
        current_angle = servo_states[servo_id]["current_angle"]
        return ServoResponse(
            success=True,
            message=f"Servo {servo_id} is now held at {current_angle}°",
            servo_id=servo_id,
            angle=current_angle
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error holding servo: {str(e)}")

@app.post("/servos/{servo_id}/release", summary="Release Single Servo")
async def release_servo(servo_id: int) -> ServoResponse:
    """Release (detach) a specific servo to reduce power consumption and jitter"""
    if servo_id not in servos:
        raise HTTPException(status_code=404, detail=f"Servo {servo_id} not found")
    
    try:
        # Cancel any pending detach timer
        if servo_id in servo_timers:
            servo_timers[servo_id].cancel()
            del servo_timers[servo_id]
        
        # Detach servo
        detach_servo(servo_id)
        
        # Broadcast status update to WebSocket clients
        await broadcast_servo_status()
        
        current_angle = servo_states[servo_id]["current_angle"]
        return ServoResponse(
            success=True,
            message=f"Servo {servo_id} released (was at {current_angle}°)",
            servo_id=servo_id,
            angle=current_angle
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error releasing servo: {str(e)}")

@app.post("/servos/hold-all", summary="Hold All Servos")
async def hold_all_servos() -> ServoResponse:
    """Attach and hold all servos in their current positions"""
    held_servos = []
    
    for servo_id in servos.keys():
        try:
            # Cancel any pending detach timer
            if servo_id in servo_timers:
                servo_timers[servo_id].cancel()
                del servo_timers[servo_id]
            
            # Attach servo to hold position
            attach_servo(servo_id)
            held_servos.append(servo_id)
        except Exception as e:
            print(f"Error holding servo {servo_id}: {e}")
    
    # Broadcast status update to WebSocket clients
    await broadcast_servo_status()
    
    return ServoResponse(
        success=True,
        message=f"All servos are now held. Affected servos: {held_servos}"
    )

@app.post("/servos/release-all", summary="Release All Servos")
async def release_all_servos() -> ServoResponse:
    """Release (detach) all servos to reduce power consumption and jitter"""
    released_servos = []
    
    for servo_id in servos.keys():
        try:
            # Cancel any pending detach timer
            if servo_id in servo_timers:
                servo_timers[servo_id].cancel()
                del servo_timers[servo_id]
            
            # Detach servo
            detach_servo(servo_id)
            released_servos.append(servo_id)
        except Exception as e:
            print(f"Error releasing servo {servo_id}: {e}")
    
    # Broadcast status update to WebSocket clients
    await broadcast_servo_status()
    
    return ServoResponse(
        success=True,
        message=f"All servos released. Affected servos: {released_servos}"
    )

@app.get("/servos/config", summary="Get Servo Configuration")
async def get_servo_config() -> ServoConfigResponse:
    """Get current servo configuration settings"""
    config = ServoConfig(
        detach_enabled=SERVO_DETACH_ENABLED,
        hold_time=SERVO_HOLD_TIME,
        min_pulse_width=SERVO_MIN_PULSE_WIDTH,
        max_pulse_width=SERVO_MAX_PULSE_WIDTH,
        hold_mode=SERVO_HOLD_MODE,
        smooth_enabled=SERVO_SMOOTH_ENABLED,
        smooth_steps=SERVO_SMOOTH_STEPS,
        smooth_delay=SERVO_SMOOTH_DELAY
    )
    return ServoConfigResponse(
        success=True,
        message="Current servo configuration",
        config=config
    )

@app.post("/servos/config", summary="Update Servo Configuration")
async def update_servo_config(config: ServoConfig) -> ServoConfigResponse:
    """Update servo configuration settings to reduce jitter"""
    global SERVO_DETACH_ENABLED, SERVO_HOLD_TIME, SERVO_MIN_PULSE_WIDTH, SERVO_MAX_PULSE_WIDTH, SERVO_HOLD_MODE
    global SERVO_SMOOTH_ENABLED, SERVO_SMOOTH_STEPS, SERVO_SMOOTH_DELAY
    
    # Validate hold_mode
    if config.hold_mode not in ["auto", "hold", "release"]:
        raise HTTPException(status_code=400, detail="hold_mode must be 'auto', 'hold', or 'release'")
    
    SERVO_DETACH_ENABLED = config.detach_enabled
    SERVO_HOLD_TIME = config.hold_time
    SERVO_MIN_PULSE_WIDTH = config.min_pulse_width
    SERVO_MAX_PULSE_WIDTH = config.max_pulse_width
    SERVO_HOLD_MODE = config.hold_mode
    SERVO_SMOOTH_ENABLED = config.smooth_enabled
    SERVO_SMOOTH_STEPS = config.smooth_steps
    SERVO_SMOOTH_DELAY = config.smooth_delay
    
    # Handle mode-specific actions
    if config.hold_mode == "release":
        # Release all servos immediately
        for servo_id in servos.keys():
            detach_servo(servo_id)
        # Cancel all timers
        for timer in servo_timers.values():
            timer.cancel()
        servo_timers.clear()
    elif config.hold_mode == "hold":
        # Attach all servos and cancel timers
        for servo_id in servos.keys():
            attach_servo(servo_id)
        for timer in servo_timers.values():
            timer.cancel()
        servo_timers.clear()
    elif not SERVO_DETACH_ENABLED:
        # Cancel all existing timers if detach is disabled in auto mode
        for timer in servo_timers.values():
            timer.cancel()
        servo_timers.clear()
    
    # Re-initialize servos with new pulse width settings
    smooth_info = f", Smooth: {config.smooth_enabled} ({config.smooth_steps} steps, {config.smooth_delay}s delay)" if config.smooth_enabled else ""
    print(f"Updating servo configuration - Mode: {config.hold_mode}, Pulse: {SERVO_MIN_PULSE_WIDTH*1000:.1f}-{SERVO_MAX_PULSE_WIDTH*1000:.1f}ms{smooth_info}")
    initialize_servos()
    
    return ServoConfigResponse(
        success=True,
        message=f"Servo configuration updated. Mode: {config.hold_mode}, Detach: {config.detach_enabled}, Hold time: {config.hold_time}s, Pulse: {config.min_pulse_width*1000:.1f}-{config.max_pulse_width*1000:.1f}ms, Smooth: {config.smooth_enabled}",
        config=config
    )

@app.websocket("/ws/servos/status")
async def websocket_servo_status(websocket: WebSocket):
    """WebSocket endpoint for real-time servo status updates"""
    await manager.connect(websocket)
    try:
        # Send initial status when client connects
        await broadcast_servo_status()
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client (ping/pong or requests)
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle different message types
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif message.get("type") == "get_status":
                    await broadcast_servo_status()
                    
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format"
                }))
            except Exception as e:
                await websocket.send_text(json.dumps({
                    "type": "error", 
                    "message": f"Error: {str(e)}"
                }))
                
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)

# Cleanup function
def cleanup_servos():
    """Clean up servo resources"""
    global servos, servo_states, servo_timers
    
    if not servos:
        return
        
    print("Cleaning up servos...")
    
    # Cancel all pending timers
    for timer in servo_timers.values():
        timer.cancel()
    servo_timers.clear()
    print("  All servo timers cancelled")
    
    # Detach all servos
    for servo_id, servo in list(servos.items()):
        try:
            servo.detach()
            print(f"  Servo {servo_id} detached")
        except Exception as e:
            print(f"  Error detaching servo {servo_id}: {e}")
    
    # Clear the dictionaries
    servos.clear()
    servo_states.clear()

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