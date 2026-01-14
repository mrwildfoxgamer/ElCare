import pandas as pd
import joblib
import time
import os
from datetime import datetime
import json

# ============================
# CONFIG
# ============================
DATA_FILE = "test_data.csv"
MODEL_FILE = "elderly_behavior_model.pkl"

INACTIVITY_THRESHOLD_HOURS = 6
CHECK_INTERVAL = 1

ALERT_LOG = "alerts_log.json"
WARNING_LOG = "warnings_log.json"

# ============================
# LOAD MODEL
# ============================
model = joblib.load(MODEL_FILE)
print("✓ Model loaded")

last_processed = 0
alerts_seen = set()
warnings_seen = set()

# ============================
# PROCESS DATA
# ============================
def process(df):
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["hour"] = df["timestamp"].dt.floor("h")

    groups = df.groupby("hour")
    full_range = pd.date_range(df["hour"].min(), df["hour"].max(), freq="h")

    hourly = pd.DataFrame(index=full_range)
    hourly.index.name = "hour"

    hourly["total_power"] = groups["power"].sum()
    hourly["active_devices"] = groups["device"].nunique()
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

    hourly["ml_anomaly"] = model.predict(X)
    hourly["warning"] = (
        (hourly["ml_anomaly"] == -1) ^
        (hourly["inactivity_streak"] >= INACTIVITY_THRESHOLD_HOURS)
    )

    hourly["alert"] = (
        (hourly["ml_anomaly"] == -1) &
        (hourly["inactivity_streak"] >= INACTIVITY_THRESHOLD_HOURS)
    )

    return hourly

# ============================
# LOGGING
# ============================
def log_event(file, data):
    if os.path.exists(file):
        with open(file, "r") as f:
            log = json.load(f)
    else:
        log = []
    log.append(data)
    with open(file, "w") as f:
        json.dump(log, f, indent=2)

# ============================
# MAIN LOOP
# ============================
print("\n🏥 Elderly Monitoring System Started\n")

while True:
    if not os.path.exists(DATA_FILE):
        time.sleep(CHECK_INTERVAL)
        continue

    df = pd.read_csv(DATA_FILE)
    if len(df) <= last_processed:
        time.sleep(CHECK_INTERVAL)
        continue

    hourly = infer(process(df))
    latest = hourly.iloc[-1]
    hour_key = latest["hour"].isoformat()

    if latest["alert"] and hour_key not in alerts_seen:
        alerts_seen.add(hour_key)
        print("\n🚨 EMERGENCY ALERT 🚨")
        print("Hour:", hour_key)
        print("Inactive:", latest["inactivity_streak"], "hours")
        log_event(ALERT_LOG, latest.to_dict())

    elif latest["warning"] and hour_key not in warnings_seen:
        warnings_seen.add(hour_key)
        print("\n⚠️ WARNING")
        print("Hour:", hour_key)
        log_event(WARNING_LOG, latest.to_dict())

    else:
        print("🟢 NORMAL |",
              datetime.now().strftime("%H:%M:%S"),
              "| Devices:", int(latest["active_devices"]))

    last_processed = len(df)
    time.sleep(CHECK_INTERVAL)

