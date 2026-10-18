# Face Recognition Attendance Database (Terminal Project)

A Python terminal-based mini project demonstrating **hashing, storage, database management, and face recognition**.

## Features
- Register students and capture face samples using a webcam
- Recognize registered students with OpenCV LBPH face recognition
- Store students and attendance in SQLite
- Prevent duplicate attendance for the same student on the same date
- Use a Python dictionary as a hash table for fast student-ID lookup
- Use SHA-256 hashes to detect changes to attendance record fields
- View attendance by date and export all attendance to CSV

## Requirements
- Python 3.10 or newer recommended
- Webcam
- Windows, macOS, or Linux

## Setup (Windows PowerShell)
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

If PowerShell blocks activation, run this once in the current terminal:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Setup (Linux/macOS)
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

## How to use
1. Select **1** and register each student with a unique student ID.
2. Look toward the webcam and press **SPACE** to capture each sample. Capture at least 10; 20 is recommended.
3. Select **2** to start recognition. Press **Q** in the camera window to stop.
4. Select **3** to list students, **4** to view attendance, or **5** to export a CSV.
5. Select **6** to verify stored attendance hashes.
6. If you add or remove face samples manually, select **7** to retrain.

## Data files created automatically
- `attendance.db` — SQLite database containing students and attendance
- `faces/<label>/` — grayscale face samples for each registered student
- `face_model.yml` — trained OpenCV LBPH model
- `attendance_export.csv` — generated when CSV export is selected

## DSA / course concepts
- **Hash table:** Python dictionary used to check whether a student ID exists (average O(1) lookup).
- **Hashing:** SHA-256 digest stored per attendance row. This is a basic integrity check, not a digital signature or tamper-proof audit system.
- **Storage:** Face samples are stored as image files; structured records are stored in SQLite.
- **Database constraints:** Primary keys, foreign keys, and a unique `(student_id, attendance_date)` constraint prevent duplicate daily attendance.
- **Searching:** SQLite queries retrieve students and daily attendance.

## Important limitations
- LBPH is a lightweight classroom/demo approach, not a high-security biometric system. Lighting, camera angle, and threshold settings affect accuracy.
- A photo or screen replay may fool basic face recognition. This project does not include liveness detection.
- SHA-256 hashes do not encrypt records, and someone with database write access could alter records and recompute hashes. Do not use this as a production attendance system.
- Obtain consent before capturing biometric data. Store the project locally and delete face samples when no longer needed.
