import pandas as pd
import joblib
from sklearn.ensemble import IsolationForest

# ============================
# CONFIG
# ============================
DATA_FILE = "train_data.csv"
MODEL_FILE = "elderly_behavior_model.pkl"

ANOMALY_CONTAMINATION = 0.005   # lower = fewer false alerts
INACTIVITY_THRESHOLD_HOURS = 4

# ============================
# LOAD DATA
# ============================
df = pd.read_csv(DATA_FILE)
df["timestamp"] = pd.to_datetime(df["timestamp"])

# ============================
# AGGREGATE TO HOURLY
# ============================
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
hourly["active_devices"] = groups["device"].nunique()
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

hourly["power_per_device"] = (
    hourly["total_power"] / (hourly["active_devices"] + 1)
)

hourly["rolling_power_6h"] = hourly["total_power"].rolling(
    window=6, min_periods=1
).mean()

FEATURES = [
    "total_power",
    "active_devices",
    "hour_of_day",
    "inactivity_streak",
    "power_per_device",
    "rolling_power_6h"
]

X_train = hourly[FEATURES]

# ============================
# TRAIN MODEL (NORMAL DATA ONLY)
# ============================
model = IsolationForest(
    n_estimators=300,
    contamination=ANOMALY_CONTAMINATION,
    random_state=42
)

model.fit(X_train)

# ============================
# SAVE MODEL
# ============================
joblib.dump(model, MODEL_FILE)
print("✅ Model trained and saved:", MODEL_FILE)

