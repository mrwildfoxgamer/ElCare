import pandas as pd
import joblib
import time
import os
from datetime import datetime
import json
import warnings

warnings.filterwarnings("ignore")

# ============================
# CONFIG
# ============================
DATA_FILE = "test_data.csv"
MODEL_FILE = "elderly_behavior_model.pkl"

INACTIVITY_THRESHOLD_HOURS = 5
CHECK_INTERVAL = 1

ALERT_LOG = "alerts_log.json"
WARNING_LOG = "warnings_log.json"

# ============================
# LOAD MODEL
# ============================
if not os.path.exists(MODEL_FILE):
    print(f"Error: {MODEL_FILE} not found. Run train.py first.")
    exit(1)

model = joblib.load(MODEL_FILE)
print("✓ Model loaded")

last_processed_len = 0
alerts_seen = set()
warnings_seen = set()

# ============================
# PROCESS DATA
# ============================
def process(df):
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    
    # CRITICAL FIX: Don't filter out empty devices - we need them to track time!
    # Empty device rows indicate "time passed with no activity"
    
    df["hour"] = df["timestamp"].dt.floor("h")

    # Group by hour - include ALL rows
    groups = df.groupby("hour")
    
    # Handle empty dataframe
    if df.empty:
        return pd.DataFrame(columns=["total_power", "active_devices", "hour_of_day", 
                                   "inactivity_streak", "power_per_device", "rolling_power_6h"])

    full_range = pd.date_range(df["hour"].min(), df["hour"].max(), freq="h")

    hourly = pd.DataFrame(index=full_range)
    hourly.index.name = "hour"

    # Count only non-empty devices for active_devices
    hourly["total_power"] = groups["power"].sum()
    hourly["active_devices"] = groups.apply(
        lambda x: x[x['device'].notna() & (x['device'] != "")]['device'].nunique()
    )
    
    hourly = hourly.fillna(0).reset_index()

    hourly["hour_of_day"] = hourly["hour"].dt.hour
    hourly["inactive"] = (hourly["active_devices"] == 0).astype(int)

    hourly["inactivity_streak"] = hourly["inactive"].rolling(
        window=INACTIVITY_THRESHOLD_HOURS,
        min_periods=1
    ).sum()

    hourly["power_per_device"] = (
        hourly["total_power"] / (hourly["active_devices"] + 1)
    )

    hourly["rolling_power_6h"] = hourly["total_power"].rolling(
        window=6, min_periods=1
    ).mean()

    return hourly

# ============================
# INFERENCE
# ============================
def infer(hourly):
    if hourly.empty:
        return hourly
        
    FEATURES = [
        "total_power",
        "active_devices",
        "hour_of_day",
        "inactivity_streak",
        "power_per_device",
        "rolling_power_6h"
    ]

    X = hourly[FEATURES]
    hourly["score"] = model.decision_function(X)
    hourly["smoothed_score"] = hourly["score"].rolling(
        window=3, min_periods=1
    ).mean()
    
    hourly["anomaly_score"] = hourly["smoothed_score"]

    hourly["ml_anomaly"] = model.predict(X)
    
    # CRITICAL FIX: Make warnings and alerts more sensitive
    # Warning: Either ML detects anomaly OR long inactivity
    hourly["warning"] = (
        (hourly["ml_anomaly"] == -1) |
        (hourly["inactivity_streak"] >= 3)  # Warning at 3 hours
    )

    # Alert: ML anomaly AND significant inactivity OR extreme inactivity alone
    hourly["alert"] = (
        ((hourly["ml_anomaly"] == -1) & (hourly["inactivity_streak"] >= INACTIVITY_THRESHOLD_HOURS)) |
        (hourly["inactivity_streak"] >= 7)  # Emergency if 7+ hours regardless
    )

    return hourly

# ============================
# LOGGING
# ============================
def log_event(file, data):
    if 'timestamp' in data:
        data['timestamp'] = str(data['timestamp'])
    if 'hour' in data:
        data['hour'] = str(data['hour'])
        
    try:
        if os.path.exists(file):
            with open(file, "r") as f:
                try:
                    log = json.load(f)
                except json.JSONDecodeError:
                    log = []
        else:
            log = []
        
        log.append(data)
        
        with open(file, "w") as f:
            json.dump(log, f, indent=2)
    except Exception as e:
        print(f"Error logging event: {e}")

# ============================
# MAIN LOOP
# ============================
print("\n🏥 Elderly Monitoring System Started\n")

while True:
    if not os.path.exists(DATA_FILE):
        time.sleep(CHECK_INTERVAL)
        continue

    try:
        df = pd.read_csv(DATA_FILE)
    except Exception as e:
        time.sleep(CHECK_INTERVAL)
        continue
        
    if df.empty or len(df) <= last_processed_len:
        time.sleep(CHECK_INTERVAL)
        continue

    # Process and Infer
    processed_df = process(df)
    if processed_df.empty:
        last_processed_len = len(df)
        time.sleep(CHECK_INTERVAL)
        continue
        
    hourly = infer(processed_df)
    latest = hourly.iloc[-1]
    
    hour_key = str(latest["hour"])

    # Output status
    if latest["alert"] and hour_key not in alerts_seen:
        alerts_seen.add(hour_key)
        print("\n🚨 EMERGENCY ALERT 🚨")
        print("Hour:", hour_key)
        print("Inactive Streak:", latest["inactivity_streak"], "hours")
        print("ML Anomaly Score:", latest["anomaly_score"])
        print("Active Devices:", int(latest["active_devices"]))
        log_event(ALERT_LOG, latest.to_dict())

    elif latest["warning"] and hour_key not in warnings_seen:
        warnings_seen.add(hour_key)
        print("\n⚠️ WARNING")
        print("Hour:", hour_key)
        print("Inactive Streak:", latest["inactivity_streak"], "hours")
        print("ML Anomaly Score:", latest["anomaly_score"])
        log_event(WARNING_LOG, latest.to_dict())

    else:
        print(f"🟢 NORMAL | {datetime.now().strftime('%H:%M:%S')} | Devices: {int(latest['active_devices'])} | Inactive: {int(latest['inactivity_streak'])}h", end="\r")

    last_processed_len = len(df)
    time.sleep(CHECK_INTERVAL)
