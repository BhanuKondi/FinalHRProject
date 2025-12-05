# routes/admin_attendance.py
from flask import Blueprint, render_template, jsonify, request
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from models.models import User
from models.attendance import Attendance
from sqlalchemy import func, and_
from calendar import monthrange

admin_attendance_bp = Blueprint("admin_attendance_bp", __name__, url_prefix="/admin/attendance")
IST = ZoneInfo("Asia/Kolkata")

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
