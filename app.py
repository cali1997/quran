import os
import time
from io import BytesIO
from datetime import datetime
from functools import wraps

from flask import Flask, flash, redirect, render_template, request, send_file, session, url_for
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
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

ADMIN_CREDENTIALS = {
    "adnaan": "Insha-allah",
    "tiger": "Appel100@",
}

ADMIN_DISPLAY_NAMES = {
    "adnaan": "معلم عدنان",
    "tiger": "Ustaad Mohamed",
}

db = SQLAlchemy(app)

PDF_ARABIC_FONT_NAME = "Helvetica"
PDF_FONT_REGISTERED = False
PDF_SIDE_IMAGE = None

SURAH_OPTIONS = [
    "Al-Fatihah",
    "Al-Baqarah",
    "Ali 'Imran",
    "An-Nisa",
    "Al-Ma'idah",
    "Al-An'am",
    "Al-A'raf",
    "Al-Anfal",
    "At-Tawbah",
    "Yunus",
    "Hud",
    "Yusuf",
    "Ar-Ra'd",
    "Ibrahim",
    "Al-Hijr",
    "An-Nahl",
    "Al-Isra",
    "Al-Kahf",
    "Maryam",
    "Ta-Ha",
    "Al-Anbiya",
    "Al-Hajj",
    "Al-Mu'minun",
    "An-Nur",
    "Al-Furqan",
    "Ash-Shu'ara",
    "An-Naml",
    "Al-Qasas",
    "Al-'Ankabut",
    "Ar-Rum",
    "Luqman",
    "As-Sajdah",
    "Al-Ahzab",
    "Saba",
    "Fatir",
    "Ya-Sin",
    "As-Saffat",
    "Sad",
    "Az-Zumar",
    "Ghafir",
    "Fussilat",
    "Ash-Shuraa",
    "Az-Zukhruf",
    "Ad-Dukhan",
    "Al-Jathiyah",
    "Al-Ahqaf",
    "Muhammad",
    "Al-Fath",
    "Al-Hujurat",
    "Qaf",
    "Adh-Dhariyat",
    "At-Tur",
    "An-Najm",
    "Al-Qamar",
    "Ar-Rahman",
    "Al-Waqi'ah",
    "Al-Hadid",
    "Al-Mujadilah",
    "Al-Hashr",
    "Al-Mumtahanah",
    "As-Saff",
    "Al-Jumu'ah",
    "Al-Munafiqun",
    "At-Taghabun",
    "At-Talaq",
    "At-Tahrim",
    "Al-Mulk",
    "Al-Qalam",
    "Al-Haqqah",
    "Al-Ma'arij",
    "Nuh",
    "Al-Jinn",
    "Al-Muzzammil",
    "Al-Muddaththir",
    "Al-Qiyamah",
    "Al-Insan",
    "Al-Mursalat",
    "An-Naba",
    "An-Nazi'at",
    "Abasa",
    "At-Takwir",
    "Al-Infitar",
    "Al-Mutaffifin",
    "Al-Inshiqaq",
    "Al-Buruj",
    "At-Tariq",
    "Al-A'la",
    "Al-Ghashiyah",
    "Al-Fajr",
    "Al-Balad",
    "Ash-Shams",
    "Al-Layl",
    "Ad-Duhaa",
    "Ash-Sharh",
    "At-Tin",
    "Al-'Alaq",
    "Al-Qadr",
    "Al-Bayyinah",
    "Az-Zalzalah",
    "Al-'Adiyat",
    "Al-Qari'ah",
    "At-Takathur",
    "Al-'Asr",
    "Al-Humazah",
    "Al-Fil",
    "Quraysh",
    "Al-Ma'un",
    "Al-Kawthar",
    "Al-Kafirun",
    "An-Nasr",
    "Al-Masad",
    "Al-Ikhlas",
    "Al-Falaq",
    "An-Nas",
]


class StudentProgress(db.Model):
    __tablename__ = "student_progress"

    id = db.Column(db.Integer, primary_key=True)
    owner_username = db.Column(db.String(64), nullable=False, default="adnaan")
    student_name = db.Column(db.String(120), nullable=False)
    juz_number = db.Column(db.Integer, nullable=False)
    ayah_reference = db.Column(db.String(120), nullable=False)
    recorded_at = db.Column(db.DateTime, nullable=False)
    attendance_status = db.Column(db.String(16), nullable=False, default="present")
    is_present = db.Column(db.Boolean, nullable=False, default=True)
    homework_done = db.Column(db.Boolean, nullable=False, default=False)
    is_approved = db.Column(db.Boolean, nullable=False, default=False)
    approved_at = db.Column(db.DateTime, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    rating_inzet = db.Column(db.String(24), nullable=False, default="Voldoende")
    rating_gedrag = db.Column(db.String(24), nullable=False, default="Voldoende")
    rating_beoordeling = db.Column(db.String(24), nullable=False, default="Voldoende")


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
    owner_col = db.session.execute(
        text("SHOW COLUMNS FROM student_progress LIKE 'owner_username'")
    ).fetchone()
    if owner_col is None:
        db.session.execute(
            text(
                "ALTER TABLE student_progress "
                "ADD COLUMN owner_username VARCHAR(64) NOT NULL DEFAULT 'adnaan'"
            )
        )
        db.session.commit()

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

    attendance_col = db.session.execute(
        text("SHOW COLUMNS FROM student_progress LIKE 'attendance_status'")
    ).fetchone()
    if attendance_col is None:
        db.session.execute(
            text(
                "ALTER TABLE student_progress "
                "ADD COLUMN attendance_status VARCHAR(16) NOT NULL DEFAULT 'present'"
            )
        )
        db.session.execute(
            text(
                "UPDATE student_progress "
                "SET attendance_status = CASE "
                "WHEN is_present = TRUE THEN 'present' "
                "ELSE 'absent' END"
            )
        )
        db.session.commit()

    homework_col = db.session.execute(
        text("SHOW COLUMNS FROM student_progress LIKE 'homework_done'")
    ).fetchone()
    if homework_col is None:
        db.session.execute(
            text(
                "ALTER TABLE student_progress "
                "ADD COLUMN homework_done BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )
        db.session.commit()

    inzet_col = db.session.execute(
        text("SHOW COLUMNS FROM student_progress LIKE 'rating_inzet'")
    ).fetchone()
    if inzet_col is None:
        db.session.execute(
            text(
                "ALTER TABLE student_progress "
                "ADD COLUMN rating_inzet VARCHAR(24) NOT NULL DEFAULT 'Voldoende'"
            )
        )
        db.session.commit()

    gedrag_col = db.session.execute(
        text("SHOW COLUMNS FROM student_progress LIKE 'rating_gedrag'")
    ).fetchone()
    if gedrag_col is None:
        db.session.execute(
            text(
                "ALTER TABLE student_progress "
                "ADD COLUMN rating_gedrag VARCHAR(24) NOT NULL DEFAULT 'Voldoende'"
            )
        )
        db.session.commit()

    beoordeling_col = db.session.execute(
        text("SHOW COLUMNS FROM student_progress LIKE 'rating_beoordeling'")
    ).fetchone()
    if beoordeling_col is None:
        db.session.execute(
            text(
                "ALTER TABLE student_progress "
                "ADD COLUMN rating_beoordeling VARCHAR(24) NOT NULL DEFAULT 'Voldoende'"
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


def is_valid_attendance(value):
    return value in {"present", "absent", "late"}


def bool_from_homework(value):
    return value == "done"


def is_valid_rating(value):
    return value in {"Goed", "Voldoende", "Onvoldoende"}


def attendance_label(value):
    if value == "present":
        return "Aanwezig"
    if value == "late":
        return "Te laat"
    return "Afwezig"


def split_surah_ayah(ayah_reference):
    cleaned = (ayah_reference or "").strip()
    if ":" in cleaned:
        surah_part, ayah_part = cleaned.split(":", 1)
        return surah_part.strip() or "-", ayah_part.strip() or "-"
    return "-", cleaned or "-"


def combine_surah_ayah(surah_name, ayah_number):
    return f"{surah_name.strip()}:{ayah_number.strip()}"


def get_current_admin_username():
    return session.get("admin_username", "adnaan")


def get_admin_progress_query():
    return StudentProgress.query.filter_by(owner_username=get_current_admin_username())


def get_admin_row_or_404(row_id):
    return get_admin_progress_query().filter_by(id=row_id).first_or_404()


def register_pdf_fonts_once():
    global PDF_ARABIC_FONT_NAME
    global PDF_FONT_REGISTERED

    if PDF_FONT_REGISTERED:
        return

    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    ]
    for font_path in font_candidates:
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont("DejaVuSans", font_path))
            PDF_ARABIC_FONT_NAME = "DejaVuSans"
            break

    PDF_FONT_REGISTERED = True


def to_pdf_arabic(text):
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        reshaper = arabic_reshaper.ArabicReshaper(
            {
                "support_ligatures": False,
            }
        )
        return get_display(reshaper.reshape(text))
    except Exception:
        return text


def get_pdf_side_image():
    global PDF_SIDE_IMAGE

    if PDF_SIDE_IMAGE is not None:
        return PDF_SIDE_IMAGE

    project_root = app.root_path
    static_dir = os.path.join(project_root, "static")
    candidates = [
        os.path.join(project_root, "holy-quran-9988617.webp"),
        os.path.join(project_root, "pdf_side_image.jpg"),
        os.path.join(project_root, "pdf_side_image.jpeg"),
        os.path.join(project_root, "pdf_side_image.png"),
        os.path.join(project_root, "pdf_side_image.webp"),
        os.path.join(static_dir, "pdf_side_image.jpg"),
        os.path.join(static_dir, "pdf_side_image.jpeg"),
        os.path.join(static_dir, "pdf_side_image.png"),
        os.path.join(static_dir, "pdf_side_image.webp"),
    ]

    for image_path in candidates:
        if os.path.exists(image_path):
            try:
                PDF_SIDE_IMAGE = ImageReader(image_path)
                return PDF_SIDE_IMAGE
            except Exception:
                continue

    PDF_SIDE_IMAGE = False
    return None


def draw_pdf_side_images(pdf, page_width, page_height):
    # Keep page white and use the image only as side icons.
    pdf.setFillColor(colors.white)
    pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)

    side_image = get_pdf_side_image()
    if not side_image:
        return

    icon_size = 64
    icon_y = page_height - 76
    left_x = 8
    right_x = page_width - icon_size - 8

    pdf.drawImage(
        side_image,
        left_x,
        icon_y,
        width=icon_size,
        height=icon_size,
        mask="auto",
        preserveAspectRatio=True,
        anchor="c",
    )
    pdf.drawImage(
        side_image,
        right_x,
        icon_y,
        width=icon_size,
        height=icon_size,
        mask="auto",
        preserveAspectRatio=True,
        anchor="c",
    )


def draw_bismillah_header(pdf, page_width, y):
    register_pdf_fonts_once()

    arabic_text = to_pdf_arabic("بسم الله الرحمن الرحيم")
    pdf.setFont(PDF_ARABIC_FONT_NAME, 18)
    pdf.setFillColor(colors.HexColor("#0f172a"))
    pdf.drawCentredString(page_width / 2, y, arabic_text)
    y -= 18

    pdf.setStrokeColor(colors.HexColor("#93a4ba"))
    pdf.line(40, y, page_width - 40, y)
    y -= 14

    return y


def draw_pdf_title_block(pdf, page_width, y, title, subtitle):
    block_x = 40
    block_y = y - 40
    block_width = page_width - 80
    block_height = 44

    pdf.setFillColor(colors.HexColor("#e5edf7"))
    pdf.roundRect(block_x, block_y, block_width, block_height, 8, fill=1, stroke=0)

    pdf.setFillColor(colors.HexColor("#10243d"))
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(page_width / 2, block_y + 27, title)

    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(colors.HexColor("#334155"))
    pdf.drawCentredString(page_width / 2, block_y + 11, subtitle)

    return block_y - 16


def format_dutch_date(dt):
    weekdays = [
        "Maandag",
        "Dinsdag",
        "Woensdag",
        "Donderdag",
        "Vrijdag",
        "Zaterdag",
        "Zondag",
    ]
    months = [
        "januari",
        "februari",
        "maart",
        "april",
        "mei",
        "juni",
        "juli",
        "augustus",
        "september",
        "oktober",
        "november",
        "december",
    ]
    weekday = weekdays[dt.weekday()]
    month = months[dt.month - 1]
    return f"{weekday} {dt.day} {month} {dt.year}"


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

        if ADMIN_CREDENTIALS.get(username) == password:
            session["is_admin"] = True
            session["admin_username"] = username
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
    feedback_name = request.args.get("feedback_name", "").strip()
    result_name = request.args.get("result_name", "").strip()
    admin_username = get_current_admin_username()
    admin_display_name = ADMIN_DISPLAY_NAMES.get(admin_username, "معلم")
    admin_query = get_admin_progress_query()

    all_student_names = sorted(
        {
            row.student_name
            for row in admin_query.with_entities(StudentProgress.student_name).all()
        },
        key=str.lower,
    )

    if search_name and search_name not in all_student_names:
        search_name = ""

    query = admin_query

    if search_name:
        query = query.filter(func.lower(StudentProgress.student_name) == search_name.lower())

    progress_rows = query.order_by(StudentProgress.recorded_at.desc()).all()
    total_count = len(progress_rows)
    present_count = sum(1 for row in progress_rows if row.attendance_status == "present")
    absent_count = sum(1 for row in progress_rows if row.attendance_status == "absent")
    late_count = sum(1 for row in progress_rows if row.attendance_status == "late")
    approved_count = sum(1 for row in progress_rows if row.is_approved)
    pending_count = total_count - approved_count
    homework_done_count = sum(1 for row in progress_rows if row.homework_done)
    homework_open_count = total_count - homework_done_count
    presence_pct = round((present_count / total_count) * 100) if total_count else 0
    absent_pct = round((absent_count / total_count) * 100) if total_count else 0
    late_pct = round((late_count / total_count) * 100) if total_count else 0
    approval_pct = round((approved_count / total_count) * 100) if total_count else 0
    homework_pct = (
        round((homework_done_count / total_count) * 100) if total_count else 0
    )
    homework_open_pct = (
        round((homework_open_count / total_count) * 100) if total_count else 0
    )
    activities = [
        "Quran",
        "Qaida Annorania",
        "Dictee",
        "Schrijfvaardigheid",
        "Geloof",
        "Grammatica",
        "Gebed",
        "Woordenschat",
        "Spreekvaardigheid",
        "Pauze",
    ]
    rating_options = ["Goed", "Voldoende", "Onvoldoende"]
    student_names = all_student_names
    selected_feedback_row = None
    selected_result_row = None

    if student_names:
        if feedback_name not in student_names:
            feedback_name = student_names[0]

        selected_feedback_row = next(
            (row for row in progress_rows if row.student_name == feedback_name), None
        )

        if result_name not in student_names:
            result_name = feedback_name

        selected_result_row = next(
            (row for row in progress_rows if row.student_name == result_name), None
        )

    return render_template(
        "index.html",
        progress_rows=progress_rows,
        search_name=search_name,
        today_label=format_dutch_date(datetime.now()),
        total_count=total_count,
        present_count=present_count,
        absent_count=absent_count,
        late_count=late_count,
        absent_pct=absent_pct,
        late_pct=late_pct,
        approved_count=approved_count,
        pending_count=pending_count,
        presence_pct=presence_pct,
        approval_pct=approval_pct,
        homework_done_count=homework_done_count,
        homework_open_count=homework_open_count,
        homework_pct=homework_pct,
        homework_open_pct=homework_open_pct,
        activities=activities,
        rating_options=rating_options,
        student_names=student_names,
        feedback_name=feedback_name,
        selected_feedback_row=selected_feedback_row,
        result_name=result_name,
        selected_result_row=selected_result_row,
        surah_options=SURAH_OPTIONS,
        admin_display_name=admin_display_name,
    )


@app.route("/rapport", methods=["GET"])
@login_required
def rapport_page():
    rows = get_admin_progress_query().order_by(StudentProgress.student_name.asc()).all()
    generated_at = datetime.now().strftime("%d-%m-%Y %H:%M")
    return render_template("rapport.html", rows=rows, generated_at=generated_at)


@app.route("/add", methods=["POST"])
@login_required
def add_progress():
    admin_username = get_current_admin_username()
    selected_student = request.form.get("student_choice", "").strip()
    new_student_name = normalize_name(request.form.get("student_name_new", ""))
    student_name = normalize_name(selected_student if selected_student else new_student_name)

    if selected_student == "__new__":
        student_name = new_student_name

    juz_number_raw = request.form.get("juz_number", "").strip()
    surah_name = request.form.get("surah_name", "").strip()
    ayah_number = request.form.get("ayah_number", "").strip()
    attendance_value = request.form.get("attendance_status", "present")
    homework_value = request.form.get("homework", "open")

    if not student_name or not juz_number_raw or not surah_name or not ayah_number:
        flash("Vul alle velden in.", "error")
        return redirect(url_for("index"))

    if surah_name not in SURAH_OPTIONS:
        flash("Kies een geldige surah.", "error")
        return redirect(url_for("index"))

    ayah_reference = combine_surah_ayah(surah_name, ayah_number)

    if not is_valid_attendance(attendance_value):
        flash("Ongeldige aanwezigheidsstatus.", "error")
        return redirect(url_for("index"))

    if homework_value not in {"done", "open"}:
        flash("Ongeldige huiswerkstatus.", "error")
        return redirect(url_for("index"))

    existing_exact = get_admin_progress_query().filter(
        func.lower(StudentProgress.student_name) == student_name.lower()
    ).first()
    if existing_exact and selected_student != "__new__":
        try:
            juz_number = int(juz_number_raw)
        except ValueError:
            flash("Juz nummer moet een getal zijn.", "error")
            return redirect(url_for("index"))

        existing_exact.juz_number = juz_number
        existing_exact.ayah_reference = ayah_reference
        existing_exact.attendance_status = attendance_value
        existing_exact.is_present = bool_from_presence(attendance_value)
        existing_exact.homework_done = bool_from_homework(homework_value)
        existing_exact.recorded_at = datetime.now()
        db.session.commit()
        flash("Bestaande leerling bijgewerkt.", "success")
        return redirect(url_for("index"))

    if existing_exact and selected_student == "__new__":
        flash("Deze leerlingnaam bestaat al. Kies hem uit het menu.", "error")
        return redirect(url_for("index"))

    if len(student_name.split()) == 1:
        fname = first_name(student_name)
        same_first = get_admin_progress_query().filter(
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
        owner_username=admin_username,
        student_name=student_name,
        juz_number=juz_number,
        ayah_reference=ayah_reference,
        recorded_at=datetime.now(),
        attendance_status=attendance_value,
        is_present=bool_from_presence(attendance_value),
        homework_done=bool_from_homework(homework_value),
    )
    db.session.add(row)
    db.session.commit()

    flash("Voortgang opgeslagen.", "success")
    return redirect(url_for("index"))


@app.route("/approve/<int:row_id>", methods=["POST"])
@login_required
def approve(row_id):
    search_name = request.args.get("search_name", "").strip()
    row = get_admin_row_or_404(row_id)
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
    row = get_admin_row_or_404(row_id)
    db.session.delete(row)
    db.session.commit()
    flash("Leerlingrecord verwijderd.", "success")
    return redirect(url_for("index", search_name=search_name))


@app.route("/delete-by-name", methods=["POST"])
@login_required
def delete_by_name():
    search_name = request.args.get("search_name", "").strip()
    student_name = normalize_name(request.form.get("student_name", ""))

    if not student_name:
        flash("Kies eerst een leerling om te verwijderen.", "error")
        return redirect(url_for("index", search_name=search_name))

    row = get_admin_progress_query().filter(
        func.lower(StudentProgress.student_name) == student_name.lower()
    ).first()

    if row is None:
        flash("Leerling niet gevonden.", "error")
        return redirect(url_for("index", search_name=search_name))

    db.session.delete(row)
    db.session.commit()
    flash(f"Leerling '{student_name}' verwijderd.", "success")
    return redirect(url_for("index", search_name=search_name))


@app.route("/update/<int:row_id>", methods=["POST"])
@login_required
def update_progress(row_id):
    search_name = request.args.get("search_name", "").strip()
    ayah_reference = request.form.get("ayah_reference", "").strip()
    feedback = request.form.get("feedback", "").strip()
    attendance_value = request.form.get("attendance_status", "present")
    homework_value = request.form.get("homework", "open")
    inzet_rating = request.form.get("inzet_rating", "Voldoende")
    gedrag_rating = request.form.get("gedrag_rating", "Voldoende")
    beoordeling_rating = request.form.get("beoordeling_rating", "Voldoende")

    if not ayah_reference:
        flash("Ayah mag niet leeg zijn.", "error")
        return redirect(url_for("index", search_name=search_name))

    if not is_valid_attendance(attendance_value):
        flash("Ongeldige aanwezigheidsstatus.", "error")
        return redirect(url_for("index", search_name=search_name))

    if homework_value not in {"done", "open"}:
        flash("Ongeldige huiswerkstatus.", "error")
        return redirect(url_for("index", search_name=search_name))

    if not all(
        [
            is_valid_rating(inzet_rating),
            is_valid_rating(gedrag_rating),
            is_valid_rating(beoordeling_rating),
        ]
    ):
        flash("Ongeldige beoordelingskeuze.", "error")
        return redirect(url_for("index", search_name=search_name))

    row = get_admin_row_or_404(row_id)
    row.ayah_reference = ayah_reference
    row.feedback = feedback
    row.attendance_status = attendance_value
    row.is_present = bool_from_presence(attendance_value)
    row.homework_done = bool_from_homework(homework_value)
    row.rating_inzet = inzet_rating
    row.rating_gedrag = gedrag_rating
    row.rating_beoordeling = beoordeling_rating
    row.recorded_at = datetime.now()
    db.session.commit()

    flash("Ayah, feedback, huiswerk en datum/tijd bijgewerkt.", "success")
    return redirect(url_for("index", search_name=search_name))


@app.route("/update-attendance/<int:row_id>", methods=["POST"])
@login_required
def update_attendance(row_id):
    search_name = request.args.get("search_name", "").strip()
    attendance_value = request.form.get("attendance_status", "present")

    if not is_valid_attendance(attendance_value):
        flash("Ongeldige aanwezigheidsstatus.", "error")
        return redirect(url_for("index", search_name=search_name))

    row = get_admin_row_or_404(row_id)
    row.attendance_status = attendance_value
    row.is_present = bool_from_presence(attendance_value)
    db.session.commit()

    flash(f"Aanwezigheid aangepast voor {row.student_name}.", "success")
    return redirect(url_for("index", search_name=search_name))


@app.route("/update-homework/<int:row_id>", methods=["POST"])
@login_required
def update_homework(row_id):
    search_name = request.args.get("search_name", "").strip()
    homework_value = request.form.get("homework", "open")

    if homework_value not in {"done", "open"}:
        flash("Ongeldige huiswerkstatus.", "error")
        return redirect(url_for("index", search_name=search_name))

    row = get_admin_row_or_404(row_id)
    row.homework_done = bool_from_homework(homework_value)
    db.session.commit()

    flash(f"Huiswerkstatus aangepast voor {row.student_name}.", "success")
    return redirect(url_for("index", search_name=search_name))


@app.route("/update-feedback", methods=["POST"])
@login_required
def update_feedback():
    search_name = request.args.get("search_name", "").strip()
    student_name = normalize_name(request.form.get("student_name", ""))
    feedback_text = request.form.get("feedback", "").strip()
    beoordeling_rating = request.form.get("beoordeling_rating", "Voldoende")

    if not student_name:
        flash("Kies eerst een leerling.", "error")
        return redirect(url_for("index", search_name=search_name))

    if not is_valid_rating(beoordeling_rating):
        flash("Ongeldige beoordelingskeuze.", "error")
        return redirect(url_for("index", search_name=search_name, feedback_name=student_name))

    row = get_admin_progress_query().filter(
        func.lower(StudentProgress.student_name) == student_name.lower()
    ).first()
    if row is None:
        flash("Leerling niet gevonden.", "error")
        return redirect(url_for("index", search_name=search_name))

    row.feedback = feedback_text
    row.rating_beoordeling = beoordeling_rating
    row.recorded_at = datetime.now()
    db.session.commit()

    flash("Feedback opgeslagen.", "success")
    return redirect(
        url_for("index", search_name=search_name, feedback_name=row.student_name)
    )


@app.route("/update-ratings/<int:row_id>", methods=["POST"])
@login_required
def update_ratings(row_id):
    search_name = request.args.get("search_name", "").strip()
    inzet_rating = request.form.get("inzet_rating", "Voldoende")
    gedrag_rating = request.form.get("gedrag_rating", "Voldoende")
    beoordeling_rating = request.form.get("beoordeling_rating", "Voldoende")

    if not all(
        [
            is_valid_rating(inzet_rating),
            is_valid_rating(gedrag_rating),
            is_valid_rating(beoordeling_rating),
        ]
    ):
        flash("Ongeldige beoordelingskeuze.", "error")
        return redirect(url_for("index", search_name=search_name))

    row = get_admin_row_or_404(row_id)
    row.rating_inzet = inzet_rating
    row.rating_gedrag = gedrag_rating
    row.rating_beoordeling = beoordeling_rating
    db.session.commit()

    flash("Behaalde resultaten opgeslagen.", "success")
    return redirect(url_for("index", search_name=search_name))


@app.route("/pdf/<int:row_id>", methods=["GET"])
@login_required
def download_student_pdf(row_id):
    row = get_admin_row_or_404(row_id)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    draw_pdf_side_images(pdf, width, height)
    y = height - 60

    y = draw_bismillah_header(pdf, width, y)
    y = draw_pdf_title_block(
        pdf,
        width,
        y,
        "Quran Leerling Rapport",
        f"Gegenereerd op {datetime.now().strftime('%d-%m-%Y %H:%M')}",
    )

    card_x = 40
    card_width = width - 80
    card_height = 210
    card_y = y - card_height

    pdf.setFillColor(colors.HexColor("#f8fbff"))
    pdf.roundRect(card_x, card_y, card_width, card_height, 8, fill=1, stroke=0)

    surah_value, ayah_value = split_surah_ayah(row.ayah_reference)
    rows = [
        ("Naam", row.student_name, colors.HexColor("#0f172a")),
        ("Aanwezigheid", attendance_label(row.attendance_status), colors.HexColor("#0f172a")),
        ("Juz", str(row.juz_number), colors.HexColor("#0f172a")),
        ("Surah", surah_value, colors.HexColor("#0f172a")),
        ("Ayah", ayah_value, colors.HexColor("#0f172a")),
        (
            "Huiswerk",
            "Ingeleverd" if row.homework_done else "Niet ingeleverd",
            colors.HexColor("#b91c1c"),
        ),
        ("Feedback", row.feedback or "-", colors.HexColor("#0f172a")),
    ]

    line_y = card_y + card_height - 28
    for label, value, color in rows:
        pdf.setFillColor(color)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(card_x + 16, line_y, f"{label}:")
        pdf.setFont("Helvetica", 11)
        pdf.drawString(card_x + 126, line_y, value)
        line_y -= 24

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


@app.route("/pdf-by-name", methods=["GET"])
@login_required
def download_student_pdf_by_name():
    student_name = normalize_name(request.args.get("student_name", ""))

    if not student_name:
        flash("Kies eerst een leerling voor PDF-download.", "error")
        return redirect(url_for("index"))

    row = get_admin_progress_query().filter(
        func.lower(StudentProgress.student_name) == student_name.lower()
    ).first()
    if row is None:
        flash("Leerling niet gevonden.", "error")
        return redirect(url_for("index"))

    return download_student_pdf(row.id)


@app.route("/pdf-all", methods=["GET"])
@login_required
def download_all_students_pdf():
    rows = get_admin_progress_query().order_by(StudentProgress.student_name.asc()).all()

    if not rows:
        flash("Nog geen leerlingen om als PDF te downloaden.", "error")
        return redirect(url_for("index"))

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    draw_pdf_side_images(pdf, width, height)

    y = height - 50
    y = draw_bismillah_header(pdf, width, y)
    y = draw_pdf_title_block(
        pdf,
        width,
        y,
        "Quran Leerling Totaalrapport",
        f"Datum: {datetime.now().strftime('%d-%m-%Y %H:%M')}",
    )

    for index, row in enumerate(rows, start=1):
        card_height = 188
        if y - card_height < 50:
            pdf.showPage()
            draw_pdf_side_images(pdf, width, height)
            y = height - 50
            y = draw_bismillah_header(pdf, width, y)
            y = draw_pdf_title_block(
                pdf,
                width,
                y,
                "Quran Leerling Totaalrapport (vervolg)",
                f"Datum: {datetime.now().strftime('%d-%m-%Y %H:%M')}",
            )

        card_x = 40
        card_width = width - 80
        card_y = y - card_height

        pdf.setFillColor(colors.HexColor("#f8fbff"))
        pdf.roundRect(card_x, card_y, card_width, card_height, 8, fill=1, stroke=0)

        surah_value, ayah_value = split_surah_ayah(row.ayah_reference)
        row_items = [
            ("Naam", row.student_name, colors.HexColor("#0f172a")),
            ("Aanwezigheid", attendance_label(row.attendance_status), colors.HexColor("#0f172a")),
            ("Juz", str(row.juz_number), colors.HexColor("#0f172a")),
            ("Surah", surah_value, colors.HexColor("#0f172a")),
            ("Ayah", ayah_value, colors.HexColor("#0f172a")),
            (
                "Huiswerk",
                "Ingeleverd" if row.homework_done else "Niet ingeleverd",
                colors.HexColor("#b91c1c"),
            ),
            ("Feedback", row.feedback or "-", colors.HexColor("#0f172a")),
        ]

        line_y = card_y + card_height - 24
        for label, value, color in row_items:
            pdf.setFillColor(color)
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawString(card_x + 14, line_y, f"{label}:")
            pdf.setFont("Helvetica", 10)
            pdf.drawString(card_x + 104, line_y, value)
            line_y -= 22

        y = card_y - 12

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="quran_totaalrapport.pdf",
        mimetype="application/pdf",
    )


if __name__ == "__main__":
    if not wait_for_db():
        raise RuntimeError("Database is niet bereikbaar.")

    with app.app_context():
        db.create_all()
        ensure_schema_updates()

    app.run(host="0.0.0.0", port=5000)
