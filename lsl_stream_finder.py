"""
LSL Stream Finder
----------------
This script detects and lists all available LSL streams.
Use this to troubleshoot LSL connection issues.
"""

import time
print("Importing pylsl...")

try:
    from pylsl import StreamInlet, resolve_stream
    print("Using standard pylsl import pattern")
    resolve_function = resolve_stream
except ImportError:
    try:
        from pylsl import StreamInlet
        from pylsl.pylsl import resolve_byprop as resolve_stream
        print("Using older pylsl import pattern")
        resolve_function = resolve_stream
    except ImportError:
        try:
            from pylsl import StreamInlet
            from pylsl import resolve_byprop as resolve_stream
            print("Using alternative pylsl import pattern")
            resolve_function = resolve_stream
        except ImportError:
            print("Failed to import pylsl. Please install with: pip install pylsl")
            exit(1)

print("\nLooking for ANY available LSL streams (10 second timeout)...")
print("(Please make sure OpenBCI GUI is streaming data via LSL)")

try:
    # Try to find all streams
    print("\n--- Method 1: resolve_streams() ---")
    try:
        from pylsl import resolve_streams
        print("Calling resolve_streams()...")
        streams = resolve_streams(wait_time =10.0)
        if streams:
            print(f"Found {len(streams)} streams:")
            for i, stream in enumerate(streams):
                try:
                    name = stream.name()
                    stream_type = stream.type()
                    source_id = stream.source_id()
                    channel_count = stream.channel_count()
                    print(f"  [{i}] Name: '{name}', Type: '{stream_type}', ID: '{source_id}', Channels: {channel_count}")
                except Exception as e:
                    print(f"  [{i}] Error getting stream info: {e}")
        else:
            print("No streams found with resolve_streams().")
    except Exception as e:
        print(f"Method 1 failed: {e}")

    # Try to find EMGJoystick streams specifically
    print("\n--- Method 2: resolve_stream('type', 'EMGJoystick') ---")
    try:
        streams = resolve_function('type', 'EMGJoystick', timeout=5.0)
        if streams:
            print(f"Found {len(streams)} EMGJoystick streams:")
            for i, stream in enumerate(streams):
                try:
                    print(f"  [{i}] Name: '{stream.name()}', Type: '{stream.type()}'")
                except Exception as e:
                    print(f"  [{i}] Error getting stream info: {e}")
        else:
            print("No EMGJoystick streams found.")
    except Exception as e:
        print(f"Method 2 failed: {e}")

    # Try to find all EMG streams
    print("\n--- Method 3: resolve_stream('type', 'EMG') ---")
    try:
        streams = resolve_function('type', 'EMG', timeout=5.0)
        if streams:
            print(f"Found {len(streams)} EMG streams:")
            for i, stream in enumerate(streams):
                try:
                    print(f"  [{i}] Name: '{stream.name()}', Type: '{stream.type()}'")
                except Exception as e:
                    print(f"  [{i}] Error getting stream info: {e}")
        else:
            print("No EMG streams found.")
    except Exception as e:
        print(f"Method 3 failed: {e}")

    # Try to find streams by name containing "obci"
    print("\n--- Method 4: resolve_stream('name', '*obci*') ---")
    try:
        from pylsl import resolve_byprop
        streams = resolve_byprop('name', 'obci', timeout=5.0)
        if streams:
            print(f"Found {len(streams)} streams with 'obci' in name:")
            for i, stream in enumerate(streams):
                try:
                    print(f"  [{i}] Name: '{stream.name()}', Type: '{stream.type()}'")
                except Exception as e:
                    print(f"  [{i}] Error getting stream info: {e}")
        else:
            print("No streams found with 'obci' in name.")
    except Exception as e:
        print(f"Method 4 failed: {e}")

except Exception as e:
    print(f"Error during stream detection: {e}")

print("\nStream detection finished. If no streams were found, please check:")
print("1. Is OpenBCI GUI running and streaming data via LSL?")
print("2. Are both applications running on the same machine?")
print("3. Is there any firewall blocking UDP communication?")