# File: application/src/app/utils/file.py
import os
import uuid
import logging
from typing import Optional
import asyncio
import functools
from io import BytesIO

from fastapi import UploadFile, HTTPException, status
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Import S3 configuration
from ..config.s3_config import s3_client, S3_BUCKET_NAME

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# File logging to a specific path is disabled for the serverless environment.
# The logger will now output to stdout/stderr, which is captured by Vercel.

async def upload_file_to_s3(file_obj, key: str, content_type: Optional[str] = None) -> str:
    """
    Upload file to AWS S3.
    
    Args:
        file_obj: File-like object containing the data
        key: The S3 key (path) for the uploaded file
        content_type: Optional content type for the file
        
    Returns:
        str: URL to the uploaded file
    """
    try:
        # Check if S3 client is properly initialized
        if s3_client is None:
            logger.error("S3 client is not initialized. Check your AWS configuration.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="S3 service is not configured properly. Please check AWS credentials and bucket settings."
            )
        
        # Reset file pointer to beginning
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
        
        # Upload the file using upload_fileobj
        loop = asyncio.get_event_loop()
        
        # For upload_fileobj, we pass the file object directly, not as a parameter
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type

        upload_func = functools.partial(
            s3_client.upload_fileobj, 
            file_obj, 
            S3_BUCKET_NAME, 
            key, 
            ExtraArgs=extra_args
        )
        await loop.run_in_executor(None, upload_func)

        # Generate the URL using the client's endpoint to ensure region-correctness
        url = f"{s3_client.meta.endpoint_url}/{S3_BUCKET_NAME}/{key}"
        
        logger.debug(f"Successfully uploaded file to S3: {url}")
        return url
        
    except NoCredentialsError:
        logger.error("AWS credentials not found")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AWS credentials not configured. Please check your environment variables."
        )
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchBucket':
            logger.error(f"S3 bucket '{S3_BUCKET_NAME}' does not exist")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"S3 bucket '{S3_BUCKET_NAME}' does not exist. Please check your bucket configuration."
            )
        elif error_code == 'AccessDenied':
            logger.error(f"Access denied to S3 bucket '{S3_BUCKET_NAME}'")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Access denied to S3 bucket '{S3_BUCKET_NAME}'. Please check your IAM permissions."
            )
        else:
            logger.error(f"S3 upload failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file to S3: {str(e)}"
            )
    except Exception as e:
        logger.error(f"S3 upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to S3: {str(e)}"
        )

async def save_upload_and_get_url(file: UploadFile, folder: str = "") -> str:
    """
    Upload the file to S3 and return the URL.
    
    Args:
        file: UploadFile object from FastAPI
        folder: Optional folder path in S3
        
    Returns:
        str: URL to the uploaded file
    """
    try:
        # Validate S3 configuration first
        if s3_client is None:
            logger.error("S3 client is not initialized")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="File upload service is not configured. Please check AWS S3 configuration."
            )
        
        if not S3_BUCKET_NAME:
            logger.error("S3 bucket name is not configured")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="S3 bucket name is not configured. Please check your environment variables."
            )
        
        # Generate a unique filename
        ext = os.path.splitext(file.filename)[1].lower()
        file_id = uuid.uuid4().hex
        filename = f"{file_id}{ext}"
        
        # Create the S3 key (path)
        if folder:
            key = f"{folder.rstrip('/')}/{filename}"
        else:
            key = filename
        
        # Read file content
        file_content = await file.read()
        file_obj = BytesIO(file_content)
        
        # Upload the file
        return await upload_file_to_s3(file_obj, key, file.content_type)
        
    except Exception as e:
        logger.error(f"Error processing file upload: {str(e)}")
        if not isinstance(e, HTTPException):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process file upload: {str(e)}"
            )
        raise
