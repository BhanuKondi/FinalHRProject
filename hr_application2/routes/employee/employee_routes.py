from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models.db import db
from models.models import Employee, User, Leave, LeaveType
from models.attendance import Attendance, IST
from datetime import datetime, date
from functools import wraps
import uuid

employee_bp = Blueprint("employee", __name__, url_prefix="/employee")

# ------------------------ Helper: Get logged-in employee ------------------------
def current_employee():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return Employee.query.filter_by(user_id=user_id).first()

# ------------------------ Login Required Decorator ------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "warning")
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

# ------------------------ Dashboard ------------------------
@employee_bp.route("/dashboard")
@login_required
def dashboard():
    emp = current_employee()
    return render_template("employee/dashboard.html", employee=emp)

# ------------------------ Profile ------------------------
@employee_bp.route("/profile", methods=["GET"])
@login_required
def profile():
    emp = current_employee()
    return render_template("employee/profile.html", employee=emp)

@employee_bp.route("/profile/edit", methods=["POST"])
@login_required
def profile_edit():
    emp = current_employee()

    phone = request.form.get("phone")
    address = request.form.get("address")
    display_name = request.form.get("display_name")

    if phone:
        emp.phone = phone
    if address:
        emp.address = address
    if display_name:
        user = User.query.get(emp.user_id)
        user.display_name = display_name

    db.session.commit()
    flash("Profile updated successfully.", "success")
    return redirect(url_for("employee.profile"))

# ------------------------ Leave Management ------------------------
@employee_bp.route("/leave_management")
@login_required
def leave_management():
    emp = current_employee()
    if not emp:
        return redirect("/login")

    allocated = getattr(emp, "allocated_leaves", 12)

    # All leave types
    leave_types = LeaveType.query.all()
    # All leaves of employee
    leaves = Leave.query.filter_by(employee_id=emp.id).order_by(Leave.submitted_at.desc()).all()

    # Determine if "Track Leave Requests" should be shown
    show_track = request.args.get("show_track", "False") == "True"

    return render_template(
        "employee/leave_management.html",
        employee=emp,
        allocated=allocated,
        leave_types=leave_types,
        leaves=leaves,
        show_track=show_track
    )

@employee_bp.route("/leave_management/apply", methods=["POST"])
@login_required
def leave_apply():
    emp = current_employee()
    if not emp:
        return redirect("/login")

    leave_type_id = request.form.get("leave_type_id")
    start_date_str = request.form.get("start_date")
    end_date_str = request.form.get("end_date")
    reason = request.form.get("reason")

    if not all([leave_type_id, start_date_str, end_date_str, reason]):
        flash("All fields are required.", "danger")
        return redirect(url_for("employee.leave_management"))

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid date format. Use YYYY-MM-DD.", "danger")
        return redirect(url_for("employee.leave_management"))

    if start_date > end_date:
        flash("End date cannot be before start date.", "danger")
        return redirect(url_for("employee.leave_management"))

    # Calculate days count (full days only)
    days_count = (end_date - start_date).days + 1

    new_leave = Leave(
        leave_uid=str(uuid.uuid4()),
        employee_id=emp.id,
        leave_type_id=leave_type_id,
        start_date=start_date,
        end_date=end_date,
        days_count=days_count,
        reason=reason,
        status="Pending_L1",
        submitted_at=datetime.utcnow()
    )

    db.session.add(new_leave)
    db.session.commit()

    flash("Leave request submitted successfully.", "success")
    # Redirect to leave management and show track section
    return redirect(url_for("employee.leave_management", show_track="True"))

# ------------------------ Attendance ------------------------
@employee_bp.route("/attendance")
@login_required
def attendance_page():
    emp = current_employee()
    logs = Attendance.query.filter_by(user_id=emp.user_id).order_by(Attendance.id.desc()).all()
    return render_template("employee/attendance.html", employee=emp, logs=logs)

@employee_bp.route("/attendance/clock_in", methods=["POST"])
@login_required
def clock_in():
    emp = current_employee()
    today = date.today()

    count_today = Attendance.query.filter_by(user_id=emp.user_id, date=today).count()
    now = datetime.now(IST)

    new_log = Attendance(
        user_id=emp.user_id,
        date=today,
        transaction_no=count_today + 1,
        clock_in=now
    )

    db.session.add(new_log)
    db.session.commit()

    flash("Clock-in successful.", "success")
    return redirect(url_for("employee.attendance_page"))

@employee_bp.route("/attendance/clock_out/<int:log_id>", methods=["POST"])
@login_required
def clock_out(log_id):
    emp = current_employee()
    log = Attendance.query.get(log_id)

    if not log or log.user_id != emp.user_id:
        flash("Invalid request.", "danger")
        return redirect(url_for("employee.attendance_page"))

    if log.clock_out:
        flash("Already clocked out.", "warning")
        return redirect(url_for("employee.attendance_page"))

    now = datetime.now(IST)
    log.finish(now)

    db.session.commit()
    flash("Clock-out successful.", "success")
    return redirect(url_for("employee.attendance_page"))
