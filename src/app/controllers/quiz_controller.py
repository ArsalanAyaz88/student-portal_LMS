# File: application/src/app/controllers/quiz_controller.py

from sqlmodel import Session, select
from uuid import UUID
from fastapi import HTTPException, status
from datetime import datetime

from ..models.quiz import Quiz, QuizSubmission, Answer, Option
from ..models.quiz_audit_log import QuizAuditLog
from ..models.enrollment import Enrollment
from ..schemas.quiz import (
    QuizCreate,
    QuizUpdate,
    QuizSubmissionCreate,
    QuizResult,
    QuizResultDetail,
)


def _ensure_enrollment(db: Session, course_id: UUID, student_id: UUID):
    """403 if the student isn't approved+accessible for this course."""
    stmt = (
        select(Enrollment)
        .where(
            Enrollment.course_id     == course_id,
            Enrollment.user_id       == student_id,
            Enrollment.status        == "approved",
            Enrollment.is_accessible == True,
        )
    )
    if not db.exec(stmt).first():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="🚫 You are not enrolled in this course."
        )


def list_quizzes(db: Session, course_id: UUID, student_id: UUID):
    _ensure_enrollment(db, course_id, student_id)
    return db.exec(
        select(Quiz).where(Quiz.course_id == course_id)
    ).all()


def get_quiz_detail(db: Session, course_id: UUID, quiz_id: UUID, student_id: UUID):
    _ensure_enrollment(db, course_id, student_id)

    quiz = db.exec(
        select(Quiz)
        .where(Quiz.id == quiz_id, Quiz.course_id == course_id)
    ).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

    # eager-load options
    for q in quiz.questions:
        _ = q.options

    return quiz


def submit_quiz(
    db: Session,
    course_id: UUID,
    quiz_id: UUID,
    student_id: UUID,
    payload: QuizSubmissionCreate
) -> QuizResult:
    # --- Only allow one submission per student per quiz ---
    existing_submission = db.exec(
        select(QuizSubmission)
        .where(
            QuizSubmission.quiz_id == quiz_id,
            QuizSubmission.student_id == student_id
        )
    ).first()
    if existing_submission:
        raise HTTPException(
            status_code=403,
            detail="You have already submitted this quiz. Only one attempt is allowed."
        )
    # 1️⃣ verify enrollment + quiz exists
    quiz = get_quiz_detail(db, course_id, quiz_id, student_id)

    # 2️⃣ prepare validation maps
    valid_qids = {q.id for q in quiz.questions}
    valid_opts = {q.id: {opt.id for opt in q.options} for q in quiz.questions}

    # 3️⃣ record new submission
    sub = QuizSubmission(
        quiz_id=quiz_id,
        student_id=student_id,
        submitted_at=datetime.utcnow()
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    # --- Audit log ---
    audit = QuizAuditLog(
        student_id=student_id,
        quiz_id=quiz_id,
        action="submit",
        details=f"Submission ID: {sub.id}"
    )
    db.add(audit)
    db.commit()


    # 4️⃣ map correct answers
    correct_map = {
        opt.question_id: opt.id
        for q in quiz.questions
        for opt in q.options
        if opt.is_correct
    }

    score = 0
    details: list[QuizResultDetail] = []

    # 5️⃣ validate & save each answer
    for ans in payload.answers:
        # question must belong to quiz
        if ans.question_id not in valid_qids:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                f"Invalid question_id: {ans.question_id}")
        # if provided, option must belong to that question
        sel = ans.selected_option_id
        if sel is not None and sel not in valid_opts[ans.question_id]:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                f"Option {sel} is not valid for question {ans.question_id}")

        # compute correctness
        is_corr = (sel == correct_map.get(ans.question_id))
        if is_corr:
            score += 1

        details.append(QuizResultDetail(
            question_id=ans.question_id,
            correct=is_corr
        ))

        # persist answer
        db.add(Answer(
            submission_id=sub.id,
            question_id=ans.question_id,
            selected_option_id=sel
        ))

    # Update submission with auto-calculated score
    sub.score = score
    sub.is_graded = True
    db.add(sub)
    db.commit()

    return QuizResult(
        submission_id=sub.id,
        score=score,
        total=len(payload.answers),
        details=details
    )


def get_quiz_result(
    db: Session,
    course_id: UUID,
    quiz_id: UUID,
    submission_id: UUID,
    student_id: UUID
) -> QuizResult:
    _ensure_enrollment(db, course_id, student_id)

    sub = db.get(QuizSubmission, submission_id)
    if not sub or sub.quiz_id != quiz_id or sub.student_id != student_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Submission not found")

    if sub.score is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not available yet.")

    details: list[QuizResultDetail] = []
    total_questions = 0
    for ans in sub.answers:
        total_questions += 1
        opt = db.get(Option, ans.selected_option_id) if ans.selected_option_id else None
        correct = bool(opt and opt.is_correct)
        details.append(QuizResultDetail(
            question_id=ans.question_id,
            correct=correct
        ))

    return QuizResult(
        submission_id=sub.id,
        score=sub.score,
        total=total_questions,
        details=details
    )


def create_quiz(db: Session, course_id: UUID, quiz_data: QuizCreate) -> Quiz:
    new_quiz = Quiz(course_id=course_id, title=quiz_data.title, description=quiz_data.description)
    db.add(new_quiz)
    db.commit()
    db.refresh(new_quiz)

    for q_data in quiz_data.questions:
        new_question = Question(quiz_id=new_quiz.id, text=q_data.text, is_multiple_choice=q_data.is_multiple_choice)
        db.add(new_question)
        db.commit()
        db.refresh(new_question)

        for o_data in q_data.options:
            new_option = Option(question_id=new_question.id, text=o_data.text, is_correct=o_data.is_correct)
            db.add(new_option)
    
    db.commit()
    db.refresh(new_quiz)
    return new_quiz

def update_quiz(db: Session, quiz_id: UUID, quiz_data: QuizUpdate) -> Quiz:
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

    update_data = quiz_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(quiz, key, value)

    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return quiz

def delete_quiz(db: Session, quiz_id: UUID):
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    
    db.delete(quiz)
    db.commit()
    return {"message": "Quiz deleted successfully"}

def get_quiz_submissions(db: Session, quiz_id: UUID):
    return db.exec(select(QuizSubmission).where(QuizSubmission.quiz_id == quiz_id)).all()
