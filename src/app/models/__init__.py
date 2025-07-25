# src/app/models/__init__.py

# This file centralizes all model imports, ensuring that SQLAlchemy's metadata
# is aware of every table before any operations are performed. This is the
# definitive solution to prevent mapper initialization and 'Table not found' errors.

# --- Base Models (Fewest dependencies) ---
from .user import User
from .profile import Profile
from .oauth import OAuthAccount
from .password_reset import PasswordReset
from .bank_account import BankAccount

# --- Course-related Models ---
from .course import Course
from .video import Video
from .assignment import Assignment
from .quiz import Quiz, Question, Option

# --- User Activity and Enrollment Models (Dependent on User and Course) ---
from .enrollment import Enrollment, EnrollmentApplication
from .course_progress import CourseProgress
from .video_progress import VideoProgress
from .quiz_audit_log import QuizAuditLog
from .course_feedback import CourseFeedback

# --- Payment and Notification Models ---
from .payment import PaymentProof
from .notification import Notification
from .certificate import Certificate


# The __all__ list defines the public API for the 'models' package.
__all__ = [
    "User",
    "Profile",
    "OAuthAccount",
    "PasswordReset",
    "BankAccount",
    "Course",
    "Video",
    "Assignment",
    "Quiz",
    "Question",
    "Option",
    "Enrollment",
    "EnrollmentApplication",
    "CourseProgress",
    "VideoProgress",
    "QuizAuditLog",
    "CourseFeedback",
    "PaymentProof",
    "Notification",
    "Certificate",
]

# --- Configure Model Relationships After Import ---
# This eliminates circular dependency issues by configuring relationships
# with direct class references instead of string-based forward references.
from sqlmodel import Relationship

# Configure EnrollmentApplication relationships
EnrollmentApplication.user = Relationship(back_populates="enrollment_applications")
EnrollmentApplication.course = Relationship(back_populates="enrollment_applications")

# Configure Enrollment relationships  
Enrollment.user = Relationship(back_populates="enrollments")
Enrollment.course = Relationship(back_populates="enrollments")