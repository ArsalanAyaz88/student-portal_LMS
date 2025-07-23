# File: app/schemas/__init__.py

from .video import VideoRead
from .quiz import QuizRead
from .course import CourseRead

# Resolve forward references to break circular dependencies
VideoRead.model_rebuild()
QuizRead.model_rebuild()
CourseRead.model_rebuild()