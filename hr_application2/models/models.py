from datetime import datetime
from .db import db
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.mysql import INTEGER, BIGINT, VARCHAR, TEXT
import uuid

# ------------------- Roles -------------------
class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(INTEGER, primary_key=True)
    name = db.Column(VARCHAR(100), unique=True, nullable=False)


# ------------------- Users -------------------
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(INTEGER, primary_key=True)
    email = db.Column(VARCHAR(255), unique=True, nullable=False)
    password_hash = db.Column(VARCHAR(255), nullable=False)
    display_name = db.Column(VARCHAR(255))

    role_id = db.Column(INTEGER, db.ForeignKey("roles.id"), nullable=False)
    role = db.relationship("Role")

    is_active = db.Column(db.Boolean, default=True)
    must_change_password = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)

    # 1-to-1 Employee Profile
    employee = db.relationship("Employee", back_populates="user", uselist=False)

    # 👇 ADD THIS: Link Attendance to User
    attendance_records = db.relationship("Attendance", backref="user", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# ------------------- Employees -------------------
class Employee(db.Model):
    __tablename__ = "employees"
    id = db.Column(INTEGER, primary_key=True)
    emp_code = db.Column(VARCHAR(50), unique=True, nullable=False)

    user_id = db.Column(INTEGER, db.ForeignKey("users.id"))
    user = db.relationship("User", back_populates="employee")

    first_name = db.Column(VARCHAR(100), nullable=False)
    last_name = db.Column(VARCHAR(100), nullable=False)
    work_email = db.Column(VARCHAR(255), unique=True, nullable=False)
    phone = db.Column(VARCHAR(20))
    address = db.Column(TEXT)
    date_of_joining = db.Column(db.Date, nullable=False)

    manager_emp_id = db.Column(INTEGER, db.ForeignKey("employees.id"))
    manager = db.relationship(
    "Employee",
    remote_side=[id],
    backref="team_members"
)

    status = db.Column(VARCHAR(50), default="Active")
    department = db.Column(VARCHAR(100))
    job_title = db.Column(VARCHAR(100))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 👇 OPTIONAL — only if you want attendance per employee also
    #attendance_records = db.relationship("Attendance", backref="employee", lazy=True)


# ------------------- Leave Types -------------------
class LeaveType(db.Model):
    __tablename__ = "leave_types"
    id = db.Column(INTEGER, primary_key=True, autoincrement=True)
    code = db.Column(VARCHAR(50), unique=True, nullable=False)
    name = db.Column(VARCHAR(100), nullable=False)
    description = db.Column(TEXT)
    default_days_per_year = db.Column(INTEGER)

    


# ------------------- Leaves -------------------
class Leave(db.Model):
    __tablename__ = "leaves"

    id = db.Column(db.Integer, primary_key=True)
    emp_code = db.Column(db.String(50), db.ForeignKey("employees.emp_code"), nullable=False)

    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    total_days = db.Column(db.Integer)
    reason = db.Column(db.String(200))
    status = db.Column(db.String(20), default="Pending")
    decision_date = db.Column(db.DateTime)

    employee = db.relationship("Employee", backref="leaves", foreign_keys=[emp_code])

class Holiday(db.Model):
    __tablename__ = "holidays" 
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    day = db.Column(db.String(20))
    occasion = db.Column(db.String(100))
class LeaveSummary(db.Model):
    __tablename__ = "leave_summary"

    id = db.Column(db.Integer, primary_key=True)
    emp_code = db.Column(db.String(50), db.ForeignKey("employees.emp_code"), nullable=False)

    total_leaves = db.Column(db.Integer, default=24)
    consumed = db.Column(db.Integer, default=0)
    pending = db.Column(db.Integer, default=24)

    employee = db.relationship("Employee", backref="leave_summary", lazy=True)
class LeaveApprovalConfig(db.Model):
    __tablename__ = 'leave_approval_config'

    id = db.Column(db.Integer, primary_key=True)
    level1_approver_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    level2_approver_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    level1_approver = db.relationship("User", foreign_keys=[level1_approver_id])
    level2_approver = db.relationship("User", foreign_keys=[level2_approver_id])
class Leavee(db.Model):
    __tablename__ = 'employee_leaves'
    id = db.Column(db.Integer, primary_key=True)
    emp_code = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    total_days = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    employee_name=db.Column(db.String(45), nullable=False)
    status = db.Column(db.String(20), default="PENDING_L1")  # PENDING_L1, REJECTED_L1, PENDING_L2, APPROVED
    level1_approver_id = db.Column(db.Integer, nullable=True)
    level2_approver_id = db.Column(db.Integer, nullable=True)
    current_approver_id = db.Column(db.Integer, nullable=True)      # <-- NEW
    level1_decision_date = db.Column(db.DateTime, nullable=True)
    level2_decision_date = db.Column(db.DateTime, nullable=True)

from models.attendance import Attendance
