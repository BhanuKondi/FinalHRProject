from flask import Blueprint, render_template, request, session, redirect, flash, url_for
from models.models import User
from models.db import db

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")

@settings_bp.route("/change_password", methods=["GET", "POST"])
def change_password():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    user = User.query.get(user_id)

    if request.method == "POST":
        new_password = request.form.get("new_password")

        if not new_password or len(new_password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return redirect(url_for("settings.change_password"))

        user.set_password(new_password)
        user.must_change_password = False
        db.session.commit()
        flash("Password updated successfully.", "success")

        # Redirect based on role
        if user.role.name.lower() == "admin":
            return redirect(url_for("admin.dashboard"))
        else:
            return redirect("/employee/dashboard")

    return render_template("change_password.html", user=user)
