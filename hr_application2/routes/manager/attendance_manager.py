from flask import Blueprint, render_template, session, redirect, jsonify
from models.models import Employee
from models.attendance import Attendance, IST
from models.db import db
from datetime import datetime, date

manager_attendance_bp = Blueprint(
    "manager_attendance_bp",
    __name__,
    url_prefix="/manager/attendance"
)

# --------------------------------------------------
# Helper: fetch logged-in manager
# --------------------------------------------------
def current_manager():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return Employee.query.filter_by(user_id=user_id).first()


# --------------------------------------------------
# Attendance UI Page (HTML)
# --------------------------------------------------
@manager_attendance_bp.route("/")
def attendance_page():
    mgr = current_manager()
    if not mgr:
        return redirect("/login")

    return render_template("manager/attendance.html", manager=mgr)


# --------------------------------------------------
# List All Attendance Logs (JSON)
# --------------------------------------------------
@manager_attendance_bp.route("/list")
def attendance_list():
    mgr = current_manager()
    if not mgr:
        return jsonify([])

    logs = Attendance.query.filter_by(user_id=mgr.user_id).order_by(Attendance.id.desc()).all()

    result = [
        {
            "id": log.id,
            "transaction_no": log.transaction_no,
            "date": log.date.strftime("%d-%m-%Y"),
            "clock_in": log.clock_in.strftime("%I:%M:%S %p"),
            "clock_out": log.clock_out.strftime("%I:%M:%S %p") if log.clock_out else "-",
            "worked": (
                f"{log.duration_seconds // 3600:02}:"
                f"{(log.duration_seconds % 3600) // 60:02}:"
                f"{log.duration_seconds % 60:02}"
                if log.duration_seconds else "00:00:00"
            )
        }
        for log in logs
    ]

    return jsonify(result)


# --------------------------------------------------
# CLOCK-IN
@manager_attendance_bp.route("/clock_in", methods=["POST"])
def clock_in():
    mgr = current_manager()
    if not mgr:
        return jsonify({"error": "Not logged in"}), 401

    today = date.today()

    # Count today's records
    record_count = Attendance.query.filter_by(user_id=mgr.user_id, date=today).count()

    now = datetime.now(IST)

    # Calculate shift start/end using the helper
    shift_start_dt, shift_end_dt = Attendance.get_shift_datetime(now)

    new_log = Attendance(
        user_id=mgr.user_id,
        transaction_no=record_count + 1,
        date=today,
        clock_in=now,
        shift_start=shift_start_dt,
        shift_end=shift_end_dt
    )

    db.session.add(new_log)
    db.session.commit()

    return jsonify({"success": True, "message": "Clock-in successful"})


# --------------------------------------------------
# CLOCK-OUT
# --------------------------------------------------
@manager_attendance_bp.route("/clock_out/<int:log_id>", methods=["POST"])
def clock_out(log_id):
    mgr = current_manager()
    if not mgr:
        return jsonify({"error": "Not logged in"}), 401

    log = Attendance.query.get(log_id)

    if not log or log.user_id != mgr.user_id:
        return jsonify({"error": "Invalid attendance record"}), 400

    if log.clock_out:
        return jsonify({"error": "Already clocked out"}), 400

    now = datetime.now(IST)

    # ---------------- SHIFT VALIDATION ----------------
    if log.shift_start:
        if now < log.shift_start:
            return jsonify({
                "error": "Clock-out not allowed before shift start time"
            }), 400

    # Allow clock-out anytime after shift start
    log.finish(now)
    db.session.commit()

    return jsonify({"success": True, "message": "Clock-out successful"})
# --------------------------------------------------
# Active Session Check (JSON)
# --------------------------------------------------
@manager_attendance_bp.route("/current")
def current_session():
    mgr = current_manager()
    if not mgr:
        return jsonify({"active": False})

    today = date.today()

    log = Attendance.query.filter_by(
        user_id=mgr.user_id, date=today, clock_out=None
    ).order_by(Attendance.id.desc()).first()

    if log:
        return jsonify({
            "active": True,
            "clock_in": log.clock_in.isoformat(),
            "log_id": log.id
        })

    return jsonify({"active": False})


# --------------------------------------------------
# TODAY SUMMARY
# --------------------------------------------------
@manager_attendance_bp.route("/today-summary")
def today_summary():
    mgr = current_manager()
    if not mgr:
        return jsonify({"total_seconds": 0, "transactions": []})

    today = date.today()

    logs = Attendance.query.filter_by(user_id=mgr.user_id, date=today).order_by(Attendance.id.asc()).all()

    total_seconds = sum(log.duration_seconds or 0 for log in logs)

    transactions = [
        {
            "transaction_no": log.transaction_no,
            "clock_in": log.clock_in.strftime("%I:%M:%S %p"),
            "clock_out": log.clock_out.strftime("%I:%M:%S %p") if log.clock_out else "-",
            "duration": log.duration_seconds or 0
        }
        for log in logs
    ]

    return jsonify({
        "total_seconds": total_seconds,
        "transactions": transactions
    })
