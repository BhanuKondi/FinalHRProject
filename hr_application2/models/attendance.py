from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from models.db import db

# Load IST timezone; fallback to UTC
try:
    IST = ZoneInfo("Asia/Kolkata")
except ZoneInfoNotFoundError:
    IST = ZoneInfo("UTC")


SHIFT_START_HOUR = 10  # 10 AM
SHIFT_END_HOUR = 6     # 6 AM next day

class Attendance(db.Model):
    __tablename__ = "attendance"
  
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    transaction_no = db.Column(db.Integer, nullable=False)

    clock_in = db.Column(db.DateTime(timezone=True), nullable=False)
    clock_out = db.Column(db.DateTime(timezone=True), nullable=True)

    duration_seconds = db.Column(db.Integer, nullable=True)

    date = db.Column(db.Date, nullable=False)

    # New fields for shift boundaries
    shift_start = db.Column(db.DateTime(timezone=True), nullable=False)
    shift_end = db.Column(db.DateTime(timezone=True), nullable=False)

    def finish(self, out_time):
        """
        Complete the attendance by setting clock_out and computing duration.
        """
        self.clock_out = out_time

        if self.clock_in and self.clock_out:
            delta = (self.clock_out - self.clock_in).total_seconds()
            self.duration_seconds = int(delta) if delta > 0 else 0
        else:
            self.duration_seconds = 0

    @staticmethod
    def get_shift_datetime(now: datetime):
        """
        Return shift_start and shift_end datetime for the given timestamp.
        Handles 10 AM → 6 AM next day shift.
        """
        shift_start_dt = now.replace(hour=SHIFT_START_HOUR, minute=0, second=0, microsecond=0)
        if now.hour < SHIFT_END_HOUR:  # Early morning → belongs to previous day's shift
            shift_start_dt -= timedelta(days=1)
        shift_end_dt = shift_start_dt + timedelta(hours=20)  # 10 AM → 6 AM next day
        return shift_start_dt, shift_end_dt

    @staticmethod
    def get_shift_date(now: datetime):
        """
        Return the date that represents the shift for this timestamp.
        """
        if now.hour < SHIFT_END_HOUR:
            return (now - timedelta(days=1)).date()
        return now.date()
