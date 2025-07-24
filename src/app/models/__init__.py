"""
This module imports all the models to make them accessible under the app.models
namespace and to ensure they are registered with SQLModel's metadata.
"""
# This file ensures that all models are imported and registered with SQLModel's metadata.
# By importing them here, we can avoid circular import errors in other parts of the app
# and ensure that `create_db_and_tables` knows about all our tables.

from .user import User, OAuthAccount
from .course import Course
from .video import Video, VideoProgress
from .enrollment import Enrollment, EnrollmentApplication
from .payment import PaymentProof
from .bank_account import BankAccount
from .assignment import Assignment, AssignmentSubmission
from .certificate import Certificate
from .course_feedback import CourseFeedback
from .course_progress import CourseProgress
from .notification import Notification
from .password_reset import PasswordReset
from .payment import Payment
from .profile import Profile
from .quiz import Answer, Option, Question, Quiz, QuizSubmission
from .quiz_audit_log import QuizAuditLog

print("All models imported successfully into models package.")