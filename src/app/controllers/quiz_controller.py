# File: application/src/app/controllers/quiz_controller.py

import logging
from sqlmodel import Session, select
from sqlalchemy import func
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
    QuizListRead,
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
    logging.info(f"Listing all quizzes for course_id: {course_id}, student_id: {student_id}")
    try:
        _ensure_enrollment(db, course_id, student_id)
        logging.info(f"Enrollment verified for student {student_id} in course {course_id}")

        # A quiz is considered published if its due_date is not NULL.
        quizzes_stmt = select(Quiz).where(
            Quiz.course_id == course_id,
            Quiz.due_date != None
        )
        all_quizzes = db.exec(quizzes_stmt).all()

        if not all_quizzes:
            return []

        quiz_ids = [quiz.id for quiz in all_quizzes]

        # Get all submissions by the student for these quizzes
        submissions_stmt = select(QuizSubmission).where(
            QuizSubmission.student_id == student_id,
            QuizSubmission.quiz_id.in_(quiz_ids)
        )
        submissions = db.exec(submissions_stmt).all()
        submissions_map = {sub.quiz_id: sub for sub in submissions}

        # Get question counts for all quizzes
        question_count_stmt = (
            select(Question.quiz_id, func.count(Question.id).label("question_count"))
            .where(Question.quiz_id.in_(quiz_ids))
            .group_by(Question.quiz_id)
        )
        question_counts_result = db.exec(question_count_stmt).all()
        question_counts_map = {quiz_id: count for quiz_id, count in question_counts_result}

        quizzes_with_status = []
        for quiz in all_quizzes:
            submission = submissions_map.get(quiz.id)
            quizzes_with_status.append(
                QuizListRead(
                    id=quiz.id,
                    title=quiz.title,
                    description=quiz.description,
                    due_date=quiz.due_date,
                    course_id=quiz.course_id,
                    is_submitted=submission is not None,
                    score=submission.score if submission else None,
                    submission_id=submission.id if submission else None,
                    total_questions=question_counts_map.get(quiz.id, 0),
                )
            )

        logging.info(f"Found {len(all_quizzes)} quizzes for course {course_id}, with submission statuses.")
        return quizzes_with_status
    except HTTPException as e:
        logging.error(f"HTTPException while listing quizzes: {e.detail}", exc_info=True)
        raise
    except Exception as e:
        logging.error(f"Unexpected error listing quizzes: {e}", exc_info=True)
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
            .where(Quiz.id == quiz_id, Quiz.course_id == course_id)
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
    logging.info(f"Attempting quiz submission for quiz_id: {quiz_id}, student_id: {student_id}")
    logging.info(f"Submission payload: {payload.dict()}")
    
    try:
        _ensure_enrollment(db, course_id, student_id)
        # If a student has already submitted this quiz, delete the old submission.
        existing_submission = db.exec(
            select(QuizSubmission).where(
                QuizSubmission.student_id == student_id,
                QuizSubmission.quiz_id == quiz_id
            )
        ).first()

        if existing_submission:
            logging.info(f"Student {student_id} is re-submitting quiz {quiz_id}. Deleting previous submission.")
            
            # Explicitly delete answers associated with the submission to avoid foreign key violations
            # if cascade delete is not configured.
            answers_to_delete = db.exec(
                select(Answer).where(Answer.submission_id == existing_submission.id)
            ).all()
            for answer in answers_to_delete:
                db.delete(answer)

            db.delete(existing_submission)
            db.commit()
        logging.info("No existing submission found for this student and quiz.")

        quiz = db.get(Quiz, quiz_id)
        if not quiz:
            logging.error(f"Quiz with id {quiz_id} not found.")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found or not available for submission.")
        logging.info(f"Quiz '{quiz.title}' found.")

        valid_question_ids = {q.id for q in quiz.questions}
        logging.info(f"Quiz has {len(valid_question_ids)} questions. Payload has {len(payload.answers)} answers.")
        if len(payload.answers) != len(valid_question_ids):
            logging.error("Number of answers in payload does not match number of questions in quiz.")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="All questions must be answered.")

        score = 0
        
        new_submission = QuizSubmission(
            quiz_id=quiz_id,
            student_id=student_id,
            submitted_at=get_pakistan_time(),
            score=0 # Initial score
        )
        db.add(new_submission)
        db.flush() # Flush to get submission ID
        logging.info(f"Created new submission with id: {new_submission.id}")

        for answer_data in payload.answers:
            if answer_data.question_id not in valid_question_ids:
                logging.error(f"Invalid question_id {answer_data.question_id} in payload.")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid question ID: {answer_data.question_id}")
            
            selected_option = db.get(Option, answer_data.selected_option_id)
            if selected_option and selected_option.is_correct:
                score += 1

            db_answer = Answer(**answer_data.dict(), submission_id=new_submission.id)
            db.add(db_answer)
        
        logging.info("All answers processed.")

        new_submission.score = score
        new_submission.is_graded = True
        db.add(new_submission)
        db.commit()
        db.refresh(new_submission)
        
        logging.info(f"Quiz submission successful for student {student_id} on quiz {quiz_id}. Final score: {score}")
        return new_submission
    except HTTPException as e:
        logging.error(f"HTTPException during quiz submission: {e.detail}", exc_info=True)
        raise
    except Exception as e:
        logging.critical(f"An unexpected critical error occurred during quiz submission: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during quiz submission."
        )


def list_submissions_for_student(db: Session, course_id: UUID, student_id: UUID):
    logging.info(f"Listing submissions for student {student_id} in course {course_id}")
    try:
        _ensure_enrollment(db, course_id, student_id)
        
        submissions = db.exec(
            select(QuizSubmission)
            .join(Quiz)
            .where(
                QuizSubmission.student_id == student_id,
                Quiz.course_id == course_id
            )
            .options(joinedload(QuizSubmission.quiz))
        ).all()
        
        logging.info(f"Found {len(submissions)} submissions for student {student_id} in course {course_id}")
        return submissions
    except Exception as e:
        logging.error(f"Error listing submissions for student {student_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve quiz submissions.")

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
