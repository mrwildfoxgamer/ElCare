import pandas as pd
import joblib
import time
import os
import json
from datetime import datetime

# ============================
# CONFIG
# ============================
DATA_FILE = "test_data.csv"
MODEL_FILE = "elderly_behavior_model.pkl"
INACTIVITY_THRESHOLD_HOURS = 3
CHECK_INTERVAL = 1  # Check every 1 second (matches data generation)
ALERT_LOG_FILE = "alerts_log.json"
WARNING_LOG_FILE = "warnings_log.json"

# ============================
# LOAD MODEL
# ============================
print("Loading ML model...")
model = joblib.load(MODEL_FILE)
print("✓ Model loaded successfully")

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
        "timestamp": datetime.now().isoformat(),
        "warning_hour": warning_row["hour"].isoformat(),
        "total_power": float(warning_row["total_power"]),
        "active_devices": int(warning_row["active_devices"]),
        "inactivity_streak": float(warning_row["inactivity_streak"]),
        "anomaly_score": float(warning_row["anomaly_score"]),
        "ml_anomaly": bool(warning_row["anomaly"] == -1),
        "high_inactivity": bool(warning_row["inactivity_streak"] >= INACTIVITY_THRESHOLD_HOURS)
    }
    
    warning_history.append(warning_data)
    
    # Load existing data, append, and save
    if os.path.exists(WARNING_LOG_FILE):
        with open(WARNING_LOG_FILE, 'r') as f:
            warnings = json.load(f)
    else:
        warnings = []
    
    warnings.append(warning_data)
    
    with open(WARNING_LOG_FILE, 'w') as f:
        json.dump(warnings, f, indent=2)
    
    return warning_data


def log_alert(alert_row):
    """Log alert to file and history"""
    alert_data = {
        "timestamp": datetime.now().isoformat(),
        "alert_hour": alert_row["hour"].isoformat(),
        "total_power": float(alert_row["total_power"]),
        "active_devices": int(alert_row["active_devices"]),
        "inactivity_streak": float(alert_row["inactivity_streak"]),
        "anomaly_score": float(alert_row["anomaly_score"])
    }
    
    alert_history.append(alert_data)
    
    # Load existing data, append, and save
    if os.path.exists(ALERT_LOG_FILE):
        with open(ALERT_LOG_FILE, 'r') as f:
            alerts = json.load(f)
    else:
        alerts = []
    
    alerts.append(alert_data)
    
    with open(ALERT_LOG_FILE, 'w') as f:
        json.dump(alerts, f, indent=2)
    
    return alert_data


def display_warning(warning_data):
    """Display warning in console"""
    print("\n" + "="*60)
    print("⚠️ WARNING - UNUSUAL PATTERN DETECTED")
    print("="*60)
    print(f"Detection Time:     {warning_data['timestamp']}")
    print(f"Warning Hour:       {warning_data['warning_hour']}")
    print(f"Total Power:        {warning_data['total_power']:.2f} W")
    print(f"Active Devices:     {warning_data['active_devices']}")
    print(f"Inactivity Streak:  {warning_data['inactivity_streak']:.0f} hours")
    print(f"Anomaly Score:      {warning_data['anomaly_score']:.4f}")
    print("-"*60)
    
    if warning_data['ml_anomaly']:
        print("🔸 ML Model detected anomalous behavior")
    if warning_data['high_inactivity']:
        print("🔸 High inactivity detected (>= 6 hours)")
    
    print("="*60)
    print("ℹ️ Monitoring situation - not yet critical")
    print("="*60 + "\n")


def display_alert(alert_data):
    """Display alert in console"""
    print("\n" + "="*60)
    print("🚨 EMERGENCY ALERT - IMMEDIATE ATTENTION REQUIRED! 🚨")
    print("="*60)
    print(f"Detection Time:     {alert_data['timestamp']}")
    print(f"Alert Hour:         {alert_data['alert_hour']}")
    print(f"Total Power:        {alert_data['total_power']:.2f} W")
    print(f"Active Devices:     {alert_data['active_devices']}")
    print(f"Inactivity Streak:  {alert_data['inactivity_streak']:.0f} hours")
    print(f"Anomaly Score:      {alert_data['anomaly_score']:.4f}")
    print("="*60)
    print("🔴 BOTH CONDITIONS MET:")
    print("   • ML Model detected anomaly")
    print("   • High inactivity (>= 6 hours)")
    print("="*60)
    print("⚠️ CRITICAL: Check on elderly person immediately!")
    print("="*60 + "\n")


def display_status(hourly, new_entries):
    """Display current monitoring status"""
    if hourly.empty:
        return
    
    latest = hourly.iloc[-1]
    
    # Determine status
    if latest["alert"]:
        status = "🚨 EMERGENCY"
        detail = "No activity"
    elif latest["warning"]:
        status = "⚠️ WARNING"
        if latest["anomaly"] == -1:
            detail = "Unusual pattern"
        else:
            detail = f"{latest['inactivity_streak']:.0f}h inactive"
    else:
        status = "🟢 NORMAL"
        detail = f"{int(latest['active_devices'])} devices active"
    
    print(f"{status} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {detail}")


# ============================
# MAIN MONITORING LOOP
# ============================
def monitor_continuous():
    """Continuously monitor the data file for new entries"""
    global last_processed_count
    
    print("\n" + "="*60)
    print("🏥 REAL-TIME ELDERLY MONITORING SYSTEM")
    print("="*60)
    print(f"Monitoring file: {DATA_FILE}")
    print(f"Check interval: {CHECK_INTERVAL} second(s)")
    print(f"Inactivity threshold: {INACTIVITY_THRESHOLD_HOURS} hours")
    print("="*60)
    print("STATUS LEVELS:")
    print("  🟢 NORMAL     - All conditions normal")
    print("  🟡 ML ANOMALY - ML detected anomaly only")
    print("  ⚠️ WARNING    - One condition met (concerning)")
    print("  🚨 EMERGENCY  - Both conditions met (critical!)")
    print("="*60)
    print("Press Ctrl+C to stop monitoring\n")
    
    try:
        while True:
            # Check if file exists
            if not os.path.exists(DATA_FILE):
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Waiting for data file...")
                time.sleep(CHECK_INTERVAL)
                continue
            
            # Read current data
            df = pd.read_csv(DATA_FILE)
            current_count = len(df)
            
            # Check if there's new data
            if current_count > last_processed_count:
                new_entries = current_count - last_processed_count
                
                # Process and run inference
                hourly = process_data(df)
                hourly = run_inference(hourly)
                
                # Check for new ALERTS (both conditions)
                alerts = hourly[hourly["alert"]]
                
                if not alerts.empty:
                    for idx, alert_row in alerts.iterrows():
                        alert_hour = alert_row["hour"]
                        
                        # Check if already alerted
                        already_alerted = any(
                            a["alert_hour"] == alert_hour.isoformat()
                            for a in alert_history
                        )
                        
                        if not already_alerted:
                            alert_data = log_alert(alert_row)
                            display_alert(alert_data)
                
                # Check for new WARNINGS (only one condition)
                warnings = hourly[hourly["warning"]]
                
                if not warnings.empty:
                    for idx, warning_row in warnings.iterrows():
                        warning_hour = warning_row["hour"]
                        
                        # Check if already warned
                        already_warned = any(
                            w["warning_hour"] == warning_hour.isoformat()
                            for w in warning_history
                        )
                        
                        if not already_warned:
                            warning_data = log_warning(warning_row)
                            display_warning(warning_data)
                
                # Display status
                display_status(hourly, new_entries)
                
                # Update counter
                last_processed_count = current_count
            
            # Wait before next check
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n" + "="*60)
        print("Monitoring stopped by user")
        print(f"Total warnings: {len(warning_history)}")
        print(f"Total alerts: {len(alert_history)}")
        
        if warning_history:
            print("\nWarning Summary:")
            for i, warning in enumerate(warning_history, 1):
                conditions = []
                if warning['ml_anomaly']:
                    conditions.append("ML Anomaly")
                if warning['high_inactivity']:
                    conditions.append("High Inactivity")
                print(f"  {i}. {warning['warning_hour']} - {', '.join(conditions)}")
        
        if alert_history:
            print("\nAlert Summary:")
            for i, alert in enumerate(alert_history, 1):
                print(f"  {i}. {alert['alert_hour']} - "
                      f"Inactivity: {alert['inactivity_streak']:.0f}h")
        print("="*60)


# ============================
# RUN MONITORING
# ============================
if __name__ == "__main__":
    monitor_continuous()
