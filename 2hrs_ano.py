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
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found! Run sim.py first.")
        return None
    
    try:
        df = pd.read_csv(csv_file)
    except pd.errors.EmptyDataError:
        print("Error: CSV is empty.")
        return None

    if df.empty:
        print("Error: CSV file is empty!")
        return None
    
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    last_timestamp = df["timestamp"].max()
    
    print(f"\nLast entry in CSV: {last_timestamp}")
    
    anomaly_start = last_timestamp + timedelta(minutes=30)
    anomaly_start = anomaly_start.replace(minute=0, second=0, microsecond=0)
    anomaly_end = anomaly_start + timedelta(hours=duration_hours)
    
    print(f"Anomaly Start: {anomaly_start}")
    print(f"Anomaly End:   {anomaly_end}")
    
    return anomaly_start, anomaly_end


def append_anomaly_real_time(csv_file, anomaly_start, anomaly_end):
    try:
        df = pd.read_csv(csv_file)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        last_timestamp = df["timestamp"].max()
    except:
        last_timestamp = datetime.now()
    
    current_time = last_timestamp + timedelta(minutes=STEP_MINUTES)
    
    DEVICES = {
        "bedroom_light": 12, "bedroom_fan": 60, "kitchen_light": 15,
        "kettle": 1200, "stove": 1500, "bathroom_light": 10, "tv": 100
    }
    
    ROUTINE = {
        "morning": (6, 9), "afternoon": (12, 14),
        "evening": (18, 21), "night": (22, 5)
    }
    
    def is_time_between(hour, start, end):
        if start <= end:
            return start <= hour < end
        return hour >= start or hour < end
    
  def generate_activity(hour, is_anomaly=False):
    if is_anomaly:
        # Mostly no activity, but occasional abnormal spikes
        if random.random() < 0.15:  # 15% chance of abnormal burst
            return random.sample(
                ["bedroom_light", "tv", "kettle", "stove", "bathroom_light"],
                random.randint(2, 4)
            )
        return []  # no activity most of the time
    
    def append_to_csv(events, filename):
        if not events: return
        df_new = pd.DataFrame(events)
        try:
            df_new.to_csv(filename, mode='a', header=False, index=False)
        except: pass
    
    print(f"\n--- STARTING INJECTION ---")
    
    try:
        iteration = 0
        end_time = anomaly_end + timedelta(hours=2)
        
        while current_time <= end_time:
            hour = current_time.hour
            is_anomaly = (current_time >= anomaly_start and current_time < anomaly_end)
            
            active_devices = generate_activity(hour, is_anomaly)
            
            events = []
            if active_devices:
                for device in active_devices:
                    events.append({
                        "timestamp": current_time, "device": device,
                        "power": DEVICES[device], "state": "ON"
                    })
            else:
                # Add empty entry to keep time moving
                events.append({
                    "timestamp": current_time, "device": "", 
                    "power": 0, "state": "OFF"
                })
            
            append_to_csv(events, csv_file)
            
            status = "🔴 ANOMALY" if is_anomaly else "🟢 NORMAL"
            device_count = len([e for e in events if e['device']])
            
            print(f"[Iter {iteration:04d}] {status} | {current_time.strftime('%H:%M:%S')} | {device_count} devices active")
            
            current_time += timedelta(minutes=STEP_MINUTES)
            iteration += 1
            time.sleep(REAL_TIME_INTERVAL)
            
    except KeyboardInterrupt:
        print("Stopped.")

if __name__ == "__main__":
    result = inject_future_anomaly(CSV_FILE, ANOMALY_DURATION_HOURS)
    if result:
        append_anomaly_real_time(CSV_FILE, result[0], result[1])
