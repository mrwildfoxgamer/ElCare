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
INACTIVITY_THRESHOLD_HOURS = 6
CHECK_INTERVAL = 1  # Check every 1 second (matches data generation)
ALERT_LOG_FILE = "alerts_log.csv"

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
    
    # Alert logic
    hourly["alert"] = (
        (hourly["anomaly"] == -1) &
        (hourly["inactivity_streak"] >= INACTIVITY_THRESHOLD_HOURS)
    )
    
    return hourly


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


def display_alert(alert_data):
    """Display alert in console"""
    print("\n" + "="*60)
    print("🚨 EMERGENCY ALERT DETECTED! 🚨")
    print("="*60)
    print(f"Detection Time:     {alert_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Alert Hour:         {alert_data['alert_hour']}")
    print(f"Total Power:        {alert_data['total_power']:.2f} W")
    print(f"Active Devices:     {int(alert_data['active_devices'])}")
    print(f"Inactivity Streak:  {alert_data['inactivity_streak']:.0f} hours")
    print(f"Anomaly Score:      {alert_data['anomaly_score']:.4f}")
    print("="*60)
    print("⚠️  Possible emergency situation - Check on elderly person!")
    print("="*60 + "\n")


def display_status(hourly, new_entries):
    """Display current monitoring status"""
    if hourly.empty:
        return
    
    latest = hourly.iloc[-1]
    
    status = "🟢 NORMAL" if latest["anomaly"] == 1 else "🔴 ANOMALY"
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
          f"Status: {status} | "
          f"Hour: {latest['hour'].strftime('%Y-%m-%d %H:%M')} | "
          f"Power: {latest['total_power']:.0f}W | "
          f"Devices: {int(latest['active_devices'])} | "
          f"Inactive: {latest['inactivity_streak']:.0f}h | "
          f"New entries: {new_entries}")


# ============================
# MAIN MONITORING LOOP
# ============================
def monitor_continuous():
    """Continuously monitor the data file for new entries"""
    global last_processed_count
    
    print("\n" + "="*60)
    print("🔍 REAL-TIME ELDERLY MONITORING SYSTEM")
    print("="*60)
    print(f"Monitoring file: {DATA_FILE}")
    print(f"Check interval: {CHECK_INTERVAL} second(s)")
    print(f"Inactivity threshold: {INACTIVITY_THRESHOLD_HOURS} hours")
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
                
                # Check for new alerts
                alerts = hourly[hourly["alert"]]
                
                if not alerts.empty:
                    # Check if this is a new alert (not already logged)
                    for idx, alert_row in alerts.iterrows():
                        alert_hour = alert_row["hour"]
                        
                        # Check if we've already alerted for this hour
                        already_alerted = any(
                            a["alert_hour"] == alert_hour 
                            for a in alert_history
                        )
                        
                        if not already_alerted:
                            alert_data = log_alert(alert_row)
                            display_alert(alert_data)
                
                # Display status
                display_status(hourly, new_entries)
                
                # Update counter
                last_processed_count = current_count
            
            # Wait before next check
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n" + "="*60)
        print("Monitoring stopped by user")
        print(f"Total alerts detected: {len(alert_history)}")
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
