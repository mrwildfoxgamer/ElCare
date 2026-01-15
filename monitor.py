        # Show reaimport pandas as pd
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

INACTIVITY_THRESHOLD_HOURS = 5   # HARD emergency rule
CHECK_INTERVAL = 1

ALERT_LOG = "alerts_log.json"
WARNING_LOG = "warnings_log.json"

# ============================
# LOAD MODEL
# ============================
if not os.path.exists(MODEL_FILE):
    print(f"❌ Model not found: {MODEL_FILE}")
    print("Run train.py first")
    exit(1)

model = joblib.load(MODEL_FILE)
print("✅ ML model loaded")

last_processed_len = 0
alerts_seen = set()
warnings_seen = set()

# ============================
# DATA PROCESSING
# ============================
def process(df):
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # IMPORTANT: keep empty rows for time progression
    df["hour"] = df["timestamp"].dt.floor("h")
    groups = df.groupby("hour")

    full_range = pd.date_range(
        start=df["hour"].min(),
        end=df["hour"].max(),
        freq="h"
    )

    hourly = pd.DataFrame(index=full_range)
    hourly.index.name = "hour"

    hourly["total_power"] = groups["power"].sum()

    # Count only real devices
    hourly["active_devices"] = groups.apply(
        lambda x: x[x["device"].notna() & (x["device"] != "")]["device"].nunique()
    )

    hourly = hourly.fillna(0).reset_index()
    hourly["hour_of_day"] = hourly["hour"].dt.hour

    # ============================
    # TRUE inactivity streak
    # ============================
    hourly["inactive"] = (hourly["active_devices"] == 0).astype(int)

    streak = 0
    streaks = []
    for inactive in hourly["inactive"]:
        streak = streak + 1 if inactive else 0
        streaks.append(streak)

    hourly["inactivity_streak"] = streaks

    # ============================
    # FEATURES
    # ============================
    hourly["power_per_device"] = (
        hourly["total_power"] / (hourly["active_devices"] + 1)
    )

    hourly["rolling_power_6h"] = hourly["total_power"].rolling(
        window=6, min_periods=1
    ).mean()

    return hourly


# ============================
# ML INFERENCE (WARNINGS ONLY)
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
    hourly["ml_score"] = model.decision_function(X)
    hourly["ml_anomaly"] = model.predict(X)

    # ML is ONLY for warnings
    hourly["warning"] = (
        (hourly["ml_anomaly"] == -1) &
        (hourly["inactivity_streak"] < INACTIVITY_THRESHOLD_HOURS)
    )

    # RULE-BASED EMERGENCY (NO ML)
    hourly["alert"] = (
        hourly["inactivity_streak"] >= INACTIVITY_THRESHOLD_HOURS
    )

    return hourly


# ============================
# LOGGING
# ============================
def log_event(file, data):
    data = data.copy()
    data["timestamp"] = str(data["hour"])

    try:
        if os.path.exists(file):
            with open(file, "r") as f:
                log = json.load(f)
        else:
            log = []

        log.append(data)

        with open(file, "w") as f:
            json.dump(log, f, indent=2)
    except Exception as e:
        print("Logging error:", e)


# ============================
# MAIN LOOP
# ============================
print("\n🏥 Elderly Monitoring System ACTIVE")
print(f"⚠️  Warning: ML-based pattern deviation")
print(f"🚨 Emergency: {INACTIVITY_THRESHOLD_HOURS}h continuous inactivity\n")

while True:
    if not os.path.exists(DATA_FILE):
        time.sleep(CHECK_INTERVAL)
        continue

    try:
        df = pd.read_csv(DATA_FILE)
    except:
        time.sleep(CHECK_INTERVAL)
        continue

    if df.empty or len(df) <= last_processed_len:
        time.sleep(CHECK_INTERVAL)
        continue

    hourly = infer(process(df))
    latest = hourly.iloc[-1]
    hour_key = str(latest["hour"])

    # ============================
    # EMERGENCY ALERT
    # ============================
    if latest["alert"] and hour_key not in alerts_seen:
        alerts_seen.add(hour_key)

        print("\n" + "=" * 60)
        print("🚨🚨🚨 CRITICAL EMERGENCY 🚨🚨🚨")
        print("=" * 60)
        print(f"Time: {hour_key}")
        print(f"Inactivity: {int(latest['inactivity_streak'])} hours")
        print(f"Active Devices: {int(latest['active_devices'])}")
        print(f"Total Power: {latest['total_power']:.2f} W")
        print("=" * 60 + "\n")

        log_event(ALERT_LOG, latest.to_dict())

    # ============================
    # WARNING
    # ============================
    elif latest["warning"] and hour_key not in warnings_seen:
        warnings_seen.add(hour_key)

        print("\n⚠️ WARNING: Unusual behavior detected")
        print(f"Time: {hour_key}")
        print(f"ML Score: {latest['ml_score']:.4f}")
        print(f"Inactivity: {int(latest['inactivity_streak'])}h\n")

        log_event(WARNING_LOG, latest.to_dict())

    # ============================
    # LIVE STATUS
    # ============================
    else:
        streak = int(latest["inactivity_streak"])
        icon = "🟢" if streak < 2 else "🟡" if streak < 4 else "🔴"

        print(
            f"{icon} {datetime.now().strftime('%H:%M:%S')} | "
            f"Devices: {int(latest['active_devices'])} | "
            f"Inactive: {streak}h | "
            f"ML Score: {latest['ml_score']:.2f}",
            end="\r"
        )

    last_processed_len = len(df)
    time.sleep(CHECK_INTERVAL)
l-time status
        streak_hours = int(latest['inactivity_streak'])
        status_icon = "🟢"
        if streak_hours >= 4:
            status_icon = "🔴"
        elif streak_hours >= 2:
            status_icon = "🟡"
            
        print(f"{status_icon} {datetime.now().strftime('%H:%M:%S')} | Devices: {int(latest['active_devices'])} | Inactive: {streak_hours}h | Score: {latest['anomaly_score']:.2f}", end="\r")

    last_processed_len = len(df)
    time.sleep(CHECK_INTERVAL)
