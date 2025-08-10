# File location: src/app/schemas/payment_proof.py
from pydantic import BaseModel
from typing import Optional

class ProofCreate(BaseModel):
    proof_url: Optional[str] = None  # For legacy or fallback
    # We'll use file upload in the endpoint, so this field is optional
    