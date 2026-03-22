import argparse
import random
from datetime import timedelta
from pathlib import Path

import pandas as pd
from faker import Faker


# Initialize Faker and seed for reproducibility
fake = Faker()
Faker.seed(42)
random.seed(42)

# Configuration
NUM_CLINICS = 100
NUM_PATIENTS = 10000
NUM_CONVERSATION_SESSIONS = 15000

# MedSpa Domain Data
MEDSPA_SERVICES = [
    "Botox",
    "Dermal Fillers",
    "Laser Hair Removal",
    "Chemical Peel",
    "Microneedling",
    "CoolSculpting",
    "HydraFacial",
    "Laser Skin Resurfacing",
    "IV Therapy",
    "Tattoo Removal",
]
APPT_STATUSES = [
    "Completed",
    "Completed",
    "Completed",
    "Cancelled",
    "No-Show",
    "Scheduled",
    "Scheduled",
]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
TIMES = ["09:00 AM", "10:30 AM", "11:00 AM", "01:00 PM", "02:30 PM", "04:00 PM"]


def generate_data(output_dir: Path) -> None:
    print("Generating synthetic MedSpa data... This may take a few moments.")

    # 1. Generate Clinics
    print("Generating Clinics...")
    clinics = []
    for i in range(1, NUM_CLINICS + 1):
        clinics.append(
            {
                "clinic_id": i,
                "clinic_name": f"{fake.last_name()} {random.choice(['MedSpa', 'Aesthetics', 'Wellness Center', 'Skin Clinic'])}",
                "address": fake.street_address(),
                "city": fake.city(),
                "state": fake.state_abbr(),
                "zip_code": fake.zipcode(),
                "phone": fake.phone_number(),
                "email": f"info@{fake.domain_name()}",
            }
        )
    df_clinics = pd.DataFrame(clinics)

    # 2. Generate Patients
    print("Generating Patients...")
    patients = []
    for i in range(1, NUM_PATIENTS + 1):
        patients.append(
            {
                "patient_id": i,
                "primary_clinic_id": random.randint(1, NUM_CLINICS),
                "first_name": fake.first_name(),
                "last_name": fake.last_name(),
                "dob": fake.date_of_birth(minimum_age=18, maximum_age=70).strftime("%Y-%m-%d"),
                "gender": random.choice(
                    ["Female", "Female", "Female", "Male", "Non-binary"]
                ),  # Weighted towards typical MedSpa demographics
                "email": fake.email(),
                "phone": fake.phone_number(),
            }
        )
    df_patients = pd.DataFrame(patients)

    # 3. Generate Appointments
    print("Generating Appointments...")
    appointments = []
    appt_id = 1
    for p in patients:
        # Each patient has between 0 and 6 appointments
        num_appts = random.randint(0, 6)
        for _ in range(num_appts):
            appt_date = fake.date_between(start_date="-2y", end_date="+3m")
            appointments.append(
                {
                    "appointment_id": appt_id,
                    "patient_id": p["patient_id"],
                    "clinic_id": p["primary_clinic_id"],
                    "service": random.choice(MEDSPA_SERVICES),
                    "appointment_date": appt_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "status": random.choice(APPT_STATUSES),
                    "provider_name": f"{fake.first_name()} {fake.last_name()}, {random.choice(['RN', 'NP', 'MD', 'Esthetician'])}",
                }
            )
            appt_id += 1
    df_appts = pd.DataFrame(appointments)

    # 4. Generate Conversational Logs
    print("Generating Conversational Logs...")
    conversations = []
    log_id = 1

    # Chat templates representing common MedSpa intents
    chat_templates = [
        # Booking Intent
        [
            {"role": "user", "text": "Hi, I want to book a {service} appointment."},
            {
                "role": "agent",
                "text": "Absolutely! I can help you schedule your {service}. What day of the week works best for you?",
            },
            {"role": "user", "text": "Do you have anything next {day}?"},
            {
                "role": "agent",
                "text": "Let me check our calendar for next {day}... Yes, we have a slot at {time}. Does that work?",
            },
            {"role": "user", "text": "Perfect, book it."},
        ],
        # Pricing Inquiry
        [
            {"role": "user", "text": "How much does {service} cost?"},
            {
                "role": "agent",
                "text": "Our {service} treatments typically start at ${price}. Would you like to book a free consultation to get an exact quote?",
            },
            {"role": "user", "text": "No thanks, I'll think about it."},
        ],
        # Cancellation/Reschedule
        [
            {
                "role": "user",
                "text": "I need to cancel my appointment for tomorrow.",
            },
            {
                "role": "agent",
                "text": "I can help with that. Can you please verify your name and phone number?",
            },
            {"role": "user", "text": "It's {first_name} {last_name}, {phone}."},
            {
                "role": "agent",
                "text": "Thank you, {first_name}. I have cancelled your appointment. Let us know when you're ready to reschedule.",
            },
        ],
        # Post-Treatment Question
        [
            {
                "role": "user",
                "text": "I had {service} done yesterday and my skin is a bit red. Is that normal?",
            },
            {
                "role": "agent",
                "text": "Hi {first_name}, mild redness is completely normal for 24-48 hours after {service}. Are you experiencing any severe pain or blistering?",
            },
            {"role": "user", "text": "No, just redness. Thanks for letting me know!"},
            {
                "role": "agent",
                "text": "You're welcome! Please reach out if symptoms worsen or don't subside in a few days.",
            },
        ],
    ]

    for session_id in range(1, NUM_CONVERSATION_SESSIONS + 1):
        patient = random.choice(patients)
        template = random.choice(chat_templates)
        service = random.choice(MEDSPA_SERVICES)

        # Start the conversation at a random time in the past year
        timestamp = fake.date_time_between(start_date="-1y", end_date="now")

        for msg in template:
            # Format the text with context-aware variables
            text = msg["text"].format(
                service=service,
                day=random.choice(DAYS),
                time=random.choice(TIMES),
                price=random.randint(150, 800),
                first_name=patient["first_name"],
                last_name=patient["last_name"],
                phone=patient["phone"],
            )

            conversations.append(
                {
                    "log_id": log_id,
                    "session_id": session_id,
                    "patient_id": patient["patient_id"],
                    "clinic_id": patient["primary_clinic_id"],
                    "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "role": msg["role"],
                    "message": text,
                }
            )

            # Increment timestamp by a few minutes to simulate human/bot typing delay
            timestamp += timedelta(minutes=random.randint(1, 5))
            log_id += 1

    df_convos = pd.DataFrame(conversations)

    # Export Data to CSV
    print("Exporting data to CSV files...")
    output_dir.mkdir(parents=True, exist_ok=True)

    df_clinics.to_csv(output_dir / "medspa_clinics.csv", index=False)
    df_patients.to_csv(output_dir / "medspa_patients.csv", index=False)
    df_appts.to_csv(output_dir / "medspa_appointments.csv", index=False)
    df_convos.to_csv(output_dir / "medspa_conversations.csv", index=False)

    print("Success! Generated:")
    print(f"- {len(df_clinics)} Clinics")
    print(f"- {len(df_patients)} Patients")
    print(f"- {len(df_appts)} Appointments")
    print(
        f"- {len(df_convos)} Conversational Messages ({NUM_CONVERSATION_SESSIONS} sessions)"
    )
    print(f"Output directory: {output_dir.resolve()}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate synthetic relational MedSpa CSV datasets for Eve training."
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory where CSV files will be written (default: current directory)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    generate_data(Path(args.output_dir))
