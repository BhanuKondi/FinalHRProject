from flask import Blueprint, jsonify, session
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from models.db import db
from models.attendance import Attendance

attendance_bp = Blueprint("attendance_bp", __name__, url_prefix="/attendance")

IST = ZoneInfo("Asia/Kolkata")
SHIFT_START_HOUR = 10  # 10 AM
SHIFT_END_HOUR = 6     # 6 AM next day

# ---------------------- Helper Functions ----------------------

def get_shift_date(now):
    """
    Returns the shift date for a timestamp considering 10AM - 6AM shift
    """
    if now.hour < SHIFT_END_HOUR:  # 12 AM - 5:59 AM → previous day's shift
        shift_day = (now - timedelta(days=1)).date()
    else:
        shift_day = now.date()
    return shift_day

def auto_close_previous(user_id):
    """
    Automatically closes any previous open attendance record
    """
    record = Attendance.query.filter_by(user_id=user_id, clock_out=None).first()
    if record:
        now = datetime.now(IST)
        ci = record.clock_in.replace(tzinfo=None)
        co = now.replace(tzinfo=None)
        record.clock_out = now
        record.duration_seconds = int((co - ci).total_seconds())
        db.session.commit()

# ---------------------- Routes ----------------------

@attendance_bp.route("/clock_in", methods=["POST"])
def clock_in():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Login required"}), 401

    auto_close_previous(user_id)

    now = datetime.now(IST)
    shift_day = get_shift_date(now)

    # Shift start/end datetime
    shift_start_dt = now.replace(hour=SHIFT_START_HOUR, minute=0, second=0, microsecond=0)
    if now.hour < SHIFT_END_HOUR:
        shift_start_dt -= timedelta(days=1)
    shift_end_dt = shift_start_dt + timedelta(hours=20)  # 10 AM → 6 AM next day

    # Determine next transaction number
    last_txn = Attendance.query.filter_by(user_id=user_id, date=shift_day)\
        .order_by(Attendance.transaction_no.desc()).first()
    next_txn = (last_txn.transaction_no + 1) if last_txn else 1

    attendance = Attendance(
        user_id=user_id,
        transaction_no=next_txn,
        clock_in=now,
        date=shift_day,
        shift_start=shift_start_dt,
        shift_end=shift_end_dt
    )

    db.session.add(attendance)
    db.session.commit()

    return jsonify({"message": "Clocked In", "transaction_no": next_txn})

@attendance_bp.route("/clock_out", methods=["POST"])
def clock_out():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Login required"}), 401

    open_record = Attendance.query.filter_by(user_id=user_id, clock_out=None).first()
    if not open_record:
        return jsonify({"error": "No active session"}), 400

    now = datetime.now(IST)
    ci = open_record.clock_in.replace(tzinfo=None)
    co = now.replace(tzinfo=None)

    open_record.clock_out = now
    open_record.duration_seconds = int((co - ci).total_seconds())
    db.session.commit()

    return jsonify({
        "message": "Clocked Out",
        "duration": open_record.duration_seconds,
        "clock_out": now.strftime("%d/%m/%Y, %I:%M:%S %p"),
        "transaction_no": open_record.transaction_no,
    })

@attendance_bp.route("/status", methods=["GET"])
def status():
    user_id = session.get("user_id")
    open_record = Attendance.query.filter_by(user_id=user_id, clock_out=None).first()
    return jsonify({"active": True if open_record else False})

@attendance_bp.route("/current", methods=["GET"])
def current_session():
    user_id = session.get("user_id")
    record = Attendance.query.filter_by(user_id=user_id, clock_out=None).first()
    if not record:
        return jsonify({"active": False})

    return jsonify({
        "active": True,
        "clock_in": record.clock_in.isoformat(),
        "shift_start": record.shift_start.isoformat(),
        "shift_end": record.shift_end.isoformat()
    })

@attendance_bp.route("/today-summary", methods=["GET"])
def today_summary():
    user_id = session.get("user_id")
    now = datetime.now(IST)
    shift_day = get_shift_date(now)

    records = Attendance.query.filter_by(user_id=user_id, date=shift_day)\
        .order_by(Attendance.transaction_no).all()
    total_seconds = sum(r.duration_seconds or 0 for r in records)

    hrs = total_seconds // 3600
    mins = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    formatted = f"{hrs:02}:{mins:02}:{secs:02}"

    transactions = [{
        "transaction_no": r.transaction_no,
        "clock_in": r.clock_in.strftime("%d/%m/%Y, %I:%M:%S %p"),
        "clock_out": r.clock_out.strftime("%d/%m/%Y, %I:%M:%S %p") if r.clock_out else "-",
        "duration": r.duration_seconds if r.duration_seconds else "-",
        "shift_start": r.shift_start.strftime("%d/%m/%Y, %I:%M:%S %p"),
        "shift_end": r.shift_end.strftime("%d/%m/%Y, %I:%M:%S %p")
    } for r in records]

    return jsonify({
        "worked": formatted,
        "total_seconds": total_seconds,
        "transactions": transactions,
    })
