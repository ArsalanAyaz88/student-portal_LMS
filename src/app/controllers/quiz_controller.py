# File: application/src/app/controllers/quiz_controller.py

import logging
from sqlmodel import Session, select
from sqlalchemy.orm import joinedload
from uuid import UUID
from fastapi import HTTPException, status
from datetime import datetime
from ..utils.time import get_pakistan_time

from ..models.quiz import Quiz, Question, QuizSubmission, Answer, Option
from ..models.enrollment import Enrollment
from ..schemas.quiz import (
    QuizSubmissionCreate,
    QuizResult,
    ResultAnswer,
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
    logging.info(f"Listing quizzes for course_id: {course_id}, student_id: {student_id}")
    try:
        _ensure_enrollment(db, course_id, student_id)
        logging.info(f"Enrollment verified for student {student_id} in course {course_id}")
        
        quizzes = db.exec(
            select(Quiz).where(Quiz.course_id == course_id, Quiz.published == True)
        ).all()
        
        logging.info(f"Found {len(quizzes)} quizzes for course {course_id}")
        return quizzes
    except HTTPException as e:
        logging.error(f"HTTPException while listing quizzes for course {course_id}: {e.detail}", exc_info=True)
        raise
    except Exception as e:
        logging.error(f"Unexpected error listing quizzes for course {course_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while fetching quizzes."
        )


def get_quiz_detail(db: Session, course_id: UUID, quiz_id: UUID, student_id: UUID):
    logging.info(f"Fetching quiz details for quiz_id: {quiz_id}, student_id: {student_id}")
    try:
        _ensure_enrollment(db, course_id, student_id)
        logging.info(f"Enrollment verified for student_id: {student_id}")

        statement = (
            select(Quiz)
            .where(Quiz.id == quiz_id, Quiz.course_id == course_id, Quiz.published == True)
            .options(joinedload(Quiz.questions).joinedload(Question.options))
        )
        quiz = db.exec(statement).first()

        if not quiz:
            logging.warning(f"Quiz not found or not published for quiz_id: {quiz_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found or is not available.")

        logging.info(f"Successfully fetched quiz: {quiz.title}")
        return quiz
    except HTTPException as e:
        logging.error(f"HTTPException in get_quiz_detail for quiz_id {quiz_id}: {e.detail}", exc_info=True)
        raise
    except Exception as e:
        logging.error(f"Unexpected error in get_quiz_detail for quiz_id {quiz_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred while fetching the quiz.")


def submit_quiz(
    db: Session,
    course_id: UUID,
    quiz_id: UUID,
    student_id: UUID,
    payload: QuizSubmissionCreate
) -> QuizSubmission:
    _ensure_enrollment(db, course_id, student_id)
    
    existing_submission = db.exec(
        select(QuizSubmission).where(QuizSubmission.quiz_id == quiz_id, QuizSubmission.student_id == student_id)
    ).first()
    if existing_submission:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You have already submitted this quiz.")

    quiz = db.get(Quiz, quiz_id)
    if not quiz or not quiz.published:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found or not available for submission.")

    valid_question_ids = {q.id for q in quiz.questions}
    if len(payload.answers) != len(valid_question_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="All questions must be answered.")

    score = 0
    correct_options = {opt.id: opt for q in quiz.questions for opt in q.options if opt.is_correct}
    
    new_submission = QuizSubmission(
        quiz_id=quiz_id,
        student_id=student_id,
        submitted_at=get_pakistan_time(),
        score=0 # Initial score
    )
    db.add(new_submission)
    db.flush() # Flush to get submission ID

    for answer_data in payload.answers:
        if answer_data.question_id not in valid_question_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid question ID: {answer_data.question_id}")
        
        # Logic to check if the selected option is correct
        selected_option = db.get(Option, answer_data.selected_option_id)
        if selected_option and selected_option.is_correct:
            score += 1

        db_answer = Answer(**answer_data.dict(), submission_id=new_submission.id)
        db.add(db_answer)

    new_submission.score = score
    new_submission.is_graded = True
    db.add(new_submission)
    db.commit()
    db.refresh(new_submission)
    
    return new_submission


def get_quiz_result(db: Session, submission_id: UUID, student_id: UUID) -> QuizResult:
    logging.info(f"Fetching quiz results for submission_id: {submission_id}")
    try:
        submission = db.exec(
            select(QuizSubmission)
            .where(QuizSubmission.id == submission_id, QuizSubmission.student_id == student_id)
            .options(
                joinedload(QuizSubmission.quiz).joinedload(Quiz.questions).joinedload(Question.options),
                joinedload(QuizSubmission.answers).joinedload(Answer.selected_option)
            )
        ).first()

        if not submission:
            logging.warning(f"Submission not found for submission_id: {submission_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

        quiz = submission.quiz
        answers_map = {ans.question_id: ans for ans in submission.answers}
        result_answers = []

        for question in quiz.questions:
            student_answer = answers_map.get(question.id)
            correct_option = next((opt for opt in question.options if opt.is_correct), None)

            if not student_answer or not correct_option or not student_answer.selected_option:
                logging.warning(f"Skipping question {question.id} due to missing data.")
                continue

            selected_option = student_answer.selected_option
            is_correct = selected_option.id == correct_option.id

            result_answers.append(
                ResultAnswer(
                    question_id=question.id,
                    question_text=question.text,
                    selected_option_id=selected_option.id,
                    selected_option_text=selected_option.text,
                    correct_option_id=correct_option.id,
                    correct_option_text=correct_option.text,
                    is_correct=is_correct,
                )
            )

        quiz_result = QuizResult(
            submission_id=submission.id,
            quiz_title=quiz.title,
            score=submission.score,
            total_questions=len(quiz.questions),
            answers=result_answers,
        )
        logging.info(f"Successfully prepared results for submission_id: {submission_id}")
        return quiz_result

    except Exception as e:
        logging.error(f"Error fetching results for submission {submission_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve quiz results.")
