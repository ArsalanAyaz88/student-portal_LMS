from fastapi import APIRouter, UploadFile, File, HTTPException
from src.app.utils.cloudinary_uploader import upload_file_to_cloudinary
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/uploads",
    tags=["uploads"],
)

@router.post("/certificate", summary="Upload an enrollment certificate and get URL")
async def upload_certificate(file: UploadFile = File(...)):
    """
    Uploads a certificate file to Cloudinary into the 'certificates' folder 
    and returns the secure URL.
    """
    if not file.content_type.startswith('image/') and file.content_type != 'application/pdf':
        raise HTTPException(status_code=400, detail="Invalid file type. Only images and PDFs are allowed.")

    try:
        logger.info(f"Uploading certificate: {file.filename}")
        file_url = await upload_file_to_cloudinary(file, 'certificates')
        logger.info(f"Certificate uploaded successfully. URL: {file_url}")
        return {"file_url": file_url}
    except Exception as e:
        logger.error(f"Certificate upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Could not upload certificate: {str(e)}")


@router.post("/payment-proof", summary="Upload a payment proof and get URL")
async def upload_payment_proof(file: UploadFile = File(...)):
    """
    Uploads a payment proof file to Cloudinary into the 'payment_proofs' folder 
    and returns the secure URL.
    """
    if not file.content_type.startswith('image/') and file.content_type != 'application/pdf':
        raise HTTPException(status_code=400, detail="Invalid file type. Only images and PDFs are allowed.")

    try:
        logger.info(f"Uploading payment proof: {file.filename}")
        file_url = await upload_file_to_cloudinary(file, 'payment_proofs')
        logger.info(f"Payment proof uploaded successfully. URL: {file_url}")
        return {"file_url": file_url}
    except Exception as e:
        logger.error(f"Payment proof upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Could not upload payment proof: {str(e)}")

