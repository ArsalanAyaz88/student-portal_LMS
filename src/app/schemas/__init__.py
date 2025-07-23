# src/app/schemas/__init__.py

# First, import the modules that contain the Pydantic models.
# This allows Python to be aware of all modules before we try to resolve the dependencies.
from . import course
from . import video
from . import quiz

# Now that all modules are loaded, we can safely call model_rebuild()
# on the models that have forward references ('str' type hints) to other models.
# This resolves the circular dependencies.
video.VideoRead.model_rebuild()
video.VideoWithProgress.model_rebuild()
quiz.QuizRead.model_rebuild()
course.CourseRead.model_rebuild()