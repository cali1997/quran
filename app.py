import os
import time
from io import BytesIO
from datetime import datetime
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, send_file, session, url_for
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, text

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me")

DB_USER = os.getenv("DB_USER", "quran_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "quran_pass")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "quran_school")

app.config[
    "SQLALCHEMY_DATABASE_URI"
] = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

ADMIN_USERNAME = "adnaan"
ADMIN_PASSWORD = "Insha-allah"

db = SQLAlchemy(app)


class StudentProgress(db.Model):
    __tablename__ = "student_progress"

    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(120), nullable=False)
    juz_number = db.Column(db.Integer, nullable=False)
    ayah_reference = db.Column(db.String(120), nullable=False)
    recorded_at = db.Column(db.DateTime, nullable=False)
    is_present = db.Column(db.Boolean, nullable=False, default=True)
    is_approved = db.Column(db.Boolean, nullable=False, default=False)
    approved_at = db.Column(db.DateTime, nullable=True)
    feedback = db.Column(db.Text, nullable=True)


def wait_for_db(max_retries=30, wait_seconds=2):
    with app.app_context():
        for _ in range(max_retries):
            try:
                db.session.execute(text("SELECT 1"))
                return True
            except Exception:
                time.sleep(wait_seconds)
        return False


def ensure_schema_updates():
    # Keep old databases compatible by adding the feedback column if needed.
    feedback_col = db.session.execute(
        text("SHOW COLUMNS FROM student_progress LIKE 'feedback'")
    ).fetchone()
    if feedback_col is None:
        db.session.execute(text("ALTER TABLE student_progress ADD COLUMN feedback TEXT NULL"))
        db.session.commit()

    present_col = db.session.execute(
        text("SHOW COLUMNS FROM student_progress LIKE 'is_present'")
    ).fetchone()
    if present_col is None:
        db.session.execute(
            text(
                "ALTER TABLE student_progress "
                "ADD COLUMN is_present BOOLEAN NOT NULL DEFAULT TRUE"
            )
        )
        db.session.commit()


def normalize_name(value):
    return " ".join(value.split())


def first_name(value):
    parts = value.split()
    return parts[0].lower() if parts else ""


def bool_from_presence(value):
    return value == "present"


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped_view


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("is_admin"):
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["is_admin"] = True
            flash("Succesvol ingelogd.", "success")
            return redirect(url_for("index"))

        flash("Onjuiste inloggegevens.", "error")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Je bent uitgelogd.", "success")
    return redirect(url_for("login"))


@app.route("/", methods=["GET"])
@login_required
def index():
    search_name = request.args.get("search_name", "").strip()
    query = StudentProgress.query

    if search_name:
        query = query.filter(StudentProgress.student_name.ilike(f"%{search_name}%"))

    progress_rows = query.order_by(StudentProgress.recorded_at.desc()).all()
    return render_template(
        "index.html", progress_rows=progress_rows, search_name=search_name
    )


@app.route("/add", methods=["POST"])
@login_required
def add_progress():
    student_name = normalize_name(request.form.get("student_name", ""))
    juz_number_raw = request.form.get("juz_number", "").strip()
    ayah_reference = request.form.get("ayah_reference", "").strip()
    presence_value = request.form.get("presence", "present")

    if not student_name or not juz_number_raw or not ayah_reference:
        flash("Vul alle velden in.", "error")
        return redirect(url_for("index"))

    if presence_value not in {"present", "absent"}:
        flash("Ongeldige aanwezigheidsstatus.", "error")
        return redirect(url_for("index"))

    existing_exact = StudentProgress.query.filter(
        func.lower(StudentProgress.student_name) == student_name.lower()
    ).first()
    if existing_exact:
        flash("Deze leerlingnaam bestaat al. Gebruik een unieke naam.", "error")
        return redirect(url_for("index"))

    if len(student_name.split()) == 1:
        fname = first_name(student_name)
        same_first = StudentProgress.query.filter(
            func.lower(StudentProgress.student_name).like(f"{fname} %")
        ).first()
        if same_first:
            flash(
                "Deze voornaam bestaat al. Voeg ook een achternaam toe (bijv. Mohamed Ali).",
                "error",
            )
            return redirect(url_for("index"))

    try:
        juz_number = int(juz_number_raw)
    except ValueError:
        flash("Juz nummer moet een getal zijn.", "error")
        return redirect(url_for("index"))

    row = StudentProgress(
        student_name=student_name,
        juz_number=juz_number,
        ayah_reference=ayah_reference,
        recorded_at=datetime.now(),
        is_present=bool_from_presence(presence_value),
    )
    db.session.add(row)
    db.session.commit()

    flash("Voortgang opgeslagen.", "success")
    return redirect(url_for("index"))


@app.route("/approve/<int:row_id>", methods=["POST"])
@login_required
def approve(row_id):
    search_name = request.args.get("search_name", "").strip()
    row = StudentProgress.query.get_or_404(row_id)
    if not row.is_approved:
        row.is_approved = True
        row.approved_at = datetime.utcnow()
        db.session.commit()
        flash("Juz is goedgekeurd.", "success")
    else:
        flash("Deze regel was al goedgekeurd.", "error")

    return redirect(url_for("index", search_name=search_name))


@app.route("/delete/<int:row_id>", methods=["POST"])
@login_required
def delete_progress(row_id):
    search_name = request.args.get("search_name", "").strip()
    row = StudentProgress.query.get_or_404(row_id)
    db.session.delete(row)
    db.session.commit()
    flash("Leerlingrecord verwijderd.", "success")
    return redirect(url_for("index", search_name=search_name))


@app.route("/update/<int:row_id>", methods=["POST"])
@login_required
def update_progress(row_id):
    search_name = request.args.get("search_name", "").strip()
    ayah_reference = request.form.get("ayah_reference", "").strip()
    feedback = request.form.get("feedback", "").strip()
    presence_value = request.form.get("presence", "present")

    if not ayah_reference:
        flash("Ayah mag niet leeg zijn.", "error")
        return redirect(url_for("index", search_name=search_name))

    if presence_value not in {"present", "absent"}:
        flash("Ongeldige aanwezigheidsstatus.", "error")
        return redirect(url_for("index", search_name=search_name))

    row = StudentProgress.query.get_or_404(row_id)
    row.ayah_reference = ayah_reference
    row.feedback = feedback
    row.is_present = bool_from_presence(presence_value)
    row.recorded_at = datetime.now()
    db.session.commit()

    flash("Ayah, feedback en datum/tijd bijgewerkt.", "success")
    return redirect(url_for("index", search_name=search_name))


@app.route("/pdf/<int:row_id>", methods=["GET"])
@login_required
def download_student_pdf(row_id):
    row = StudentProgress.query.get_or_404(row_id)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 60

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, "Quran Leerling Rapport")
    y -= 35

    pdf.setFont("Helvetica", 11)
    lines = [
        f"Naam: {row.student_name}",
        f"Juz: {row.juz_number}",
        f"Ayah: {row.ayah_reference}",
        f"Datum/Tijd laatste update: {row.recorded_at.strftime('%d-%m-%Y %H:%M')}",
        f"Aanwezigheid: {'Aanwezig' if row.is_present else 'Afwezig'}",
        f"Status: {'Goedgekeurd' if row.is_approved else 'Nog niet goedgekeurd'}",
        (
            "Datum/Tijd goedkeuring: "
            f"{row.approved_at.strftime('%d-%m-%Y %H:%M') if row.approved_at else '-'}"
        ),
        f"Feedback: {row.feedback or '-'}",
    ]

    for line in lines:
        pdf.drawString(50, y, line)
        y -= 22

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    safe_name = row.student_name.replace(" ", "_")
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"rapport_{safe_name}.pdf",
        mimetype="application/pdf",
    )


if __name__ == "__main__":
    if not wait_for_db():
        raise RuntimeError("Database is niet bereikbaar.")

    with app.app_context():
        db.create_all()
        ensure_schema_updates()

    app.run(host="0.0.0.0", port=5000)
