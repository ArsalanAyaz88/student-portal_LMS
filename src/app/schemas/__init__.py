# src/app/schemas/__init__.py

# First, import all the schema modules that have dependencies on each other.
# This ensures that all Pydantic models are defined before we try to resolve
# the forward references.
# A safe import order is established here to prevent circular dependency errors during initialization.
# Modules with fewer dependencies are imported first.
from . import user, quiz, video, course, submission, enrollment

# Now that all modules are loaded and all models are defined, we can safely
# call model_rebuild() on the models that contain forward references ('str' type hints).
# This is the standard Pydantic v2 approach to resolving circular dependencies.

# Rebuild models in video.py
video.VideoRead.model_rebuild()
video.VideoWithProgress.model_rebuild()

# Rebuild models in quiz.py
quiz.QuizRead.model_rebuild()
quiz.QuizReadWithDetails.model_rebuild()
quiz.QuizListRead.model_rebuild()
quiz.QuizSubmissionRead.model_rebuild()
quiz.QuizSubmissionReadWithStudent.model_rebuild()
quiz.QuizSubmissionReadWithDetails.model_rebuild()

# Rebuild models in course.py
course.CourseRead.model_rebuild()
course.CourseReadWithProgress.model_rebuild()
course.CourseReadWithSections.model_rebuild()

# Rebuild models in user.py
user.UserRead.model_rebuild()
