import pandas as pd
import joblib
from sklearn.ensemble import IsolationForest

# ============================
# CONFIG
# ============================
DATA_FILE = "simulated_house_data.csv"
MODEL_FILE = "elderly_behavior_model.pkl"
ANOMALY_CONTAMINATION = 0.05
INACTIVITY_THRESHOLD_HOURS = 6

# ============================
# LOAD DATA
# ============================
df = pd.read_csv(DATA_FILE)
df["timestamp"] = pd.to_datetime(df["timestamp"])

# ============================
# AGGREGATE TO HOURLY DATA
# ============================
df["hour"] = df["timestamp"].dt.floor("H")

hourly = df.groupby("hour").agg(
    total_power=("power", "sum"),
    active_devices=("device", "nunique")
).reset_index()

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
# TRAIN ON NORMAL DATA ONLY
# (exclude last 24 hours)
# ============================
train_data = hourly.iloc[:-24]
X_train = train_data[FEATURES]

model = IsolationForest(
    n_estimators=200,
    contamination=ANOMALY_CONTAMINATION,
    random_state=42
)

model.fit(X_train)

# ============================
# SAVE MODEL
# ============================
joblib.dump(model, MODEL_FILE)

# ============================
# PREDICT ANOMALIES
# ============================
X_all = hourly[FEATURES]

hourly["anomaly_score"] = model.decision_function(X_all)
hourly["anomaly"] = model.predict(X_all)

# ============================
# ALERT LOGIC
# ============================
hourly["alert"] = (
    (hourly["anomaly"] == -1) &
    (hourly["inactivity_streak"] >= INACTIVITY_THRESHOLD_HOURS)
)

# ============================
# OUTPUT
# ============================
alerts = hourly[hourly["alert"]]

print("Model trained and saved.")
print(f"Total alerts detected: {len(alerts)}")

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
    print("\nNo alerts detected.")

# Optional: save results
hourly.to_csv("ml_results.csv", index=False)

