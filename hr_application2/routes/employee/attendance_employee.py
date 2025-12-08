# routes/employee/attendance_employee.py
 
from flask import Blueprint, render_template, session, redirect, flash, url_for, jsonify
from models.models import Employee
from models.attendance import Attendance, IST
from models.db import db
from datetime import datetime, date
 
employee_attendance_bp = Blueprint(
    "employee_attendance_bp",
    __name__,
    url_prefix="/employee/attendance"
)
 
 
# --------------------------------------------------
# Helper: fetch logged-in employee
# --------------------------------------------------
def current_employee():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return Employee.query.filter_by(user_id=user_id).first()
 
 
# --------------------------------------------------
# Attendance UI Page (HTML)
# --------------------------------------------------
@employee_attendance_bp.route("/")
def attendance_page():
    emp = current_employee()
    if not emp:
        return redirect("/login")
 
    return render_template("employee/attendance.html", employee=emp)
 
 
# --------------------------------------------------
# API: Get employee’s own attendance list (JSON)
# --------------------------------------------------
@employee_attendance_bp.route("/list")
def attendance_list():
    emp = current_employee()
    if not emp:
        return jsonify([])
 
    logs = Attendance.query.filter_by(user_id=emp.user_id).order_by(Attendance.id.desc()).all()
 
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
# --------------------------------------------------
@employee_attendance_bp.route("/clock_in", methods=["POST"])
def clock_in():
    emp = current_employee()
    if not emp:
        return redirect("/login")
 
    today = date.today()
 
    # Count how many logs today
    record_count = Attendance.query.filter_by(user_id=emp.user_id, date=today).count()
 
    now = datetime.now(IST)
 
    new_log = Attendance(
        user_id=emp.user_id,
        transaction_no=record_count + 1,
        date=today,
        clock_in=now
    )
 
    db.session.add(new_log)
    db.session.commit()
 
    flash("Clock-in successful!", "success")
    return redirect(url_for("employee_attendance_bp.attendance_page"))
 
 
# --------------------------------------------------
# CLOCK-OUT
# --------------------------------------------------
@employee_attendance_bp.route("/clock_out/<int:log_id>", methods=["POST"])
def clock_out(log_id):
    emp = current_employee()
    if not emp:
        return redirect("/login")
 
    log = Attendance.query.get(log_id)
 
    if not log or log.user_id != emp.user_id:
        flash("Invalid attendance record.", "danger")
        return redirect(url_for("employee_attendance_bp.attendance_page"))
 
    if log.clock_out:
        flash("Already clocked out.", "warning")
        return redirect(url_for("employee_attendance_bp.attendance_page"))
 
    now = datetime.now(IST)
 
    log.finish(now)
    db.session.commit()
 
    flash("Clock-out successful!", "success")
    return redirect(url_for("employee_attendance_bp.attendance_page"))
 
 