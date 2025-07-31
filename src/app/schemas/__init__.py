# src/app/schemas/__init__.py

# Import all the necessary models directly into this namespace.
# This creates a shared namespace where all models can find each other.
from .video import VideoRead
from .quiz import QuizRead, QuizReadWithDetails
from .course import CourseRead
from .user import UserRead

# Now, rebuild each model that has a forward reference.
# We pass `_types_namespace=globals()` to tell Pydantic to use the
# current (shared) namespace to find the string references like 'QuizRead'.

VideoRead.model_rebuild(_types_namespace=globals())
QuizRead.model_rebuild(_types_namespace=globals())
QuizReadWithDetails.model_rebuild(_types_namespace=globals())
CourseRead.model_rebuild(_types_namespace=globals()) 
UserRead.model_rebuild(_types_namespace=globals())

