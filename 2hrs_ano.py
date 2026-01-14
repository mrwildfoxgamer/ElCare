import pandas as pd
import random
from datetime import datetime, timedelta
import os
import time

# ============================
# CONFIGURATION
# ============================
CSV_FILE = "test_data.csv"
ANOMALY_DURATION_HOURS = 7
STEP_MINUTES = 10  # Must match sim.py
REAL_TIME_INTERVAL = 1  # Seconds between entries (matches sim.py)

# ============================
# ANOMALY INJECTION (FUTURE)
# ============================
def inject_future_anomaly(csv_file, duration_hours=2):
    """
    Inject a future anomaly period AFTER the current data
    This will be detected by monitor.py in real-time
    
    Args:
        csv_file: Path to the CSV file
        duration_hours: Duration of the anomaly in hours (default: 2)
    """
    
    # Check if file exists
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found!")
        print("Please run sim.py first to generate data.")
        return
    
    # Load existing data
    print(f"Loading data from {csv_file}...")
    df = pd.read_csv(csv_file)
    
    if df.empty:
        print("Error: CSV file is empty!")
        return
    
    # Parse timestamps
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    
    # Get the last timestamp
    last_timestamp = df["timestamp"].max()
    
    print(f"\nLast entry in CSV: {last_timestamp}")
    
    # Calculate when the anomaly should start
    # Start the anomaly 30 minutes after the last entry
    anomaly_start = last_timestamp + timedelta(minutes=30)
    
    # Round to nearest hour for cleaner anomaly period
    anomaly_start = anomaly_start.replace(minute=0, second=0, microsecond=0)
    anomaly_end = anomaly_start + timedelta(hours=duration_hours)
    
    print(f"\n{'='*60}")
    print(f"PLANNING FUTURE ANOMALY PERIOD")
    print(f"{'='*60}")
    print(f"Anomaly Start: {anomaly_start}")
    print(f"Anomaly End:   {anomaly_end}")
    print(f"Duration: {duration_hours} hours")
    print(f"{'='*60}\n")
    
    # Calculate how many entries until anomaly starts
    time_until_anomaly = anomaly_start - last_timestamp
    entries_until_anomaly = int(time_until_anomaly.total_seconds() / (STEP_MINUTES * 60))
    
    # Calculate entries during anomaly (all will be empty)
    anomaly_entries = int((duration_hours * 60) / STEP_MINUTES)
    
    print(f"Entries until anomaly starts: {entries_until_anomaly}")
    print(f"Time until anomaly: {time_until_anomaly}")
    print(f"Empty entries during anomaly: {anomaly_entries}")
    print(f"Total time to complete: ~{entries_until_anomaly + anomaly_entries} seconds")
    
    return anomaly_start, anomaly_end


def append_anomaly_real_time(csv_file, anomaly_start, anomaly_end):
    """
    Append entries in real-time, including the anomaly period
    This simulates the continuation of sim.py but with an anomaly
    """
    
    # Load existing data to get last timestamp
    df = pd.read_csv(csv_file)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    last_timestamp = df["timestamp"].max()
    
    # Start from next entry after last timestamp
    current_time = last_timestamp + timedelta(minutes=STEP_MINUTES)
    
    # Import device configuration from sim.py logic
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
    
    def is_time_between(hour, start, end):
        if start <= end:
            return start <= hour < end
        return hour >= start or hour < end
    
    def generate_activity(hour, is_anomaly=False):
        """Generate activity based on time of day"""
        if is_anomaly:
            return []  # No activity during anomaly
        
        active_devices = []
        
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
        if not events:
            return
        
        df_new = pd.DataFrame(events)
        df_new.to_csv(filename, mode='a', header=False, index=False)
    
    print(f"\n{'='*60}")
    print("STARTING REAL-TIME ANOMALY INJECTION")
    print(f"{'='*60}")
    print(f"Starting from: {current_time}")
    print(f"Anomaly period: {anomaly_start} to {anomaly_end}")
    print("Press Ctrl+C to stop")
    print(f"{'='*60}\n")
    
    try:
        iteration = 0
        anomaly_started = False
        anomaly_ended = False
        
        # Continue until anomaly period is complete plus some normal data after
        end_time = anomaly_end + timedelta(hours=2)
        
        while current_time <= end_time:
            hour = current_time.hour
            
            # Check if we're in anomaly period
            is_anomaly = (current_time >= anomaly_start and current_time < anomaly_end)
            
            # Status tracking
            if is_anomaly and not anomaly_started:
                print(f"\n🚨 ANOMALY PERIOD STARTED at {current_time} 🚨\n")
                anomaly_started = True
            
            if not is_anomaly and anomaly_started and not anomaly_ended:
                print(f"\n✅ ANOMALY PERIOD ENDED at {current_time} ✅\n")
                anomaly_ended = True
            
            # Generate activity (empty during anomaly)
            active_devices = generate_activity(hour, is_anomaly)
            
            events = []
            for device in active_devices:
                events.append({
                    "timestamp": current_time,
                    "device": device,
                    "power": DEVICES[device],
                    "state": "ON"
                })
            
            # Append to CSV
            if events:
                append_to_csv(events, csv_file)
                status = "🟢 NORMAL" if not is_anomaly else "🔴 ANOMALY"
                print(f"[Iter {iteration:04d}] {status} | {current_time.strftime('%Y-%m-%d %H:%M:%S')} | {len(events)} devices active")
            else:
                status = "⚪ Inactive" if not is_anomaly else "🚨 EMERGENCY"
                print(f"[Iter {iteration:04d}] {status} | {current_time.strftime('%Y-%m-%d %H:%M:%S')} | No activity")
            
            # Advance time
            current_time += timedelta(minutes=STEP_MINUTES)
            iteration += 1
            
            # Wait real-time interval
            time.sleep(REAL_TIME_INTERVAL)
        
        print(f"\n{'='*60}")
        print("ANOMALY INJECTION COMPLETE")
        print(f"{'='*60}")
        print(f"Total entries added: {iteration}")
        print(f"Final timestamp: {current_time}")
        print(f"\n✓ The {anomaly_end - anomaly_start} anomaly period has been injected!")
        print("✓ Monitor.py should have detected the emergency!")
        print(f"{'='*60}\n")
        
    except KeyboardInterrupt:
        print(f"\n\nStopped by user at {current_time}")
        print(f"Entries added: {iteration}")


# ============================
# MAIN EXECUTION
# ============================
if __name__ == "__main__":
    print("\n🚨 REAL-TIME ANOMALY INJECTION TOOL 🚨\n")
    print("This script will append future data with an anomaly period")
    print("that monitor.py can detect in real-time.\n")
    print("IMPORTANT: Run monitor.py in another terminal BEFORE running this!")
    print("-" * 60)
    
    
    # Plan the anomaly
    result = inject_future_anomaly(CSV_FILE, ANOMALY_DURATION_HOURS)
    
    if result:
        anomaly_start, anomaly_end = result
        
        print("\n" + "="*60)
        print("READY TO INJECT ANOMALY")
        print("="*60)
        print("\nMake sure monitor.py is running in another terminal!")
        print("\nThis will:")
        print("1. Continue adding normal data")
        print("2. Inject a 2-hour period with NO activity")
        print("3. Resume normal data after the anomaly")
        print("\nmonitor.py should detect and alert during the anomaly period.")
        print("="*60)
        
        append_anomaly_real_time(CSV_FILE, anomaly_start, anomaly_end)
