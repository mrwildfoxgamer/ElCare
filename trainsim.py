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
    "tv": 100
}

ROUTINE = {
    "morning": (6, 9),
    "afternoon": (12, 14),
    "evening": (18, 21),
    "night": (22, 5)
}

# ----------------------------
# SIMULATION PARAMETERS
# ----------------------------
START_DATE = datetime(2026, 1, 1)
DAYS = 30
STEP_MINUTES = 10
EMERGENCY_DAY = -1

# ----------------------------
# SIMULATION LOGIC
# ----------------------------
def is_time_between(hour, start, end):
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end


def generate_activity(hour, emergency=False):
    active_devices = []

    if emergency:
        return active_devices  # no activity at all

    if is_time_between(hour, *ROUTINE["morning"]):
        active_devices += ["bedroom_light", "kettle"]
        if random.random() > 0.3:
            active_devices.append("bedroom_fan")

    elif is_time_between(hour, *ROUTINE["afternoon"]):
        if random.random() > 0.5:
            active_devices += ["kitchen_light", "stove"]

    elif is_time_between(hour, *ROUTINE["evening"]):
        active_devices += ["tv", "bedroom_light"]

    elif is_time_between(hour, *ROUTINE["night"]):
        if random.random() > 0.85:
            active_devices.append("bathroom_light")

    return active_devices


# ----------------------------
# RUN SIMULATION
# ----------------------------
events = []
current_time = START_DATE

for day in range(DAYS):
    emergency = (day == EMERGENCY_DAY)

    for _ in range(int(24 * 60 / STEP_MINUTES)):
        hour = current_time.hour
        active = generate_activity(hour, emergency)

        for device in active:
            events.append({
                "timestamp": current_time,
                "device": device,
                "power": DEVICES[device],
                "state": "ON"
            })

        current_time += timedelta(minutes=STEP_MINUTES)

# ----------------------------
# SAVE OUTPUT
# ----------------------------
df = pd.DataFrame(events)
df.to_csv("train_data.csv", index=False) # Save as test data
print("Saved traning Data to test_data.csv")

