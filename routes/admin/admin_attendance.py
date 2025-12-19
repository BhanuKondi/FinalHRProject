# routes/admin_attendance.py
'''from flask import Blueprint, render_template, jsonify, request
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from models.models import User,Leavee
from models.attendance import Attendance
from sqlalchemy import func, and_
from calendar import monthrange
import io
import csv
from flask import Response

admin_attendance_bp = Blueprint("admin_attendance_bp", __name__, url_prefix="/admin/attendance")
IST = ZoneInfo("Asia/Kolkata")
@admin_attendance_bp.route("/reports")
def attendance_reports_page():
    return render_template("admin/reports.html")
# Helper: format seconds to HH:MM:SS
def fmt_seconds(sec):
    sec = int(sec or 0)
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02}:{m:02}:{s:02}"

@admin_attendance_bp.route("/")
def attendance_page():
    return render_template("admin/attendance_list.html")

@admin_attendance_bp.route("/list_today")
def list_today():
    """Return JSON: one row per user for today's attendance"""
    today = datetime.now(IST).date()
    users = User.query.order_by(User.display_name).all()
    result = []

    for u in users:
        records = Attendance.query.filter_by(user_id=u.id, date=today).order_by(Attendance.clock_in).all()

        if not records:
            result.append({
                "user_id": u.id,
                "name": u.display_name,
                "date": str(today),
                "clock_in": "-",
                "clock_out": "-",
                "worked": "00:00:00",
                "status": "No Activity",
                "first_in_iso": None,
                "last_out_iso": None
            })
            continue

        # first in (earliest clock_in)
        first_in = min((r.clock_in for r in records if r.clock_in), default=None)
        # last out (latest clock_out) - can be None if user still active
        last_out_candidates = [r.clock_out for r in records if r.clock_out]
        last_out = max(last_out_candidates) if last_out_candidates else None

        total_seconds = sum((r.duration_seconds or 0) for r in records)
        status = "Active" if any(r.clock_out is None for r in records) else "Completed"

        result.append({
            "user_id": u.id,
            "name": u.display_name,
            "date": str(today),
            "clock_in": first_in.strftime("%I:%M:%S %p") if first_in else "-",
            "clock_out": last_out.strftime("%I:%M:%S %p") if last_out else "-",
            "worked": fmt_seconds(total_seconds),
            "status": status,
            "first_in_iso": first_in.isoformat() if first_in else None,
            "last_out_iso": last_out.isoformat() if last_out else None
        })

    return jsonify(result)

@admin_attendance_bp.route("/list_history")
def list_history():
    """
    Return JSON list of historical attendance summary rows.
    Optional query params:
      start_date=YYYY-MM-DD, end_date=YYYY-MM-DD
    By default returns last 30 days.
    """
    q = request.args
    try:
        if q.get("start_date"):
            start_date = datetime.fromisoformat(q.get("start_date")).date()
        else:
            start_date = (datetime.now(IST).date() - timedelta(days=30))
        if q.get("end_date"):
            end_date = datetime.fromisoformat(q.get("end_date")).date()
        else:
            end_date = datetime.now(IST).date()
    except Exception:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

    # Query attendance grouped by date & user: compute first_in, last_out, total_seconds, status
    rows = []
    # fetch records in date range, ordered
    records = Attendance.query.filter(and_(Attendance.date >= start_date, Attendance.date <= end_date)).order_by(Attendance.date.desc(), Attendance.user_id).all()

    # group in memory (safe for moderate data). If large, implement DB group queries.
    grouped = {}
    for r in records:
        key = (r.date, r.user_id)
        grouped.setdefault(key, []).append(r)

    for (rdate, uid), recs in sorted(grouped.items(), reverse=True):
        user = User.query.get(uid)
        first_in = min((x.clock_in for x in recs if x.clock_in), default=None)
        last_out_candidates = [x.clock_out for x in recs if x.clock_out]
        last_out = max(last_out_candidates) if last_out_candidates else None
        total_seconds = sum((x.duration_seconds or 0) for x in recs)
        status = "Active" if any(x.clock_out is None for x in recs) else "Completed"

        rows.append({
            "date": rdate.isoformat(),
            "user_id": uid,
            "name": user.display_name if user else "Unknown",
            "clock_in": first_in.strftime("%I:%M:%S %p") if first_in else "-",
            "clock_out": last_out.strftime("%I:%M:%S %p") if last_out else "-",
            "worked": fmt_seconds(total_seconds),
            "status": status
        })

    # Also include users with no activity on a date? Usually we omit absent rows here;
    # the frontend can show absence based on missing entries for a date.
    return jsonify(rows)

@admin_attendance_bp.route("/transactions/<int:user_id>")
def attendance_transactions(user_id):
    """
    /admin/attendance/transactions/<user_id>?date=YYYY-MM-DD
    Returns all transactions for that user & date. Default = today
    """
    date_str = request.args.get("date")
    if date_str:
        try:
            the_date = datetime.fromisoformat(date_str).date()
        except Exception:
            return jsonify({"error": "Invalid date format"}), 400
    else:
        the_date = datetime.now(IST).date()

    records = Attendance.query.filter_by(user_id=user_id, date=the_date).order_by(Attendance.clock_in).all()
    txns = []
    for r in records:
        txns.append({
            "transaction_no": r.transaction_no,
            "clock_in": r.clock_in.strftime("%I:%M:%S %p") if r.clock_in else "-",
            "clock_out": r.clock_out.strftime("%I:%M:%S %p") if r.clock_out else "-",
            "duration": fmt_seconds(r.duration_seconds or 0)
        })

    # last record summary
    last_record = None
    if records:
        latest = records[-1]
        last_record = {
            "clock_in": latest.clock_in.strftime("%I:%M:%S %p") if latest.clock_in else "-",
            "clock_out": latest.clock_out.strftime("%I:%M:%S %p") if latest.clock_out else "-",
            "worked": fmt_seconds(sum((x.duration_seconds or 0) for x in records)),
            "status": "Active" if any(x.clock_out is None for x in records) else "Completed"
        }

    return jsonify({"date": str(the_date), "transactions": txns, "last_record": last_record})

@admin_attendance_bp.route("/monthly/<int:user_id>/<int:year>/<int:month>")
def monthly_summary(user_id, year, month):
    """
    Return monthly summary for the user for given year and month.
    Computes days present (days with at least one record), days in month, total worked seconds,
    average hours, late days (first_in after office start), early leaves (last_out before office end).
    """
    # config: office start & end for late/early checks
    OFFICE_START = time(9, 30)   # 09:30 as example (adjust if needed)
    OFFICE_END = time(17, 30)    # 17:30 as example

    try:
        _, days_in_month = monthrange(year, month)
    except Exception:
        return jsonify({"error": "Invalid year/month"}), 400

    start_date = date(year, month, 1)
    end_date = date(year, month, days_in_month)

    # pull all attendance rows for that user in the month
    records = Attendance.query.filter(
        Attendance.user_id == user_id,
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).order_by(Attendance.date, Attendance.clock_in).all()

    # group by date
    grouped = {}
    for r in records:
        grouped.setdefault(r.date, []).append(r)

    present_days = len(grouped)
    total_worked_seconds = sum((r.duration_seconds or 0) for r in records)

    late_days = 0
    early_leave_days = 0
    for d, recs in grouped.items():
        first_in = min((x.clock_in for x in recs if x.clock_in), default=None)
        last_out_candidates = [x.clock_out for x in recs if x.clock_out]
        last_out = max(last_out_candidates) if last_out_candidates else None
        if first_in and first_in.timetz().replace(tzinfo=None) > OFFICE_START:
            late_days += 1
        if last_out and last_out.timetz().replace(tzinfo=None) < OFFICE_END:
            early_leave_days += 1

    total_days = days_in_month
    absent_days = total_days - present_days
    avg_daily_seconds = (total_worked_seconds / present_days) if present_days else 0

    return jsonify({
        "user_id": user_id,
        "year": year,
        "month": month,
        "days_in_month": total_days,
        "present_days": present_days,
        "absent_days": absent_days,
        "total_worked": fmt_seconds(total_worked_seconds),
        "avg_daily": fmt_seconds(int(avg_daily_seconds)),
        "late_days": late_days,
        "early_leaves": early_leave_days
    })
@admin_attendance_bp.route("/list_all_employees/<date_str>")
def list_all_employees(date_str):
    """
    Returns JSON for all employees on the given date.
    Shows clock_in, clock_out, total worked; absent = 0 hrs (ABSENT)
    """
    try:
        the_date = datetime.fromisoformat(date_str).date()
    except Exception:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

    users = User.query.order_by(User.display_name).all()
    result = []

    for u in users:
        records = Attendance.query.filter_by(user_id=u.id, date=the_date).order_by(Attendance.clock_in).all()

        if not records:
            result.append({
                "name": u.display_name,
                "clock_in": "-",
                "clock_out": "-",
                "worked": "0:00:00 (ABSENT)"
            })
            continue

        first_in = min((r.clock_in for r in records if r.clock_in), default=None)
        last_out_candidates = [r.clock_out for r in records if r.clock_out]
        last_out = max(last_out_candidates) if last_out_candidates else None

        total_seconds = sum((r.duration_seconds or 0) for r in records)

        if total_seconds:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            worked_display = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
        else:
            worked_display = "0:00:00 (ABSENT)"

        result.append({
            "name": u.display_name,
            "clock_in": first_in.strftime("%H:%M:%S") if first_in else "-",
            "clock_out": last_out.strftime("%H:%M:%S") if last_out else "-",
            "worked": worked_display
        })

    return jsonify(result)
@admin_attendance_bp.route("/reports/download_summary")
def download_monthly_attendance_summary_csv():
    month_str = request.args.get("month")  # format: YYYY-MM
    if not month_str:
        return jsonify({"error": "month parameter required"}), 400
 
    try:
        year, month = map(int, month_str.split("-"))
    except Exception:
        return jsonify({"error": "Invalid month format. Use YYYY-MM"}), 400
 
    from calendar import monthrange
    _, days_in_month = monthrange(year, month)
    start_date = date(year, month, 1)
 
    # Prepare list of weekdays (Mon-Fri)
    weekdays = [start_date + timedelta(days=i) for i in range(days_in_month)
                if (start_date + timedelta(days=i)).weekday() < 5]
 
    users = User.query.order_by(User.display_name).all()
 
    # In-memory CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Employee",
        "Total Working Days",
        "Days Present",
        "Leaves Applied",
        "Worked Hours",
        "Status"
    ])
 
    for u in users:
        if not u.employee:
            continue  # Skip users without employee records
 
        total_working_days = len(weekdays)
        days_present = 0
        leaves_applied = 0
        total_worked_seconds = 0
 
        for day in weekdays:
            # Attendance records for this day
            records = Attendance.query.filter_by(user_id=u.id, date=day).all()
            day_seconds = sum((r.duration_seconds or 0) for r in records)
            total_worked_seconds += day_seconds
 
            # Check if present
            if day_seconds >= 6 * 3600:  # 6 hours
                days_present += 1
 
            # Check leave
            leave = Leavee.query.filter(
                Leavee.emp_code == u.employee.emp_code,
                Leavee.start_date <= day,
                Leavee.end_date >= day,
                Leavee.status == "Approved"
            ).first()
            if leave:
                leaves_applied += 1
 
        # Status: if total worked seconds in month ≥ 6 hours/day * total_working_days → PRESENT else ABSENT
        status = "PRESENT" if total_worked_seconds >= 6 * 3600 else "ABSENT"
 
        writer.writerow([
            u.display_name,
            total_working_days,
            days_present,
            leaves_applied,
            fmt_seconds(total_worked_seconds),
            status
        ])
 
    output.seek(0)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=attendance_summary_{month_str}.csv"})

'''
# routes/admin_attendance.py
 
from flask import Blueprint, render_template, jsonify, request, Response
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import calendar
import io
import csv
 
from sqlalchemy import func, and_, extract
 
from models.models import (
    User,
    Employee,
    Leavee,
    Holiday,
    db
)
from models.attendance import Attendance
 
 
admin_attendance_bp = Blueprint(
    "admin_attendance_bp",
    __name__,
    url_prefix="/admin/attendance"
)
 
IST = ZoneInfo("Asia/Kolkata")
 
 
@admin_attendance_bp.route("/reports")
def attendance_reports_page():
    return render_template("admin/reports.html")
 
 
# -------------------------------
# Helper
# -------------------------------
def fmt_seconds(sec):
    sec = int(sec or 0)
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02}:{m:02}:{s:02}"
 
 
@admin_attendance_bp.route("/")
def attendance_page():
    return render_template("admin/attendance_list.html")
 
 
# -------------------------------
# Today attendance
# -------------------------------
@admin_attendance_bp.route("/list_today")
def list_today():
    today = datetime.now(IST).date()
    users = User.query.order_by(User.display_name).all()
    result = []
 
    for u in users:
        records = Attendance.query.filter_by(
            user_id=u.id,
            date=today
        ).order_by(Attendance.clock_in).all()
 
        if not records:
            result.append({
                "user_id": u.id,
                "name": u.display_name,
                "date": str(today),
                "clock_in": "-",
                "clock_out": "-",
                "worked": "00:00:00",
                "status": "No Activity",
                "first_in_iso": None,
                "last_out_iso": None
            })
            continue
 
        first_in = min((r.clock_in for r in records if r.clock_in), default=None)
        last_outs = [r.clock_out for r in records if r.clock_out]
        last_out = max(last_outs) if last_outs else None
 
        total_seconds = sum((r.duration_seconds or 0) for r in records)
        status = "Active" if any(r.clock_out is None for r in records) else "Completed"
 
        result.append({
            "user_id": u.id,
            "name": u.display_name,
            "date": str(today),
            "clock_in": first_in.strftime("%I:%M:%S %p") if first_in else "-",
            "clock_out": last_out.strftime("%I:%M:%S %p") if last_out else "-",
            "worked": fmt_seconds(total_seconds),
            "status": status,
            "first_in_iso": first_in.isoformat() if first_in else None,
            "last_out_iso": last_out.isoformat() if last_out else None
        })
 
    return jsonify(result)
 
 
# -------------------------------
# Attendance history
# -------------------------------
@admin_attendance_bp.route("/list_history")
def list_history():
    q = request.args
    try:
        start_date = datetime.fromisoformat(q.get("start_date")).date() \
            if q.get("start_date") else datetime.now(IST).date() - timedelta(days=30)
        end_date = datetime.fromisoformat(q.get("end_date")).date() \
            if q.get("end_date") else datetime.now(IST).date()
    except Exception:
        return jsonify({"error": "Invalid date format"}), 400
 
    records = Attendance.query.filter(
        and_(
            Attendance.date >= start_date,
            Attendance.date <= end_date
        )
    ).order_by(
        Attendance.date.desc(),
        Attendance.user_id
    ).all()
 
    grouped = {}
    for r in records:
        grouped.setdefault((r.date, r.user_id), []).append(r)
 
    rows = []
    for (rdate, uid), recs in sorted(grouped.items(), reverse=True):
        user = User.query.get(uid)
 
        first_in = min((x.clock_in for x in recs if x.clock_in), default=None)
        last_outs = [x.clock_out for x in recs if x.clock_out]
        last_out = max(last_outs) if last_outs else None
 
        total_seconds = sum((x.duration_seconds or 0) for x in recs)
        status = "Active" if any(x.clock_out is None for x in recs) else "Completed"
 
        rows.append({
            "date": rdate.isoformat(),
            "user_id": uid,
            "name": user.display_name if user else "Unknown",
            "clock_in": first_in.strftime("%I:%M:%S %p") if first_in else "-",
            "clock_out": last_out.strftime("%I:%M:%S %p") if last_out else "-",
            "worked": fmt_seconds(total_seconds),
            "status": status
        })
 
    return jsonify(rows)
 
 
# -------------------------------
# Monthly summary
# -------------------------------
@admin_attendance_bp.route("/monthly/<int:user_id>/<int:year>/<int:month>")
def monthly_summary(user_id, year, month):
    OFFICE_START = time(9, 30)
    OFFICE_END = time(17, 30)
 
    try:
        _, days_in_month = calendar.monthrange(year, month)
    except Exception:
        return jsonify({"error": "Invalid year/month"}), 400
 
    start_date = date(year, month, 1)
    end_date = date(year, month, days_in_month)
 
    records = Attendance.query.filter(
        Attendance.user_id == user_id,
        Attendance.date.between(start_date, end_date)
    ).order_by(
        Attendance.date,
        Attendance.clock_in
    ).all()
 
    grouped = {}
    for r in records:
        grouped.setdefault(r.date, []).append(r)
 
    present_days = len(grouped)
    total_seconds = sum((r.duration_seconds or 0) for r in records)
 
    late_days = early_leave_days = 0
    for recs in grouped.values():
        first_in = min((x.clock_in for x in recs if x.clock_in), default=None)
        last_outs = [x.clock_out for x in recs if x.clock_out]
        last_out = max(last_outs) if last_outs else None
 
        if first_in and first_in.time() > OFFICE_START:
            late_days += 1
        if last_out and last_out.time() < OFFICE_END:
            early_leave_days += 1
 
    return jsonify({
        "user_id": user_id,
        "year": year,
        "month": month,
        "days_in_month": days_in_month,
        "present_days": present_days,
        "absent_days": days_in_month - present_days,
        "total_worked": fmt_seconds(total_seconds),
        "avg_daily": fmt_seconds(int(total_seconds / present_days)) if present_days else "00:00:00",
        "late_days": late_days,
        "early_leaves": early_leave_days
    })
 
# -------------------------------
# List all employees for a date
# -------------------------------
@admin_attendance_bp.route("/list_all_employees/<date_str>")
def list_all_employees(date_str):
    """
    Returns JSON for all employees on the given date.
    Shows clock_in, clock_out, total worked; absent = 0 hrs (ABSENT)
    """
    try:
        the_date = datetime.fromisoformat(date_str).date()
    except Exception:
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400
 
    users = User.query.order_by(User.display_name).all()
    result = []
 
    for u in users:
        records = Attendance.query.filter_by(user_id=u.id, date=the_date).order_by(Attendance.clock_in).all()
 
        if not records:
            result.append({
                "name": u.display_name,
                "clock_in": "-",
                "clock_out": "-",
                "worked": "0:00:00 (ABSENT)"
            })
            continue
 
        first_in = min((r.clock_in for r in records if r.clock_in), default=None)
        last_out_candidates = [r.clock_out for r in records if r.clock_out]
        last_out = max(last_out_candidates) if last_out_candidates else None
 
        total_seconds = sum((r.duration_seconds or 0) for r in records)
 
        if total_seconds:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            worked_display = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
        else:
            worked_display = "0:00:00 (ABSENT)"
 
        result.append({
            "name": u.display_name,
            "clock_in": first_in.strftime("%H:%M:%S") if first_in else "-",
            "clock_out": last_out.strftime("%H:%M:%S") if last_out else "-",
            "worked": worked_display
        })
 
    return jsonify(result)
 
# -------------------------------
# CSV download
# -------------------------------
@admin_attendance_bp.route("/reports/download_summary")
def download_monthly_attendance_summary_csv():
    month_str = request.args.get("month")
    if not month_str:
        return jsonify({"error": "month parameter required"}), 400
 
    year, month = map(int, month_str.split("-"))
 
    days_in_month = calendar.monthrange(year, month)[1]
    cal = calendar.Calendar()
 
    sundays = sum(
        1 for d in cal.itermonthdates(year, month)
        if d.month == month and d.weekday() == 6
    )
 
    holidays = Holiday.query.filter(
        extract("month", Holiday.date) == month,
        extract("year", Holiday.date) == year
    ).count()
 
    total_working_days = days_in_month - sundays - holidays
 
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Emp Code", "Employee Name",
        "Total Working Days",
        "Present Days", "Absent Days", "LWP Days"
    ])
 
    employees = Employee.query.filter_by(status="Active").all()
 
    for emp in employees:
        attendance_days = db.session.query(
            func.count(func.distinct(Attendance.date))
        ).filter(
            Attendance.user_id == emp.user_id,
            extract("month", Attendance.date) == month,
            extract("year", Attendance.date) == year,
            Attendance.duration_seconds >= 5
        ).scalar() or 0
 
        paid_leave_days = db.session.query(
            func.coalesce(func.sum(Leavee.total_days), 0)
        ).filter(
            Leavee.emp_code == emp.emp_code,
            Leavee.leave_type.in_(["Casual Leave", "Sick Leave"]),
            Leavee.status == "Approved",
            extract("month", Leavee.start_date) == month,
            extract("year", Leavee.start_date) == year
        ).scalar() or 0
 
        lwp_days = db.session.query(
            func.coalesce(func.sum(Leavee.total_days), 0)
        ).filter(
            Leavee.emp_code == emp.emp_code,
            Leavee.leave_type == "Leave Without Pay",
            Leavee.status == "Approved",
            extract("month", Leavee.start_date) == month,
            extract("year", Leavee.start_date) == year
        ).scalar() or 0
 
        present_days = int(attendance_days + paid_leave_days)
        absent_days = max(total_working_days - present_days - int(lwp_days), 0)
 
        writer.writerow([
            emp.emp_code,
            f"{emp.first_name} {emp.last_name}",
            total_working_days,
            present_days,
            absent_days,
            int(lwp_days)
        ])
 
    output.seek(0)
    return Response(
        output,
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            f"attachment; filename=attendance_summary_{month_str}.csv"
        }
    )
@admin_attendance_bp.route("/reports/monthly/json")
def get_monthly_attendance_summary_json():
    month_str = request.args.get("month")
    if not month_str:
        return jsonify([])
 
    year, month = map(int, month_str.split("-"))
 
    days_in_month = calendar.monthrange(year, month)[1]
    cal = calendar.Calendar()
 
    sundays = sum(
        1 for d in cal.itermonthdates(year, month)
        if d.month == month and d.weekday() == 6
    )
 
    holidays = Holiday.query.filter(
        extract("month", Holiday.date) == month,
        extract("year", Holiday.date) == year
    ).count()
 
    total_working_days = days_in_month - sundays - holidays
 
    employees = Employee.query.filter_by(status="Active").all()
    data = []
 
    for emp in employees:
        attendance_days = db.session.query(
            func.count(func.distinct(Attendance.date))
        ).filter(
            Attendance.user_id == emp.user_id,
            extract("month", Attendance.date) == month,
            extract("year", Attendance.date) == year,
            Attendance.duration_seconds >= 5
        ).scalar() or 0
 
        paid_leave_days = db.session.query(
            func.coalesce(func.sum(Leavee.total_days), 0)
        ).filter(
            Leavee.emp_code == emp.emp_code,
            Leavee.leave_type.in_(["Casual Leave", "Sick Leave"]),
            Leavee.status == "Approved",
            extract("month", Leavee.start_date) == month,
            extract("year", Leavee.start_date) == year
        ).scalar() or 0
 
        lwp_days = db.session.query(
            func.coalesce(func.sum(Leavee.total_days), 0)
        ).filter(
            Leavee.emp_code == emp.emp_code,
            Leavee.leave_type == "Leave Without Pay",
            Leavee.status == "Approved",
            extract("month", Leavee.start_date) == month,
            extract("year", Leavee.start_date) == year
        ).scalar() or 0
 
        present_days = int(attendance_days + paid_leave_days)
        absent_days = max(total_working_days - present_days - int(lwp_days), 0)
 
        data.append({
            "emp_code": emp.emp_code,
            "employee_name": f"{emp.first_name} {emp.last_name}",
            "total_working_days": total_working_days,
            "present_days": present_days,
            "absent_days": absent_days,
            "lwp_days": int(lwp_days)
        })
 
    return jsonify(data)