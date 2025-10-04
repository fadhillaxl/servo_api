# Servo Jitter Reduction Solutions

This document explains the comprehensive servo jitter reduction features implemented in the Servo Control API.

## Problem: Servo Jitter

Servo jitter is a common issue where servos exhibit small, unwanted movements or vibrations when they should be stationary. This is typically caused by:

1. **Continuous PWM signals** - Servos receive constant control signals even when stationary
2. **PWM signal noise** - Electrical interference in the control signal
3. **Power supply fluctuations** - Voltage variations affecting servo performance
4. **Mechanical backlash** - Play in the servo's internal gears
5. **Control loop oscillation** - The servo's internal feedback system overcompensating

## Solutions Implemented

### 1. Servo Detach Functionality ✅

**Purpose**: Stop PWM signals after servo reaches target position to eliminate continuous signal noise.

**How it works**:
- Servo attaches (powers on) before movement
- Moves to target position
- Automatically detaches after a configurable hold time
- Eliminates continuous PWM signal that causes jitter

**Configuration**:
- `detach_enabled`: Enable/disable auto-detach (default: true)
- `hold_time`: Time to hold position before detaching (0.1-10.0 seconds, default: 1.0)

**API Endpoints**:
- `POST /servos/{servo_id}/hold` - Manually hold a servo in position
- `POST /servos/{servo_id}/release` - Manually release (detach) a servo
- `POST /servos/hold-all` - Hold all servos
- `POST /servos/release-all` - Release all servos

### 2. Configurable Pulse Width Parameters ✅

**Purpose**: Fine-tune PWM signal characteristics for optimal servo control.

**How it works**:
- Allows adjustment of minimum and maximum pulse widths
- Different servos may respond better to different pulse width ranges
- Reduces signal-related jitter by optimizing PWM timing

**Configuration**:
- `min_pulse_width`: Minimum pulse width (0.1-2.0ms, default: 0.5ms)
- `max_pulse_width`: Maximum pulse width (2.0-3.0ms, default: 2.5ms)

**Benefits**:
- Better compatibility with different servo models
- Reduced electrical noise
- More precise positioning

### 3. Servo Hold/Release Modes ✅

**Purpose**: Provide different power management strategies for various use cases.

**Modes Available**:

#### Auto Mode (default)
- Servos attach before movement
- Auto-detach after hold time (if enabled)
- Best for general use with minimal power consumption

#### Hold Mode
- Servos remain powered continuously
- No auto-detach functionality
- Best for applications requiring constant position holding
- Higher power consumption but maximum holding torque

#### Release Mode
- Servos are immediately released after movement
- Minimal power consumption
- Best for applications where position holding isn't critical
- Servos can be moved manually when released

**Configuration**:
- `hold_mode`: "auto", "hold", or "release" (default: "auto")

### 4. Servo Movement Smoothing ✅

**Purpose**: Eliminate sudden movements that can cause mechanical jitter and stress.

**How it works**:
- Breaks large movements into smaller, gradual steps
- Configurable number of steps and delay between steps
- Reduces mechanical shock and vibration
- Provides smoother, more natural movement

**Configuration**:
- `smooth_enabled`: Enable/disable smooth movement (default: false)
- `smooth_steps`: Number of intermediate steps (3-50, default: 10)
- `smooth_delay`: Delay between steps (0.01-0.2 seconds, default: 0.05)

**Benefits**:
- Reduced mechanical stress on servo gears
- Smoother visual movement
- Less vibration transmitted to mounting structure
- More precise final positioning

## Configuration API

### Get Current Configuration
```bash
curl -X GET "http://localhost:8000/servos/config"
```

### Update Configuration
```bash
curl -X POST "http://localhost:8000/servos/config" \
     -H "Content-Type: application/json" \
     -d '{
       "detach_enabled": true,
       "hold_time": 0.5,
       "min_pulse_width": 0.0006,
       "max_pulse_width": 0.0024,
       "hold_mode": "auto",
       "smooth_enabled": true,
       "smooth_steps": 15,
       "smooth_delay": 0.03
     }'
```

## Recommended Settings for Different Use Cases

### Minimal Jitter (Recommended)
```json
{
  "detach_enabled": true,
  "hold_time": 0.3,
  "min_pulse_width": 0.0006,
  "max_pulse_width": 0.0024,
  "hold_mode": "auto",
  "smooth_enabled": true,
  "smooth_steps": 15,
  "smooth_delay": 0.03
}
```

### Maximum Precision
```json
{
  "detach_enabled": false,
  "hold_time": 1.0,
  "min_pulse_width": 0.0005,
  "max_pulse_width": 0.0025,
  "hold_mode": "hold",
  "smooth_enabled": true,
  "smooth_steps": 20,
  "smooth_delay": 0.02
}
```

### Power Saving
```json
{
  "detach_enabled": true,
  "hold_time": 0.1,
  "min_pulse_width": 0.0005,
  "max_pulse_width": 0.0025,
  "hold_mode": "release",
  "smooth_enabled": false,
  "smooth_steps": 10,
  "smooth_delay": 0.05
}
```

### Fast Response
```json
{
  "detach_enabled": false,
  "hold_time": 0.5,
  "min_pulse_width": 0.0005,
  "max_pulse_width": 0.0025,
  "hold_mode": "hold",
  "smooth_enabled": false,
  "smooth_steps": 10,
  "smooth_delay": 0.05
}
```

## Testing

Use the updated `test_move.sh` script to test all jitter reduction features:

```bash
./test_move.sh
```

The script includes comprehensive tests for:
- Basic servo movement
- Configuration changes
- Hold/release functionality
- Smooth movement
- WebSocket real-time updates

## WebSocket Integration

All jitter reduction features work seamlessly with the WebSocket API for real-time status updates. Connect to `/ws/servos/status` to monitor servo states during testing.

## Troubleshooting

### Still experiencing jitter?
1. Try reducing `hold_time` to 0.1-0.3 seconds
2. Enable smooth movement with more steps (15-20)
3. Adjust pulse width parameters for your specific servo model
4. Check power supply stability
5. Ensure proper servo mounting to reduce vibration

### Servo not responding?
1. Verify pulse width parameters are compatible with your servo
2. Check if servo is in "release" mode
3. Ensure proper GPIO pin connections
4. Verify power supply voltage and current capacity

### Slow movement?
1. Disable smooth movement for faster response
2. Reduce `smooth_steps` and `smooth_delay`
3. Use "hold" mode for immediate response
4. Reduce `hold_time` for faster detachment