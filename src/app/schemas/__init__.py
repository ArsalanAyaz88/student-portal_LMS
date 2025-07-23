# src/app/schemas/__init__.py

# Import all schema modules to ensure all models are loaded.
from . import video, quiz, course, user, submission, enrollment

# Now that all modules are loaded, rebuild the models that contain
# forward string references to resolve them.
# This is the standard Pydantic v2 approach.

# Rebuild models from video.py
video.VideoRead.model_rebuild()
video.VideoWithProgress.model_rebuild()

# Rebuild models from quiz.py
# (Even if they don't have forward refs to other files, it's safe to rebuild)
quiz.QuizRead.model_rebuild()
quiz.QuizReadWithDetails.model_rebuild()

# Rebuild models from course.py
course.CourseRead.model_rebuild()
course.CourseReadWithSections.model_rebuild()

# Rebuild models from user.py
user.UserRead.model_rebuild()
