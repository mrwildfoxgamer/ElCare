import pandas as pd
import joblib
from sklearn.ensemble import IsolationForest

# ============================
# CONFIG
# ============================
DATA_FILE = "train_data.csv"
MODEL_FILE = "elderly_behavior_model.pkl"

ANOMALY_CONTAMINATION = 0.02   # realistic for synthetic-normal data

# ============================
# LOAD DATA
# ============================
print(f"📥 Loading training data: {DATA_FILE}")

try:
    df = pd.read_csv(DATA_FILE)
except FileNotFoundError:
    print("❌ train_data.csv not found. Run trainsim.py first.")
    exit(1)

df["timestamp"] = pd.to_datetime(df["timestamp"])

# 🔴 CRITICAL FIX: remove empty device rows
df = df[df["device"].notna() & (df["device"] != "")]

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
hourly["hour_of_day"] = hourly["hour"].dt.hour

# ============================
# TRUE INACTIVITY STREAK
# (MUST MATCH monitor.py)
# ============================
hourly["inactive"] = (hourly["active_devices"] == 0).astype(int)

streak = 0
streaks = []
for inactive in hourly["inactive"]:
    streak = streak + 1 if inactive else 0
    streaks.append(streak)

hourly["inactivity_streak"] = streaks

# ============================
# FEATURE ENGINEERING
# ============================
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

X_train = hourly[FEATURES].fillna(0)

# ============================
# TRAIN MODEL
# ============================
print("🧠 Training Isolation Forest...")

model = IsolationForest(
    n_estimators=300,
    contamination=ANOMALY_CONTAMINATION,
    random_state=42,
    n_jobs=-1
)

model.fit(X_train)

# ============================
# SAVE MODEL
# ============================
joblib.dump(model, MODEL_FILE)

print("✅ Training complete")
print(f"📦 Model saved as: {MODEL_FILE}")
print(f"📊 Training samples: {len(X_train)}")

