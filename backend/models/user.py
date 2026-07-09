from app import db


# User Table
class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(255),
        nullable=False
    )


# Uploaded PDF Table
class UploadedPDF(db.Model):
    __tablename__ = "uploaded_pdf"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False
    )

    filename = db.Column(
        db.String(255),
        nullable=False
    )

    filepath = db.Column(
        db.String(500),
        nullable=False
    )

    upload_date = db.Column(
        db.DateTime,
        default=db.func.now()
    )


# Assessment Results Table
class Assessment(db.Model):
    __tablename__ = "assessment"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False
    )

    pdf_id = db.Column(
        db.Integer,
        db.ForeignKey('uploaded_pdf.id')
    )

    topic = db.Column(
        db.String(200)
    )

    score = db.Column(
        db.Float
    )

    total_questions = db.Column(
        db.Integer
    )

    correct_answers = db.Column(
        db.Integer
    )

    assessment_date = db.Column(
        db.DateTime,
        default=db.func.now()
    )