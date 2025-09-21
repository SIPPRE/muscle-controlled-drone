"""
Tello Drone EMG Control with Direct LSL Connection
-------------------------------------------------
This program controls a DJI Tello drone using EMG signals from OpenBCI Ganglion via LSL.
It uses a direct connection approach that should work with any LSL stream format.

Control scheme:
- Press 't' to take off
- Press 'l' to land
- Press 'r' to rotate clockwise (hold for continuous rotation)
- Press 'R' to rotate counter-clockwise (hold for continuous rotation)
- EMG signals control forward/backward movement when airborne
"""

import time
import numpy as np
from threading import Thread
import sys

# Use pygame for keyboard control instead of the keyboard module
# This doesn't require root access on Linux
import pygame

try:
    # Import pylsl directly from examples (which we know works)
    from pylsl.examples import ReceiveData
    print("Using pylsl from examples")
    
    # Import whatever works
    try:
        from pylsl import StreamInlet, resolve_stream
        print("Using standard pylsl import")
    except ImportError:
        try:
            from pylsl import StreamInlet
            from pylsl import resolve_byprop
            print("Using alternative pylsl import")
        except ImportError:
            print("Error importing pylsl. Using direct connection method only.")
except ImportError:
    print("Could not import pylsl.examples. Using standard imports.")
    try:
        from pylsl import StreamInlet, resolve_stream
        print("Using standard pylsl import")
    except ImportError:
        try:
            from pylsl import StreamInlet
            from pylsl import resolve_byprop
            print("Using alternative pylsl import")
        except ImportError:
            print("Error importing pylsl. Please install with: pip install pylsl")
            sys.exit(1)

try:
    from djitellopy import Tello
except ImportError:
    print("Warning: djitellopy not found. Simulation mode will be used.")

# Simulator class for testing without a physical drone
class TelloSimulator:
    """Simulates basic Tello drone functions for testing."""
    
    def __init__(self):
        self.battery = 100
        self.speed = 0
        self.position = [0, 0, 0]  # x, y, z
        self.is_flying = False
        print("SIMULATOR: Tello simulator initialized")
        
    def connect(self):
        print("SIMULATOR: Connected to virtual Tello")
        return True
        
    def get_battery(self):
        return self.battery
        
    def set_speed(self, speed):
        self.speed = speed
        print(f"SIMULATOR: Speed set to {speed}")
        
    def takeoff(self):
        print("SIMULATOR: Taking off")
        self.is_flying = True
        self.position[2] = 100  # cm above ground
        
    def land(self):
        print("SIMULATOR: Landing")
        self.is_flying = False
        self.position = [0, 0, 0]
        
    def send_rc_control(self, left_right, forward_backward, up_down, yaw):
        if not self.is_flying:
            return
            
        self.position[0] += left_right * 0.1
        self.position[1] += forward_backward * 0.1
        self.position[2] += up_down * 0.1
        
        # Print position and movement
        movement = []
        if forward_backward > 0:
            movement.append(f"Forward({forward_backward})")
        elif forward_backward < 0:
            movement.append(f"Backward({abs(forward_backward)})")
            
        if left_right > 0:
            movement.append(f"Right({left_right})")
        elif left_right < 0:
            movement.append(f"Left({abs(left_right)})")
            
        if up_down > 0:
            movement.append(f"Up({up_down})")
        elif up_down < 0:
            movement.append(f"Down({abs(up_down)})")
            
        if yaw > 0:
            movement.append(f"Rotate CW({yaw})")
        elif yaw < 0:
            movement.append(f"Rotate CCW({abs(yaw)})")
            
        if movement:
            movement_str = ", ".join(movement)
            print(f"SIMULATOR: {movement_str} - Position: {self.position}")
        
    def end(self):
        print("SIMULATOR: Tello session ended")

class TelloEMGControl:
    def __init__(self):
        # EMG parameters
        self.joystick_data = [0.0, 0.0]  # Initialize with neutral position
        self.emg_buffer_size = 10
        self.emg_buffer = np.zeros((self.emg_buffer_size, 2))  # Buffer for x,y values
        
        # Drone parameters
        self.drone = None
        self.is_flying = False
        self.speed = 30  # Drone speed (0-100)
        
        # LSL stream parameters
        self.inlet = None
        self.stream_type = "UNKNOWN"
        
        # Debug mode for testing
        self.debug_mode = True
        
        # Control flags
        self.running = True
        
    def connect_to_drone(self):
        """Connect to the Tello drone."""
        try:
            print("Connecting to Tello drone...")
            self.drone = Tello()
            self.drone.connect()
            
            # Check battery
            battery = self.drone.get_battery()
            print(f"Tello battery: {battery}%")
            if battery < 20:
                print("WARNING: Low battery! Please charge before flying.")
                
            # Set speed
            self.drone.set_speed(self.speed)
            print(f"Drone speed set to {self.speed}")
            return True
        except Exception as e:
            print(f"Failed to connect to drone: {e}")
            print("Continuing in simulation mode...")
            self.drone = TelloSimulator()  # Use simulator instead
            return True
            
    def connect_to_lsl_direct(self):
        """Connect directly to first available LSL stream without filtering."""
        print("Looking for ANY LSL stream...")
        
        try:
            # Create a direct connection to any LSL stream
            # Use the code pattern from pylsl.examples.ReceiveData
            print("Resolving any stream...")
            from pylsl import resolve_streams
            streams = resolve_streams(wait_time=5.0)
            
            if not streams:
                print("No LSL streams found.")
                return False
                
            print(f"Found {len(streams)} streams:")
            for i, stream in enumerate(streams):
                try:
                    name = stream.name()
                    stream_type = stream.type()
                    channel_count = stream.channel_count()
                    print(f"  [{i}] Name: '{name}', Type: '{stream_type}', Channels: {channel_count}")
                except Exception as e:
                    print(f"  [{i}] Error getting stream info: {e}")
            
            # Use the first stream by default
            self.inlet = StreamInlet(streams[0])
            try:
                self.stream_type = streams[0].type()
                print(f"Connected to '{streams[0].name()}' stream of type '{self.stream_type}'")
            except:
                self.stream_type = "UNKNOWN"
                print(f"Connected to stream (type unknown)")
            
            # Test the connection
            print("Testing LSL stream connection...")
            sample, timestamp = self.inlet.pull_sample(timeout=5.0)
            if sample:
                print(f"Successfully received data: {sample}")
                
                # Determine if this is joystick data (pairs of values)
                if len(sample) == 2:
                    print("Detected joystick-like data format. Using as EMG joystick.")
                    self.stream_type = "EMGJoystick"
                else:
                    print(f"Detected {len(sample)} channel data. Using first channel for control.")
                    self.stream_type = "EMG"
                return True
            else:
                print("No data received within timeout period.")
                return False
                
        except Exception as e:
            print(f"Error connecting to LSL stream: {e}")
            return False
            
    def process_joystick(self, joystick_data):
        """Process joystick data and return command value."""
        # Add to buffer
        self.emg_buffer = np.roll(self.emg_buffer, -1, axis=0)
        self.emg_buffer[-1] = joystick_data
        
        # Average for smoothing
        avg_joystick = np.mean(self.emg_buffer, axis=0)
        
        # FIXED: Use x-axis instead of y-axis for control
        # Your EMG data comes in the format [-0.42, 0.0] where the first element
        # contains the actual signal
        x_value = avg_joystick[0]
        
        # Since your EMG signal is negative when you flex,
        # we need to check for negative values to trigger backward movement
        if x_value < -0.2:  # Backward threshold (negative values)
            # Use the absolute value for intensity scaling
            return "backward", min(abs(x_value), 1.0)
        elif x_value > 0.2:  # Forward threshold (if you get positive values)
            return "forward", min(abs(x_value), 1.0)
        else:
            return "hover", 0.0

            
    def process_raw_emg(self, emg_data):
        """Process raw EMG data and return command value."""
        # For multi-channel data, use the first channel
        if isinstance(emg_data, (list, tuple)) and len(emg_data) > 0:
            value = emg_data[0]
        else:
            value = emg_data
            
        # Add to buffer (reshape to store just one value)
        self.emg_buffer = np.roll(self.emg_buffer, -1, axis=0)
        self.emg_buffer[-1] = [0, value]  # Store in y position
        
        # Average for smoothing    
        avg_value = np.mean(self.emg_buffer[:, 1])
        
        # Normalize to approximate joystick range
        normalized = avg_value / 500.0  # Adjust divisor based on signal range
        
        # Apply thresholds
        if normalized > 0.2:
            return "forward", min(normalized, 1.0)
        elif normalized < -0.2:
            return "backward", min(abs(normalized), 1.0)
        else:
            return "hover", 0.0
    
    def emg_control_loop(self):
        """Main loop for processing EMG and controlling the drone."""
        if not self.inlet and self.stream_type != "SIMULATION":
            print("No LSL inlet available. EMG control disabled.")
            return
            
        print(f"Starting EMG control loop... (Stream type: {self.stream_type})")
        
        # For simulation mode, we need to generate random data
        if self.stream_type == "SIMULATION":
            print("Running in SIMULATION mode with generated EMG data")
            
            # Create a sinusoidal pattern for smooth movement
            start_time = time.time()
            
            while self.running:
                # Generate sinusoidal motion with some noise
                elapsed = time.time() - start_time
                y_value = np.sin(elapsed * 0.5) * 0.7  # Sine wave with period of ~12 seconds
                x_value = np.random.normal(0, 0.1)  # Add some noise on X axis
                
                # Create simulated sample
                sample = [x_value, y_value]
                
                # Print the data in debug mode
                if self.debug_mode:
                    print(f"Simulated data: {sample}")
                
                # Process joystick data
                command, intensity = self.process_joystick(sample)
                speed_scaled = int(self.speed * intensity)
                
                # Only apply control when the drone is flying
                if self.is_flying:
                    if command == "forward":
                        self.drone.send_rc_control(0, speed_scaled, 0, 0)  # forward
                        print(f"EMG Command: Forward (speed: {speed_scaled})")
                    elif command == "backward":
                        self.drone.send_rc_control(0, -speed_scaled, 0, 0)  # backward
                        print(f"EMG Command: Backward (speed: {speed_scaled})")
                    else:
                        self.drone.send_rc_control(0, 0, 0, 0)  # hover
                
                time.sleep(0.2)  # Update every 200ms in simulation mode
            return
            
        # Normal LSL processing
        print("Receiving data from LSL stream... (watching for signals)")
        
        try:
            while self.running:
                # Get data from LSL stream
                sample, timestamp = self.inlet.pull_sample(timeout=0.1)
                if not sample:
                    continue
                
                # Print the received data in debug mode
                if self.debug_mode:
                    print(f"Received data: {sample}")
                
                # Process based on stream type
                if self.stream_type == "EMGJoystick" or len(sample) == 2:
                    command, intensity = self.process_joystick(sample)
                else:
                    command, intensity = self.process_raw_emg(sample)
                
                speed_scaled = int(self.speed * intensity)
                
                # Only apply EMG control when the drone is flying
                if self.is_flying:
                    if command == "forward":
                        self.drone.send_rc_control(0, speed_scaled, 0, 0)  # forward
                        print(f"EMG Command: Forward (speed: {speed_scaled})")
                    elif command == "backward":
                        self.drone.send_rc_control(0, -speed_scaled, 0, 0)  # backward
                        print(f"EMG Command: Backward (speed: {speed_scaled})")
                    else:
                        self.drone.send_rc_control(0, 0, 0, 0)  # hover
                
                time.sleep(0.01)  # Small delay to prevent overwhelming the CPU
        except KeyboardInterrupt:
            print("EMG control loop interrupted")
            self.running = False
        except Exception as e:
            print(f"Error in EMG control loop: {e}")
            self.running = False
    
    def keyboard_control(self):
        """Handle keyboard inputs using pygame (no root required)."""
        # Initialize pygame for keyboard input
        pygame.init()
        screen = pygame.display.set_mode((640, 240))
        pygame.display.set_caption('Tello EMG Control')
        font = pygame.font.Font(None, 36)
        
        # Draw instructions
        def draw_instructions():
            screen.fill((0, 0, 0))
            instructions = [
                "Tello Drone EMG Control",
                "",
                "t - Takeoff",
                "l - Land",
                "r - Hold for clockwise rotation",
                "R - Hold for counter-clockwise rotation",
                "q - Quit program",
                "",
                f"Flying: {'Yes' if self.is_flying else 'No'}"
            ]
            for i, line in enumerate(instructions):
                text = font.render(line, True, (255, 255, 255))
                screen.blit(text, (20, 20 + i * 24))
            pygame.display.flip()
        
        draw_instructions()
        
        # Track rotation state
        is_rotating_clockwise = False
        is_rotating_counterclockwise = False
        
        while self.running:
            # Process pygame events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    print("Window closed. Quitting program...")
                    if self.is_flying:
                        self.drone.land()
                    self.running = False
                    break
            
            # Get pressed keys
            keys = pygame.key.get_pressed()
            
            # Handle takeoff (t key)
            if keys[pygame.K_t] and not self.is_flying:
                print("Taking off...")
                self.drone.takeoff()
                self.is_flying = True
                draw_instructions()  # Update display
                time.sleep(1)  # Prevent multiple keypresses
            
            # Handle landing (l key)
            elif keys[pygame.K_l] and self.is_flying:
                print("Landing...")
                self.drone.land()
                self.is_flying = False
                draw_instructions()  # Update display
                time.sleep(1)  # Prevent multiple keypresses
            
            # Handle clockwise rotation (r key - continuous while pressed)
            if keys[pygame.K_r] and self.is_flying:
                if not is_rotating_clockwise:
                    print("Rotating clockwise...")
                    is_rotating_clockwise = True
                self.drone.send_rc_control(0, 0, 0, self.speed)  # yaw right
            elif is_rotating_clockwise:
                self.drone.send_rc_control(0, 0, 0, 0)  # stop rotation
                is_rotating_clockwise = False
            
            # Handle counter-clockwise rotation (R key / Shift+r - continuous while pressed)
            if (keys[pygame.K_r] and keys[pygame.K_LSHIFT]) and self.is_flying:
                if not is_rotating_counterclockwise:
                    print("Rotating counter-clockwise...")
                    is_rotating_counterclockwise = True
                self.drone.send_rc_control(0, 0, 0, -self.speed)  # yaw left
            elif is_rotating_counterclockwise:
                self.drone.send_rc_control(0, 0, 0, 0)  # stop rotation
                is_rotating_counterclockwise = False
            
            # Handle quit (q key)
            if keys[pygame.K_q]:
                print("Quitting program...")
                if self.is_flying:
                    self.drone.land()
                self.running = False
                break
            
            # Small delay to prevent CPU overuse
            pygame.time.delay(50)  # 50ms delay (20 fps)
        
        # Clean up pygame
        pygame.quit()
    
    def run(self):
        """Run the main program."""
        # Connect to drone
        try:
            self.connect_to_drone()
        except Exception as e:
            print(f"Error connecting to drone: {e}")
            print("Exiting program.")
            return
        
        # Connect to LSL
        if not self.connect_to_lsl_direct():
            print("Failed to connect to LSL stream.")
            print("Would you like to:")
            print("1. Continue in simulation mode (using random data)")
            print("2. Exit program")
            
            try:
                choice = input("Enter choice (1-2): ")
                if choice != '1':
                    print("Exiting program.")
                    return
                    
                # Setup simulation mode
                self.stream_type = "SIMULATION"
                print("Continuing in simulation mode with random EMG data")
            except:
                print("Invalid input. Exiting.")
                return
        
        print("\n=== Tello EMG Control Ready ===")
        print(f"Using stream type: {self.stream_type}")
        print("Starting pygame window for keyboard control...")
        print("  't' - Takeoff")
        print("  'l' - Land")
        print("  'r' - Hold to rotate clockwise")
        print("  'Shift+r' - Hold to rotate counter-clockwise")
        print("  'q' - Quit program")
        print("===============================\n")
        
        # Start EMG control thread
        emg_thread = Thread(target=self.emg_control_loop)
        emg_thread.daemon = True
        emg_thread.start()
        
        # Start keyboard control (on main thread)
        try:
            self.keyboard_control()
        except KeyboardInterrupt:
            print("\nProgram interrupted by user.")
        except Exception as e:
            print(f"\nError in keyboard control: {e}")
        finally:
            # Clean up
            print("Shutting down...")
            self.running = False
            if self.is_flying:
                self.drone.land()
            if self.drone:
                self.drone.end()
            
            # Clean up pygame if it was initialized
            if pygame.get_init():
                pygame.quit()
                
            print("Program terminated.")
            
            # Give the EMG thread time to clean up
            time.sleep(1)

if __name__ == "__main__":
    controller = TelloEMGControl()
    controller.run()