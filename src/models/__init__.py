"""
This module imports all the models to make them accessible under the app.models
namespace and to ensure they are registered with SQLModel's metadata.
"""
from .assignment import Assignment, AssignmentSubmission
from .bank_account import BankAccount
from .certificate import Certificate
from .course import Course
from .course_feedback import CourseFeedback
from .course_progress import CourseProgress
from .enrollment import Enrollment
from .enrollment_application import EnrollmentApplication
from .notification import Notification
from .oauth import OAuthAccount
from .password_reset import PasswordReset
from .payment import Payment
from .payment_proof import PaymentProof
from .profile import Profile
from .quiz import Answer, Option, Question, Quiz, QuizSubmission
from .quiz_audit_log import QuizAuditLog
from .user import User
from .video import Video
from .video_progress import VideoProgress
 