from flask import Blueprint, request, jsonify
from models.models import Employee, User
from models.db import db
from functools import wraps

api_emp = Blueprint("api_emp", __name__, url_prefix="/api")

# =============================
#  SIMPLE BASIC AUTH (HARDCODED)
# =============================

API_USERNAME = "sailpoint"
API_PASSWORD = "HrApp@123"


def basic_auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization

        if not auth:
            return jsonify({"error": "Authentication required"}), 401

        if auth.username != API_USERNAME or auth.password != API_PASSWORD:
            return jsonify({"error": "Invalid credentials"}), 401

        return f(*args, **kwargs)

    return decorated


# =============================
#  SERIALIZER
# =============================

def serialize_employee(emp):
    return {
        "empCode": emp.emp_code,
        "firstName": emp.first_name,
        "lastName": emp.last_name,
        "email": emp.work_email,
        "phone": emp.phone,
        "department": emp.department,
        "jobTitle": emp.job_title,
        "address": emp.address,
        "dateOfJoining": str(emp.date_of_joining) if emp.date_of_joining else None,
        "status": emp.status,
        "managerEmpId": emp.manager_emp_id,
        "user": {
            "id": emp.user.id,
            "email": emp.user.email,
            "isActive": emp.user.is_active
        } if emp.user else None
    }


# =============================
#  1) GET ALL EMPLOYEES
# =============================

@api_emp.route("/employees", methods=["GET"])
@basic_auth_required
def api_get_all_employees():
    employees = Employee.query.all()
    data = [serialize_employee(e) for e in employees]

    return jsonify({
        "total": len(data),
        "data": data
    }), 200


# =============================
#  2) GET EMPLOYEE BY empCode
# =============================

@api_emp.route("/employee/<string:empCode>", methods=["GET"])
@basic_auth_required
def api_get_employee(empCode):
    emp = Employee.query.filter_by(emp_code=empCode).first()

    if not emp:
        return jsonify({"error": "Employee not found"}), 404

    return jsonify(serialize_employee(emp)), 200


# =============================
#  3) CREATE EMPLOYEE
# =============================

@api_emp.route("/employee", methods=["POST"])
@basic_auth_required
def api_create_employee():
    data = request.json

    required = ["firstName", "lastName", "email", "empCode"]
    missing = [f for f in required if f not in data]

    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    # Check duplicate empCode
    if Employee.query.filter_by(emp_code=data["empCode"]).first():
        return jsonify({"error": "empCode already exists"}), 400

    # Check duplicate email
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already exists"}), 400

    # Create User
    user = User(
        email=data["email"],
        display_name=f"{data['firstName']} {data['lastName']}",
        role_id=3,
        is_active=True
    )
    user.set_password("Temp@123")

    db.session.add(user)
    db.session.commit()

    # Create Employee record
    emp = Employee(
        emp_code=data["empCode"],
        first_name=data["firstName"],
        last_name=data["lastName"],
        work_email=data["email"],
        phone=data.get("phone"),
        address=data.get("address"),
        date_of_joining=data.get("dateOfJoining"),
        department=data.get("department"),
        job_title=data.get("jobTitle"),
        status=data.get("status", "Active"),
        user_id=user.id,
        manager_emp_id=data.get("managerEmpId")
    )

    db.session.add(emp)
    db.session.commit()

    return jsonify({
        "message": "Employee created successfully",
        "employee": serialize_employee(emp)
    }), 201


# =============================
#  4) DELETE EMPLOYEE BY empCode
# =============================

@api_emp.route("/employee/<string:empCode>", methods=["DELETE"])
@basic_auth_required
def api_delete_employee(empCode):
    emp = Employee.query.filter_by(emp_code=empCode).first()

    if not emp:
        return jsonify({"error": "Employee not found"}), 404

    # Delete associated user
    if emp.user:
        db.session.delete(emp.user)

    db.session.delete(emp)
    db.session.commit()

    return jsonify({"message": "Employee deleted successfully"}), 200
