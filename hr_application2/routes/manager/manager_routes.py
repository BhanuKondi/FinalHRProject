# routes/manager/manager_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models.db import db
from models.models import Employee, User, Role
from functools import wraps

manager_bp = Blueprint("manager", __name__, url_prefix="/manager")


# ---------------- Helper Function ----------------
def current_manager():
    """
    Returns the Employee object if the logged-in user is a manager.
    """
    user_id = session.get("user_id")
    if not user_id:
        return None

    # Join Employee -> User -> Role to ensure the user is a manager
    mgr = (
        Employee.query
        .join(User)
        .join(Role)
        .filter(Employee.user_id == user_id, Role.name == "manager")
        .first()
    )
    return mgr


# ---------------- Login Required Decorator ----------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "warning")
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated


# ---------------- Dashboard Route ----------------
@manager_bp.route("/dashboard")
@login_required
def dashboard():
    mgr = current_manager()
    if not mgr:
        flash("Access denied: Not a manager.", "danger")
        return redirect("/login")

    # Example: get team members (employees that have manager_emp_id == mgr.id)
    team = Employee.query.filter_by(manager_emp_id=mgr.id).all()

    return render_template("manager/dashboard.html", manager=mgr, team=team)


# ---------------- Profile Routes ----------------
@manager_bp.route("/profile")
@login_required
def profile():
    mgr = current_manager()
    if not mgr:
        flash("Access denied: Not a manager.", "danger")
        return redirect("/login")
    return render_template("manager/profile.html", manager=mgr)


@manager_bp.route("/profile/edit", methods=["POST"])
@login_required
def profile_edit():
    mgr = current_manager()
    if not mgr:
        flash("Access denied: Not a manager.", "danger")
        return redirect("/login")

    phone = request.form.get("phone")
    address = request.form.get("address")
    display_name = request.form.get("display_name")

    if phone:
        mgr.phone = phone
    if address:
        mgr.address = address
    if display_name:
        user = User.query.get(mgr.user_id)
        user.display_name = display_name

    db.session.commit()
    flash("Profile updated successfully.", "success")
    return redirect(url_for("manager.profile"))
