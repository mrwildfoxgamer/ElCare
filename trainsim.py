import random
import pandas as pd
from datetime import datetime, timedelta

# ----------------------------
# HOUSE CONFIGURATION
# ----------------------------
DEVICES = {
    "bedroom_light": 12,
    "bedroom_fan": 60,
    "kitchen_light": 15,
    "kettle": 1200,
    "stove": 1500,
    "bathroom_light": 10,
    "tv": 100,
    "refrigerator": 150,
    "microwave": 1000,
    "phone_charger": 5,
    "lamp": 8
}

ROUTINE = {
    "morning": (6, 9),
    "afternoon": (12, 14),
    "evening": (18, 21),
    "night": (22, 5)
}

# ----------------------------
# CONFIGURATION - INCREASED DATA
# ----------------------------
CSV_FILE = "train_data.csv"
DAYS_OF_DATA = 60  # Generate 60 days (increased from typical 7-14 days)
STEP_MINUTES = 10   # Data point every 10 minutes
ENTRIES_PER_DAY = (24 * 60) // STEP_MINUTES  # 144 entries per day

# ----------------------------
# HELPER FUNCTIONS
# ----------------------------
def is_time_between(hour, start, end):
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end


def generate_activity(hour, day_of_week, add_variation=True):
    """
    Generate realistic activity based on time of day
    
    Args:
        hour: Hour of the day (0-23)
        day_of_week: Day of week (0=Monday, 6=Sunday)
        add_variation: Add random variation to make data more realistic
    """
    active_devices = []
    
    # Morning routine (6 AM - 9 AM)
    if is_time_between(hour, *ROUTINE["morning"]):
        active_devices += ["bedroom_light", "kettle"]
        
        if random.random() > 0.3:
            active_devices.append("bedroom_fan")
        
        if random.random() > 0.4:
            active_devices.append("bathroom_light")
        
        if random.random() > 0.6:
            active_devices.append("microwave")
        
        # Always charging phone in morning
        if random.random() > 0.2:
            active_devices.append("phone_charger")
    
    # Mid-morning (9 AM - 12 PM)
    elif is_time_between(hour, 9, 12):
        if random.random() > 0.6:
            active_devices.append("tv")
        
        if random.random() > 0.7:
            active_devices.append("lamp")
    
    # Afternoon routine (12 PM - 2 PM)
    elif is_time_between(hour, *ROUTINE["afternoon"]):
        if random.random() > 0.4:
            active_devices += ["kitchen_light", "stove"]
        
        if random.random() > 0.5:
            active_devices.append("microwave")
        
        # Refrigerator opens more during meal prep
        if random.random() > 0.3:
            active_devices.append("refrigerator")
    
    # Mid-afternoon (2 PM - 6 PM)
    elif is_time_between(hour, 14, 18):
        # Quieter period - possible nap time
        if random.random() > 0.8:
            active_devices.append("bathroom_light")
        
        if random.random() > 0.7:
            active_devices.append("kettle")
        
        if random.random() > 0.5:
            active_devices.append("tv")
    
    # Evening routine (6 PM - 9 PM)
    elif is_time_between(hour, *ROUTINE["evening"]):
        active_devices += ["tv", "bedroom_light"]
        
        if random.random() > 0.4:
            active_devices.append("kitchen_light")
        
        if random.random() > 0.5:
            active_devices.append("lamp")
        
        if random.random() > 0.6:
            active_devices.append("stove")
    
    # Late evening (9 PM - 11 PM)
    elif is_time_between(hour, 21, 23):
        if random.random() > 0.3:
            active_devices.append("tv")
        
        if random.random() > 0.4:
            active_devices.append("bedroom_light")
        
        if random.random() > 0.6:
            active_devices.append("bathroom_light")
        
        # Charging phone before bed
        if random.random() > 0.3:
            active_devices.append("phone_charger")
    
    # Night/Sleep (11 PM - 6 AM)
    elif is_time_between(hour, *ROUTINE["night"]):
        # Occasional bathroom visits
        if random.random() > 0.9:
            active_devices.append("bathroom_light")
        
        # Phone charging overnight
        if random.random() > 0.5:
            active_devices.append("phone_charger")
    
    # Weekend variations
    if day_of_week in [5, 6] and add_variation:  # Saturday, Sunday
        if random.random() > 0.7:
            # More TV time on weekends
            if "tv" not in active_devices and random.random() > 0.5:
                active_devices.append("tv")
    
    # Add some random noise to make data realistic
    if add_variation:
        # Occasionally miss a routine
        if random.random() > 0.95:
            if active_devices:
                active_devices.pop(random.randint(0, len(active_devices) - 1))
        
        # Occasionally add unexpected device
        if random.random() > 0.9:
            unexpected = random.choice(list(DEVICES.keys()))
            if unexpected not in active_devices:
                active_devices.append(unexpected)
    
    return active_devices


def generate_training_data(csv_file, days=60):
    """
    Generate comprehensive training data
    
    Args:
        csv_file: Output CSV file path
        days: Number of days to generate (default: 60)
    """
    
    print(f"Generating {days} days of training data...")
    print(f"Time step: {STEP_MINUTES} minutes")
    print(f"Entries per day: {ENTRIES_PER_DAY}")
    print(f"Total entries: {days * ENTRIES_PER_DAY:,}")
    print("-" * 60)
    
    # Start from 60 days ago
    start_time = datetime.now() - timedelta(days=days)
    current_time = start_time
    
    all_events = []
    entry_count = 0
    
    # Generate data for each time step
    for day in range(days):
        day_of_week = (start_time + timedelta(days=day)).weekday()
        
        for step in range(ENTRIES_PER_DAY):
            hour = current_time.hour
            
            # Generate activity for this time
            active_devices = generate_activity(hour, day_of_week)
            
            # Create events for each active device
            for device in active_devices:
                all_events.append({
                    "timestamp": current_time,
                    "device": device,
                    "power": DEVICES[device],
                    "state": "ON"
                })
            
            entry_count += 1
            
            # Progress indicator
            if entry_count % 1000 == 0:
                progress = (entry_count / (days * ENTRIES_PER_DAY)) * 100
                print(f"Progress: {progress:.1f}% - Generated {entry_count:,} entries - Current: {current_time.strftime('%Y-%m-%d %H:%M')}")
            
            # Advance time
            current_time += timedelta(minutes=STEP_MINUTES)
    
    # Create DataFrame and save
    print("\nCreating DataFrame...")
    df = pd.DataFrame(all_events)
    
    print(f"Saving to {csv_file}...")
    df.to_csv(csv_file, index=False)
    
    # Statistics
    print("\n" + "="*60)
    print("DATA GENERATION COMPLETE")
    print("="*60)
    print(f"File: {csv_file}")
    print(f"Total entries: {len(df):,}")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"Unique devices: {df['device'].nunique()}")
    print(f"Total power events: {len(df):,}")
    
    # Device usage statistics
    print("\nDevice Usage Statistics:")
    device_counts = df['device'].value_counts()
    for device, count in device_counts.items():
        percentage = (count / len(df)) * 100
        print(f"  {device:20s}: {count:6,} times ({percentage:5.2f}%)")
    
    # Hourly activity
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['hour'] = df['timestamp'].dt.hour
    hourly_activity = df.groupby('hour').size()
    
    print("\nPeak Activity Hours:")
    top_hours = hourly_activity.nlargest(5)
    for hour, count in top_hours.items():
        print(f"  {hour:02d}:00 - {count:,} events")
    
    print("="*60 + "\n")
    
    return df


# ----------------------------
# MAIN EXECUTION
# ----------------------------
if __name__ == "__main__":
    print("\n" + "="*60)
    print("TRAINING DATA GENERATOR")
    print("="*60)
    print("\nThis will generate normal behavior data for training the ML model.")
    print(f"Output file: {CSV_FILE}")
    print(f"Duration: {DAYS_OF_DATA} days")
    print(f"Total time points: {DAYS_OF_DATA * ENTRIES_PER_DAY:,}")
    print("\nThis represents NORMAL elderly behavior patterns only.")
    print("="*60 + "\n")
    
    response = input("Start generation? (yes/no): ").strip().lower()
    
    if response == 'yes':
        generate_training_data(CSV_FILE, DAYS_OF_DATA)
    else:
        print("\nGeneration cancelled.")
