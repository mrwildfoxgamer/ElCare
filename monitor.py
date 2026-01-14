import pandas as pd
import joblib
import time
import os
from datetime import datetime

# ============================
# CONFIG
# ============================
DATA_FILE = "test_data.csv"
MODEL_FILE = "elderly_behavior_model.pkl"
INACTIVITY_THRESHOLD_HOURS = 1  # Updated to 1 to ensure 2hr anomaly is detected
CHECK_INTERVAL = 1 
ALERT_LOG_FILE = "alerts_log.csv"
WARNING_LOG_FILE = "warnings_log.csv"

# ============================
# LOAD MODEL
# ============================
# print("Loading ML model...")
model = joblib.load(MODEL_FILE)
# print("✓ Model loaded successfully")

# ============================
# TRACKING STATE
# ============================
last_processed_count = 0
alert_history = []
warning_history = []

# ============================
# HELPER FUNCTIONS
# ============================
def process_data(df):
    """Process raw data into hourly aggregated features"""
    if df.empty:
        return pd.DataFrame()
    
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    
    # Aggregate to hourly
    df["hour"] = df["timestamp"].dt.floor("h")
    hourly_groups = df.groupby("hour")
    
    # Create full timeline
    full_range = pd.date_range(
        start=df["hour"].min(), 
        end=df["hour"].max(), 
        freq="h"
    )
    
    hourly = pd.DataFrame(index=full_range)
    hourly.index.name = "hour"
    
    hourly["total_power"] = hourly_groups["power"].sum()
    hourly["active_devices"] = hourly_groups["device"].nunique()
    
    # Fill NaNs with 0
    hourly = hourly.fillna(0).reset_index()
    
    # Feature engineering
    hourly["hour_of_day"] = hourly["hour"].dt.hour
    hourly["inactive"] = (hourly["active_devices"] == 0).astype(int)
    
    hourly["inactivity_streak"] = hourly["inactive"].rolling(
        window=INACTIVITY_THRESHOLD_HOURS,
        min_periods=1
    ).sum()
    
    return hourly


def run_inference(hourly):
    """Run ML inference on processed data"""
    if hourly.empty:
        return hourly
    
    FEATURES = [
        "total_power",
        "active_devices",
        "hour_of_day",
        "inactivity_streak"
    ]
    
    X = hourly[FEATURES]
    
    hourly["anomaly_score"] = model.decision_function(X)
    hourly["anomaly"] = model.predict(X)
    
    # Define conditions
    condition_ml_anomaly = (hourly["anomaly"] == -1)
    condition_inactivity = (hourly["inactivity_streak"] >= INACTIVITY_THRESHOLD_HOURS)
    
    # WARNING: Only one condition is true
    hourly["warning"] = (
        (condition_ml_anomaly & ~condition_inactivity) |
        (~condition_ml_anomaly & condition_inactivity)
    )
    
    # ALERT: Both conditions are true
    hourly["alert"] = (condition_ml_anomaly & condition_inactivity)
    
    return hourly


def log_warning(warning_row):
    """Log warning to file and history"""
    warning_data = {
        "timestamp": datetime.now(),
        "warning_hour": warning_row["hour"],
        "total_power": warning_row["total_power"],
        "active_devices": warning_row["active_devices"],
        "inactivity_streak": warning_row["inactivity_streak"],
        "anomaly_score": warning_row["anomaly_score"],
        "ml_anomaly": warning_row["anomaly"] == -1,
        "high_inactivity": warning_row["inactivity_streak"] >= INACTIVITY_THRESHOLD_HOURS
    }
    
    warning_history.append(warning_data)
    
    # Save to log file
    df_warning = pd.DataFrame([warning_data])
    if os.path.exists(WARNING_LOG_FILE):
        df_warning.to_csv(WARNING_LOG_FILE, mode='a', header=False, index=False)
    else:
        df_warning.to_csv(WARNING_LOG_FILE, mode='w', header=True, index=False)
    
    return warning_data


def log_alert(alert_row):
    """Log alert to file and history"""
    alert_data = {
        "timestamp": datetime.now(),
        "alert_hour": alert_row["hour"],
        "total_power": alert_row["total_power"],
        "active_devices": alert_row["active_devices"],
        "inactivity_streak": alert_row["inactivity_streak"],
        "anomaly_score": alert_row["anomaly_score"]
    }
    
    alert_history.append(alert_data)
    
    # Save to log file
    df_alert = pd.DataFrame([alert_data])
    if os.path.exists(ALERT_LOG_FILE):
        df_alert.to_csv(ALERT_LOG_FILE, mode='a', header=False, index=False)
    else:
        df_alert.to_csv(ALERT_LOG_FILE, mode='w', header=True, index=False)
    
    return alert_data


def display_status(hourly):
    """Display ONLY the status with no extra info"""
    if hourly.empty:
        return
    
    latest = hourly.iloc[-1]
    
    # Determine status
    if latest["alert"]:
        print("🚨 EMERGENCY")
    elif latest["warning"]:
        print("⚠️  WARNING")
    elif latest["anomaly"] == -1:
        print("🟡 ML ANOMALY")
    else:
        print("🟢 NORMAL")


# ============================
# MAIN MONITORING LOOP
# ============================
def monitor_continuous():
    """Continuously monitor the data file for new entries"""
    global last_processed_count
    
    # Minimal Startup Message
    print("...Monitoring Started...")
    
    try:
        while True:
            # Check if file exists
            if not os.path.exists(DATA_FILE):
                time.sleep(CHECK_INTERVAL)
                continue
            
            # Read current data
            df = pd.read_csv(DATA_FILE)
            current_count = len(df)
            
            # Check if there's new data
            if current_count > last_processed_count:
                
                # Process and run inference
                hourly = process_data(df)
                hourly = run_inference(hourly)
                
                # Check for new ALERTS (logging only, no display)
                alerts = hourly[hourly["alert"]]
                if not alerts.empty:
                    for idx, alert_row in alerts.iterrows():
                        already_alerted = any(a["alert_hour"] == alert_row["hour"] for a in alert_history)
                        if not already_alerted:
                            log_alert(alert_row)
                            # display_alert(alert_data) # DISABLED
                
                # Check for new WARNINGS (logging only, no display)
                warnings = hourly[hourly["warning"]]
                if not warnings.empty:
                    for idx, warning_row in warnings.iterrows():
                        already_warned = any(w["warning_hour"] == warning_row["hour"] for w in warning_history)
                        if not already_warned:
                            log_warning(warning_row)
                            # display_warning(warning_data) # DISABLED
                
                # Display ONLY the minimal status
                display_status(hourly)
                
                # Update counter
                last_processed_count = current_count
            
            # Wait before next check
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print("\nStopped.")


# ============================
# RUN MONITORING
# ============================
if __name__ == "__main__":
    monitor_continuous()
