# File: application/src/app/schemas/assignment.py

from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime

class AssignmentCreate(BaseModel):
    course_id: UUID
    title: str
    description: str
    due_date: datetime

class AssignmentRead(BaseModel):
    id: UUID
    course_id: UUID
    title: str
    description: str
    due_date: datetime

    class Config:
        orm_mode = True
        from_attributes = True

class AssignmentList(BaseModel):
    id: UUID
    title: str
    due_date: datetime

    class Config:
        orm_mode = True
        from_attributes = True

class SubmissionCreate(BaseModel):
    # a string URL or path to the uploaded file
    content_url: str

class SubmissionRead(BaseModel):
    id: UUID
    assignment_id: UUID
    student_id: UUID
    submitted_at: datetime
    content_url: str
    grade: Optional[float]
    feedback: Optional[str]

    class Config:
        orm_mode = True
        from_attributes = True

class SubmissionResponse(BaseModel):
    message: str
    submission: SubmissionRead

    class Config:
        orm_mode = True
        from_attributes = True

class SubmissionGrade(BaseModel):
    grade: float
    feedback: Optional[str] = None

class SubmissionStudent(BaseModel):
    id: UUID
    student_id: UUID
    email: str
    full_name: Optional[str]
    submitted_at: datetime
    content_url: str
    grade: Optional[float]
    feedback: Optional[str]
    class Config:
        orm_mode = True
        from_attributes = True

class SubmissionStudentsResponse(BaseModel):
    assignment: AssignmentRead
    submissions: List[SubmissionStudent]

    class Config:
        orm_mode = True
        from_attributes = True
