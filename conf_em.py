import pandas as pd
from datetime import datetime, timedelta
import os

CSV_FILE = "test_data.csv"
STEP_MINUTES = 10

def force_emergency():
    """
    Appends future timestamps with ZERO activity to trigger emergency
    """
    if not os.path.exists(CSV_FILE):
        print(f"Creating {CSV_FILE} with emergency data...")
        # Create minimal starter data
        now = datetime.now().replace(second=0, microsecond=0)
        df = pd.DataFrame([{
            "timestamp": now,
            "device": "bedroom_light",
            "power": 12,
            "state": "ON"
        }])
        df.to_csv(CSV_FILE, index=False)
        last_timestamp = now
    else:
        df = pd.read_csv(CSV_FILE)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        last_timestamp = df["timestamp"].max()
    
    # Jump 4 hours into future with timestamp entries but NO device activity
    current_time = last_timestamp + timedelta(minutes=STEP_MINUTES)
    emergency_entries = []
    
    # Add 24 entries (4 hours) with timestamps but empty device data
    # This creates the illusion of monitoring continuing but zero activity
    for i in range(42):
        # Empty row with just timestamp = no activity detected
        emergency_entries.append({
            "timestamp": current_time,
            "device": "",
            "power": 0,
            "state": ""
        })
        current_time += timedelta(minutes=STEP_MINUTES)
    
    # Append to CSV
    df_emergency = pd.DataFrame(emergency_entries)
    df_emergency.to_csv(CSV_FILE, mode='a', header=False, index=False)
    
    print(f"✅ Emergency data appended")
    print(f"Period: {emergency_entries[0]['timestamp']} to {emergency_entries[-1]['timestamp']}")
    print(f"Added: {len(emergency_entries)} empty entries (4 hours)")
    print(f"\nRun monitor.py - it will detect 4-hour inactivity as EMERGENCY")

if __name__ == "__main__":
    force_emergency()
