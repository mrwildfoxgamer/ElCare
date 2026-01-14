import pandas as pd
import random
from datetime import datetime, timedelta
import os

# ============================
# CONFIGURATION
# ============================
CSV_FILE = "test_data.csv"
ANOMALY_DURATION_HOURS = 2
BACKUP_FILE = "test_data_backup.csv"

# ============================
# ANOMALY INJECTION
# ============================
def inject_anomaly_period(csv_file, duration_hours=2):
    """
    Inject a period of complete inactivity (anomaly) into the CSV
    
    Args:
        csv_file: Path to the CSV file
        duration_hours: Duration of the anomaly in hours (default: 2)
    """
    
    # Check if file exists
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found!")
        print("Please run sim.py first to generate data.")
        return
    
    # Load existing data
    print(f"Loading data from {csv_file}...")
    df = pd.read_csv(csv_file)
    
    if df.empty:
        print("Error: CSV file is empty!")
        return
    
    # Backup original file
    print(f"Creating backup at {BACKUP_FILE}...")
    df.to_csv(BACKUP_FILE, index=False)
    
    # Parse timestamps
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    
    # Get the time range
    min_time = df["timestamp"].min()
    max_time = df["timestamp"].max()
    total_duration = max_time - min_time
    
    print(f"\nData range: {min_time} to {max_time}")
    print(f"Total duration: {total_duration}")
    
    # Select a random start time for the anomaly
    # Ensure there's enough room for the full anomaly duration
    max_start = max_time - timedelta(hours=duration_hours)
    
    if max_start <= min_time:
        print("Error: Not enough data to inject anomaly!")
        return
    
    # Random start time (at least 1 hour from the beginning for context)
    earliest_start = min_time + timedelta(hours=1)
    time_range = (max_start - earliest_start).total_seconds()
    
    if time_range <= 0:
        print("Error: Not enough data range to inject anomaly!")
        return
    
    random_offset = random.uniform(0, time_range)
    anomaly_start = earliest_start + timedelta(seconds=random_offset)
    
    # Round to nearest hour for cleaner anomaly period
    anomaly_start = anomaly_start.replace(minute=0, second=0, microsecond=0)
    anomaly_end = anomaly_start + timedelta(hours=duration_hours)
    
    print(f"\n{'='*60}")
    print(f"INJECTING ANOMALY PERIOD")
    print(f"{'='*60}")
    print(f"Start: {anomaly_start}")
    print(f"End:   {anomaly_end}")
    print(f"Duration: {duration_hours} hours")
    print(f"{'='*60}\n")
    
    # Remove all entries within the anomaly period
    original_count = len(df)
    df_filtered = df[~((df["timestamp"] >= anomaly_start) & 
                       (df["timestamp"] < anomaly_end))]
    removed_count = original_count - len(df_filtered)
    
    print(f"Original entries: {original_count}")
    print(f"Removed entries: {removed_count}")
    print(f"Remaining entries: {len(df_filtered)}")
    
    # Save modified data
    df_filtered = df_filtered.drop(columns=["timestamp"])  # Will be re-added
    df_filtered.to_csv(csv_file, index=False)
    
    print(f"\n✓ Anomaly injected successfully!")
    print(f"✓ Modified data saved to {csv_file}")
    print(f"✓ Original data backed up to {BACKUP_FILE}")
    
    return anomaly_start, anomaly_end


def verify_anomaly(csv_file):
    """Verify the anomaly was injected correctly"""
    print(f"\n{'='*60}")
    print("VERIFYING ANOMALY INJECTION")
    print(f"{'='*60}\n")
    
    df = pd.read_csv(csv_file)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    
    # Aggregate to hourly to see gaps
    df["hour"] = df["timestamp"].dt.floor("h")
    hourly_activity = df.groupby("hour").size()
    
    # Find hours with zero activity
    all_hours = pd.date_range(
        start=df["hour"].min(),
        end=df["hour"].max(),
        freq="h"
    )
    
    zero_activity_hours = []
    for hour in all_hours:
        if hour not in hourly_activity.index:
            zero_activity_hours.append(hour)
    
    if zero_activity_hours:
        print(f"Found {len(zero_activity_hours)} hour(s) with ZERO activity:")
        for hour in zero_activity_hours:
            print(f"  - {hour}")
    else:
        print("No hours with zero activity found.")
    
    print(f"\n{'='*60}\n")


# ============================
# MAIN EXECUTION
# ============================
if __name__ == "__main__":
    print("\n🚨 ANOMALY INJECTION TOOL 🚨\n")
    print("This script will inject a period of complete inactivity")
    print("into your existing test data to simulate an emergency.\n")
    
    # Inject the anomaly
    result = inject_anomaly_period(CSV_FILE, ANOMALY_DURATION_HOURS)
    
    if result:
        # Verify it was injected
        verify_anomaly(CSV_FILE)
        
        print("NEXT STEPS:")
        print("1. Run monitor.py to detect the anomaly in real-time")
        print("2. Or run inter.py to analyze the full dataset")
        print(f"3. To restore original data: cp {BACKUP_FILE} {CSV_FILE}")
