import cv2
import sqlite3
import hashlib
import csv
import os
from datetime import datetime, date

DB_FILE = "attendance.db"
FACES_DIR = "faces"
MODEL_FILE = "face_model.yml"
os.makedirs(FACES_DIR, exist_ok=True)

def connect():
    con = sqlite3.connect(DB_FILE)
    con.execute("PRAGMA foreign_keys = ON")
    return con

def init_db():
    with connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            face_label INTEGER UNIQUE NOT NULL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            attendance_date TEXT NOT NULL,
            attendance_time TEXT NOT NULL,
            record_hash TEXT NOT NULL,
            UNIQUE(student_id, attendance_date),
            FOREIGN KEY(student_id) REFERENCES students(student_id)
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        )""")
        con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('next_label','1')")

def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def student_hash_table():
    # Python dictionary provides average O(1) lookup by student ID.
    with connect() as con:
        return {row[0]: row[1] for row in con.execute(
            "SELECT student_id, name FROM students"
        )}

def register_student():
    student_id = input("Student ID: ").strip()
    name = input("Full name: ").strip()
    if not student_id or not name:
        print("Student ID and name are required.")
        return
    if student_id in student_hash_table():
        print("That student ID is already registered.")
        return

    print("Camera will open. Look at the camera and press SPACE to capture 20 face samples.")
    print("Press Q to cancel.")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open webcam. Check camera permissions or connection.")
        return

    samples, count = [], 0
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    while count < 20:
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(gray, 1.2, 5, minSize=(80, 80))
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.putText(frame, f"Samples: {count}/20 - SPACE capture, Q quit",
                        (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0,255,0), 2)
        cv2.imshow("Register face", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == 32 and len(faces) > 0:
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            face = cv2.resize(gray[y:y+h, x:x+w], (200, 200))
            samples.append(face)
            count += 1
    cap.release()
    cv2.destroyAllWindows()

    if len(samples) < 10:
        print("Registration cancelled: capture at least 10 samples.")
        return

    with connect() as con:
        label = int(con.execute("SELECT value FROM settings WHERE key='next_label'").fetchone()[0])
        con.execute("INSERT INTO students(student_id,name,face_label) VALUES(?,?,?)",
                    (student_id, name, label))
        con.execute("UPDATE settings SET value=? WHERE key='next_label'", (str(label + 1),))
    folder = os.path.join(FACES_DIR, str(label))
    os.makedirs(folder, exist_ok=True)
    for i, sample in enumerate(samples):
        cv2.imwrite(os.path.join(folder, f"{i}.png"), sample)
    train_model()
    print(f"Registered {name} ({student_id}) with {len(samples)} samples.")

def train_model():
    # LBPH is included in opencv-contrib-python.
    if not hasattr(cv2, "face"):
        print("OpenCV face module missing. Install opencv-contrib-python.")
        return
    images, labels = [], []
    with connect() as con:
        students = con.execute("SELECT face_label FROM students").fetchall()
    for (label,) in students:
        folder = os.path.join(FACES_DIR, str(label))
        if not os.path.isdir(folder):
            continue
        for filename in os.listdir(folder):
            if filename.lower().endswith((".png", ".jpg", ".jpeg")):
                image = cv2.imread(os.path.join(folder, filename), cv2.IMREAD_GRAYSCALE)
                if image is not None:
                    images.append(cv2.resize(image, (200, 200)))
                    labels.append(int(label))
    if images:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train(images, __import__("numpy").array(labels))
        recognizer.write(MODEL_FILE)

def mark_attendance(student_id):
    today = date.today().isoformat()
    now = datetime.now().strftime("%H:%M:%S")
    with connect() as con:
        student = con.execute("SELECT name FROM students WHERE student_id=?", (student_id,)).fetchone()
        if not student:
            return
        existing = con.execute("SELECT 1 FROM attendance WHERE student_id=? AND attendance_date=?",
                               (student_id, today)).fetchone()
        if existing:
            print(f"Already marked today: {student[0]} ({student_id})")
            return
        payload = f"{student_id}|{today}|{now}"
        con.execute("INSERT INTO attendance(student_id,attendance_date,attendance_time,record_hash) VALUES(?,?,?,?)",
                    (student_id, today, now, digest(payload)))
    print(f"Attendance marked: {student[0]} at {now}")

def recognize_attendance():
    if not hasattr(cv2, "face"):
        print("OpenCV face module missing. Run: pip install opencv-contrib-python")
        return
    if not os.path.exists(MODEL_FILE):
        print("No trained face model. Register at least one student first.")
        return
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.read(MODEL_FILE)
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open webcam.")
        return
    print("Looking for faces. Press Q to stop.")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        for (x, y, w, h) in detector.detectMultiScale(gray, 1.2, 5, minSize=(80, 80)):
            face = cv2.resize(gray[y:y+h, x:x+w], (200, 200))
            label, confidence = recognizer.predict(face)
            # Lower LBPH confidence is a closer match; tune threshold for your lighting/camera.
            name, student_id = "Unknown", None
            if confidence < 65:
                with connect() as con:
                    row = con.execute("SELECT student_id,name FROM students WHERE face_label=?", (int(label),)).fetchone()
                if row:
                    student_id, name = row
            color = (0, 255, 0) if student_id else (0, 0, 255)
            cv2.rectangle(frame, (x,y), (x+w,y+h), color, 2)
            cv2.putText(frame, f"{name} ({confidence:.1f})", (x,y-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
            if student_id:
                mark_attendance(student_id)
        cv2.imshow("Face attendance - Q to quit", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()
    cv2.destroyAllWindows()

def view_students():
    with connect() as con:
        rows = con.execute("SELECT student_id,name FROM students ORDER BY student_id").fetchall()
    if not rows:
        print("No students registered.")
    for sid, name in rows:
        print(f"{sid:<18} {name}")

def view_attendance():
    start = input("Date (YYYY-MM-DD, blank for today): ").strip() or date.today().isoformat()
    with connect() as con:
        rows = con.execute("""SELECT a.student_id,s.name,a.attendance_date,a.attendance_time,a.record_hash
                              FROM attendance a JOIN students s ON s.student_id=a.student_id
                              WHERE a.attendance_date=? ORDER BY a.attendance_time""", (start,)).fetchall()
    print(f"\nAttendance for {start}")
    print("-" * 78)
    for sid, name, day, time, _ in rows:
        print(f"{sid:<15} {name:<25} {day} {time}")
    print(f"Total present: {len(rows)}")

def export_csv():
    filename = "attendance_export.csv"
    with connect() as con, open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["student_id", "name", "date", "time", "record_hash"])
        writer.writerows(con.execute("""SELECT a.student_id,s.name,a.attendance_date,
                                        a.attendance_time,a.record_hash
                                        FROM attendance a JOIN students s ON s.student_id=a.student_id
                                        ORDER BY a.attendance_date,a.attendance_time"""))
    print(f"Exported to {filename}")

def verify_hashes():
    errors = 0
    with connect() as con:
        rows = con.execute("SELECT student_id,attendance_date,attendance_time,record_hash FROM attendance").fetchall()
    for sid, day, time, stored in rows:
        if digest(f"{sid}|{day}|{time}") != stored:
            print(f"Hash mismatch: {sid} on {day} at {time}")
            errors += 1
    print("All attendance record hashes verified." if errors == 0 else f"{errors} record(s) failed verification.")

def main():
    init_db()
    while True:
        print("""
========================================
 FACE RECOGNITION ATTENDANCE DATABASE
========================================
1. Register student / capture face
2. Start face recognition & attendance
3. View registered students
4. View attendance report
5. Export attendance to CSV
6. Verify attendance record hashes
7. Retrain face model
0. Exit
""")
        choice = input("Choose an option: ").strip()
        if choice == "1": register_student()
        elif choice == "2": recognize_attendance()
        elif choice == "3": view_students()
        elif choice == "4": view_attendance()
        elif choice == "5": export_csv()
        elif choice == "6": verify_hashes()
        elif choice == "7": train_model()
        elif choice == "0":
            print("Goodbye!")
            break
        else: print("Invalid option. Try again.")

if __name__ == "__main__":
    main()
