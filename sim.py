import random
import pandas as pd
from datetime import datetime, timedelta
import time
import os

# ----------------------------
# HOUSE CONFIGURATION
# ----------------------------
DEVICES = {
    "bedroom_light": 12,
    "bedroom_fan": 60,
    "kitchen_light": 15,
    "kettle": 1200,
    "stove": 1500,
    "bathroom_light": 10,
    "tv": 100
}

ROUTINE = {
    "morning": (6, 9),
    "afternoon": (12, 14),
    "evening": (18, 21),
    "night": (22, 5)
}

# ----------------------------
# CONFIGURATION
# ----------------------------
CSV_FILE = "test_data.csv"  # File to append to
STEP_MINUTES = 10           # Simulated time step (10 minutes)
REAL_TIME_INTERVAL = 1      # Real-world seconds between entries
RUN_CONTINUOUSLY = True     # Set to False to generate only one entry

# ----------------------------
# HELPER FUNCTIONS
# ----------------------------
def is_time_between(hour, start, end):
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end


def generate_activity(hour, emergency=False):
    """Generate activity based on time of day (no anomalies)"""
    active_devices = []

    if emergency:
        return active_devices  # no activity at all

    if is_time_between(hour, *ROUTINE["morning"]):
        active_devices += ["bedroom_light", "kettle"]
        if random.random() > 0.3:
            active_devices.append("bedroom_fan")

    elif is_time_between(hour, *ROUTINE["afternoon"]):
        if random.random() > 0.5:
            active_devices += ["kitchen_light", "stove"]

    elif is_time_between(hour, *ROUTINE["evening"]):
        active_devices += ["tv", "bedroom_light"]

    elif is_time_between(hour, *ROUTINE["night"]):
        if random.random() > 0.85:
            active_devices.append("bathroom_light")

    return active_devices


def append_to_csv(events, filename):
    """Append new events to CSV file"""
    df_new = pd.DataFrame(events)
    
    # Check if file exists
    if os.path.exists(filename):
        # Append without header
        df_new.to_csv(filename, mode='a', header=False, index=False)
    else:
        # Create new file with header
        df_new.to_csv(filename, mode='w', header=True, index=False)


def generate_single_entry(simulated_time=None):
    """Generate a single 10-minute entry
    
    Args:
        simulated_time: Use this time instead of real time (for simulation)
    """
    if simulated_time is None:
        simulated_time = datetime.now()
    
    hour = simulated_time.hour
    
    # Generate activity for current hour (no emergency)
    active_devices = generate_activity(hour, emergency=False)
    
    events = []
    for device in active_devices:
        events.append({
            "timestamp": simulated_time,
            "device": device,
            "power": DEVICES[device],
            "state": "ON"
        })
    
    return events, simulated_time


# ----------------------------
# MAIN EXECUTION
# ----------------------------
if __name__ == "__main__":
    print(f"Starting real-time data generation...")
    print(f"Appending to: {CSV_FILE}")
    print(f"Simulated time step: {STEP_MINUTES} minutes")
    print(f"Real-world interval: {REAL_TIME_INTERVAL} second(s)")
    print(f"Time compression: {STEP_MINUTES * 60}x (10 min = 1 sec)")
    print(f"Continuous mode: {RUN_CONTINUOUSLY}")
    print("-" * 50)
    
    # Initialize simulated time
    # Check if file exists to continue from last timestamp
    if os.path.exists(CSV_FILE):
        try:
            df_existing = pd.read_csv(CSV_FILE)
            if not df_existing.empty:
                df_existing["timestamp"] = pd.to_datetime(df_existing["timestamp"])
                last_time = df_existing["timestamp"].max()
                simulated_time = last_time + timedelta(minutes=STEP_MINUTES)
                print(f"Resuming from last timestamp: {last_time}")
                print(f"Next entry will be: {simulated_time}")
            else:
                simulated_time = datetime.now()
        except:
            simulated_time = datetime.now()
    else:
        simulated_time = datetime.now()
        print(f"Starting new simulation at: {simulated_time}")
    
    print("-" * 50)
    
    if RUN_CONTINUOUSLY:
        # Run continuously, generating new data every 1 second (representing 10 minutes)
        try:
            iteration = 0
            while True:
                events, timestamp = generate_single_entry(simulated_time)
                
                if events:
                    append_to_csv(events, CSV_FILE)
                    print(f"[Iter {iteration:04d}] {timestamp.strftime('%Y-%m-%d %H:%M:%S')} | Added {len(events)} device events")
                else:
                    print(f"[Iter {iteration:04d}] {timestamp.strftime('%Y-%m-%d %H:%M:%S')} | No activity (normal)")
                
                # Advance simulated time by 10 minutes
                simulated_time += timedelta(minutes=STEP_MINUTES)
                iteration += 1
                
                # Wait for 1 second in real time
                time.sleep(REAL_TIME_INTERVAL)
                
        except KeyboardInterrupt:
            print("\n\nStopped by user.")
            print(f"Final simulated time: {simulated_time}")
            print("Data generation completed.")
    
    else:
        # Generate only one entry
        events, timestamp = generate_single_entry(simulated_time)
        
        if events:
            append_to_csv(events, CSV_FILE)
            print(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Added {len(events)} device events")
        else:
            print(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] No activity (normal for this time)")
        
        print("Single entry generated successfully.")
