# Synthetic Data for Training

This folder provides a reproducible synthetic MedSpa dataset generator for local Eve testing and acceptance-gate quality control.

## What it generates

Running the generator script produces four relational CSV files:

- `medspa_clinics.csv`
- `medspa_patients.csv`
- `medspa_appointments.csv`
- `medspa_conversations.csv`

These files are linked by `clinic_id` and `patient_id` so Eve can be evaluated against both structured records and unstructured conversational logs.

## Prerequisites

```bash
pip install faker pandas
```

## Usage

```bash
python generate_medspa_synthetic_data.py
```

Optional output directory:

```bash
python generate_medspa_synthetic_data.py --output-dir ./data
```

## Notes

- The script is seeded for reproducibility.
- Data includes common MedSpa intents (booking, pricing, cancellation/reschedule, post-treatment follow-up).
