"""
This module imports all the models to make them accessible under the app.models
namespace and to ensure they are registered with SQLModel's metadata.
"""
# This file ensures that all models are imported and registered with SQLModel's metadata.
# By importing them here, we can avoid circular import errors in other parts of the app
# and ensure that `create_db_and_tables` knows about all our tables.

# --- Base Models (No dependencies or few dependencies) ---
from .user import User
from .oauth import OAuthAccount
from .course import Course
from .video import Video
from .bank_account import BankAccount
from .quiz import Answer, Option, Question, Quiz

# --- Dependent Models (Have relationships to base models) ---
from .enrollment import Enrollment, EnrollmentApplication
from .payment import Payment, PaymentProof
from .video_progress import VideoProgress
from .assignment import Assignment, AssignmentSubmission
from .certificate import Certificate
from .course_feedback import CourseFeedback
from .course_progress import CourseProgress
from .notification import Notification
from .password_reset import PasswordReset
from .profile import Profile
from .quiz_audit_log import QuizAuditLog
from .quiz import QuizSubmission

print("All models imported successfully into models package in correct order.")