from flask import Blueprint, render_template, request, redirect, session, flash, url_for
from models.models import User
from models.db import db

auth_bp = Blueprint("auth", __name__)

# ------------------------- LOGIN -------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        # User not found or wrong password
        if not user or not user.check_password(password):
            flash("Invalid email or password", "danger")
            return redirect(url_for('auth.login'))

        # NEW: Check Terminated / Inactive
        if hasattr(user, "is_active") and not user.is_active:
            flash("Your account is disabled or terminated. Contact Admin.", "danger")
            return redirect(url_for('auth.login'))

        # Save session
        session['user_id'] = user.id
        session['email'] = user.email
        session['role_id'] = user.role_id

        # Force password change
        if user.must_change_password:
            flash("You must change your password before proceeding.", "warning")
            return redirect(url_for('settings.change_password'))

        # --------------------------
        #   ROLE-BASED REDIRECT
        # --------------------------
        role = user.role.name.lower()

        if role == "admin":
            return redirect("/admin/dashboard")

        elif role == "manager":
            return redirect("/manager/dashboard")

        # Default → Employee
        return redirect("/employee/dashboard")

    return render_template("login.html")


# ------------------------- LOGOUT -------------------------
@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
