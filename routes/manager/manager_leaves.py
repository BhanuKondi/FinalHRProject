from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from models.models import Employee, Leave, User, Holiday, db,Leavee,LeaveApprovalConfig
from datetime import datetime

from flask import Blueprint, render_template, session, redirect, flash, url_for, jsonify
from models.models import Employee
from models.attendance import Attendance, IST
from models.db import db
from datetime import datetime, date
manager_lbp = Blueprint(
    "manager_leaves",
    __name__,
    url_prefix="/manager/leaves"
)
def current_employee():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return Employee.query.filter_by(user_id=user_id).first()
@manager_lbp.route("/leave-management")
def leave_management():
    emp = current_employee()
    if not emp:
        return redirect(url_for("auth.login"))

    holidays = Holiday.query.all()
    config = LeaveApprovalConfig.query.first()

    show_approvals_tab = False

    if config:

        # ---------------------------------------------------------
        # CASE 1: Fixed Level 1 Approver (NOT using manager)
        # ---------------------------------------------------------
        if not config.use_manager_l1 and config.level1_approver_id:
            if int(config.level1_approver_id) == emp.user_id:
                show_approvals_tab = True

        # ---------------------------------------------------------
        # CASE 2: Fixed Level 2 Approver
        # ---------------------------------------------------------
        if config.level2_approver_id:
            if int(config.level2_approver_id) == emp.user_id:
                show_approvals_tab = True

        # ---------------------------------------------------------
        # CASE 3: MANAGER-based L1 approver
        # ---------------------------------------------------------
        if config.use_manager_l1:
            # If this logged-in employee manages others
            managed_emps = Employee.query.filter_by(manager_emp_id=emp.id).all()
            if managed_emps:
                show_approvals_tab = True

    return render_template(
        "manager/leave_management.html",
        employee=emp,
        holidays=holidays,
        show_approvals_tab=show_approvals_tab
    )


@manager_lbp.route("/leave/submit", methods=["POST"])
def submit_leave():
    emp = current_employee()
    if not emp:
        return redirect(url_for("auth.login"))

    start = datetime.strptime(request.form['start_date'], "%Y-%m-%d").date()
    end = datetime.strptime(request.form['end_date'], "%Y-%m-%d").date()
    total_days = (end - start).days + 1

    config = LeaveApprovalConfig.query.first()

    # -----------------------------------------
    # 🔥 LEVEL 1 APPROVER LOGIC (UPDATED)
    # -----------------------------------------
    if config.use_manager_l1:
        # employee.manager is another Employee object
        if emp.manager:
            level1_approver_user_id = emp.manager.user_id
        else:
            flash("Manager not configured for your profile!", "danger")
            return redirect(url_for("employee_leaves.leave_management"))
    else:
        # Normal fixed user_id
        level1_approver_user_id = (
            int(config.level1_approver_id)
            if config.level1_approver_id else None
        )

    # -----------------------------------------
    # LEVEL 2 APPROVER (same as before)
    # -----------------------------------------
    level2_approver_user_id = (
        int(config.level2_approver_id)
        if config.level2_approver_id else None
    )

    # -----------------------------------------
    # CREATE LEAVE REQUEST
    # -----------------------------------------
    leave = Leavee(
        emp_code=emp.emp_code,
        start_date=start,
        end_date=end,
        total_days=total_days,
        reason=request.form['reason'],
        employee_name=request.form['employee_name'],

        status="PENDING_L1",
        level1_approver_id=level1_approver_user_id,
        level2_approver_id=level2_approver_user_id,
        current_approver_id=level1_approver_user_id
    )

    db.session.add(leave)
    db.session.commit()

    flash("Leave request submitted!", "success")
    return redirect(url_for("manager_leaves.leave_management"))


@manager_lbp.route("/leave/my-requests")
def my_requests():
    emp = current_employee()
    leaves = Leavee.query.filter_by(emp_code=emp.emp_code).all()

    return jsonify([
        {
            "id": l.id,
            "start": l.start_date.strftime("%Y-%m-%d"),
            "end": l.end_date.strftime("%Y-%m-%d"),
            "days": l.total_days,
            "reason": l.reason,
            "status": l.status
        }
        for l in leaves
    ])
@manager_lbp.route("/leave/my-approvals")
def my_approvals():
    emp = current_employee()

    # Fetch approval config
    config = LeaveApprovalConfig.query.first()
    level1 = config.level1_approver_id
    level2 = config.level2_approver_id

    all_pending = Leavee.query.filter_by(current_approver_id=emp.user_id).all()

    final_list = []

    for l in all_pending:

        # --------------------------
        # RULE: SKIP SELF-APPROVAL
        # If employee is Level-1 approver AND leave belongs to him → skip
        # --------------------------
        if emp.user_id == level1 and l.emp_code == emp.emp_code:
            # Auto-route to Level2 instead of showing in L1 approvals
            l.current_approver_id = level2
            l.status = "PENDING_L2"
            db.session.commit()
            continue  # do NOT show in the list

        # If employee is Level2 approver AND request belongs to him → auto approve
        if emp.user_id == level2 and l.emp_code == emp.emp_code:
            l.status = "APPROVED"
            l.current_approver_id = None
            db.session.commit()
            continue  # do NOT show in approvals

        # Normal case → show in list
        final_list.append({
            "id": l.id,
            "emp_code": l.emp_code,
            "employee_name":l.employee_name,
            "start": l.start_date.strftime("%Y-%m-%d"),
            "end": l.end_date.strftime("%Y-%m-%d"),
            "days": l.total_days,
            "reason": l.reason,
            "status": l.status,
            "level1_decision_date": l.level1_decision_date,
            "level2_decision_date": l.level2_decision_date,
        })

    return jsonify(final_list)

@manager_lbp.route("/leave/approve/<int:leave_id>", methods=["POST"])
def approve_leave(leave_id):
    emp = current_employee()
    leave = Leavee.query.get_or_404(leave_id)

    if leave.current_approver_id != emp.user_id:
        return jsonify({"error": "Not authorized"}), 403

    if leave.status == "PENDING_L1":
        leave.status = "PENDING_L2"
        leave.level1_decision_date = datetime.now()
        leave.current_approver_id = leave.level2_approver_id

    elif leave.status == "PENDING_L2":
        leave.status = "APPROVED"
        leave.level2_decision_date = datetime.now()
        leave.current_approver_id = None

    db.session.commit()
    return jsonify({"success": True})
@manager_lbp.route("/leave/reject/<int:leave_id>", methods=["POST"])
def reject_leave(leave_id):
    emp = current_employee()
    leave = Leavee.query.get_or_404(leave_id)

    if leave.current_approver_id != emp.user_id:
        return jsonify({"error": "Not authorized"}), 403

    if leave.status == "PENDING_L1":
        leave.status = "REJECTED_L1"
        leave.level1_decision_date = datetime.now()

    elif leave.status == "PENDING_L2":
        leave.status = "REJECTED_L2"
        leave.level2_decision_date = datetime.now()

    leave.current_approver_id = None
    db.session.commit()

    return jsonify({"success": True})
