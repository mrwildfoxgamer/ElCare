import pandas as pd
import joblib

# ============================
# CONFIG
# ============================
DATA_FILE = "test_data.csv"   # new dataset
MODEL_FILE = "elderly_behavior_model.pkl"
INACTIVITY_THRESHOLD_HOURS = 6

# ============================
# LOAD MODEL
# ============================
model = joblib.load(MODEL_FILE)

# ============================
# LOAD NEW DATA
# ============================
df = pd.read_csv(DATA_FILE)
df["timestamp"] = pd.to_datetime(df["timestamp"])

# ============================
# AGGREGATE TO HOURLY
# 1. Group existing data
df["hour"] = df["timestamp"].dt.floor("h") # Use 'h' (lowercase) to avoid warning

hourly_groups = df.groupby("hour")

# 2. Create a full timeline from start to end (fills the missing "Emergency" gaps)
full_range = pd.date_range(
    start=df["hour"].min(), 
    end=df["hour"].max(), 
    freq="h"
)

# 3. Reindex to include the empty hours and fill them with 0
hourly = pd.DataFrame(index=full_range)
hourly.index.name = "hour"

hourly["total_power"] = hourly_groups["power"].sum()
hourly["active_devices"] = hourly_groups["device"].nunique()

# Fill NaNs (created by the reindex) with 0
hourly = hourly.fillna(0).reset_index()
# ============================
# FEATURE ENGINEERING
# ============================
hourly["hour_of_day"] = hourly["hour"].dt.hour
hourly["inactive"] = (hourly["active_devices"] == 0).astype(int)

hourly["inactivity_streak"] = hourly["inactive"].rolling(
    window=INACTIVITY_THRESHOLD_HOURS,
    min_periods=1
).sum()

FEATURES = [
    "total_power",
    "active_devices",
    "hour_of_day",
    "inactivity_streak"
]

# ============================
# RUN PREDICTION
# ============================
X = hourly[FEATURES]

hourly["anomaly_score"] = model.decision_function(X)
hourly["anomaly"] = model.predict(X)

# ============================
# ALERT LOGIC
# ============================
hourly["alert"] = (
    (hourly["anomaly"] == -1) &
    (hourly["inactivity_streak"] >= INACTIVITY_THRESHOLD_HOURS)
)

# ============================
# OUTPUT RESULTS
# ============================
alerts = hourly[hourly["alert"]]

print("Inference complete.")
print(f"Alerts detected: {len(alerts)}")

if not alerts.empty:
    print("\n🚨 ALERT HOURS:")
    print(alerts[[
        "hour",
        "total_power",
        "active_devices",
        "inactivity_streak",
        "anomaly_score"
    ]])
else:
    print("\nNo anomalies detected.")

# Save results
hourly.to_csv("inference_results.csv", index=False)

