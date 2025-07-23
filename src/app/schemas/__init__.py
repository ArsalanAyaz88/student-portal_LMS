 # File: app/schemas/__init__.py

from . import course, enrollment_application_schema, quiz, user, video

# Resolve forward references for Pydantic models
course.CourseExploreDetail.model_rebuild()
course.CourseDetail.model_rebuild()
enrollment_application_schema.EnrollmentApplicationRead.model_rebuild()
video.VideoRead.model_rebuild()
video.VideoWithProgress.model_rebuild()