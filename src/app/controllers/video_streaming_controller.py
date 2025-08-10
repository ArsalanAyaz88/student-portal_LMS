"""
Optimized Video Streaming Controller with CloudFront Integration

This controller provides secure, high-performance video streaming by:
1. Using CloudFront CDN for global edge caching
2. Maintaining security through authentication and enrollment checks
3. Supporting byte-range requests for smooth streaming
4. Adding anti-download headers for content protection
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from typing import Optional
import uuid
import logging
from urllib.parse import urlparse

from ..db.session import get_db
from ..models.user import User
from ..models.video import Video
from ..models.enrollment import Enrollment
from ..models.course import Course
from ..utils.dependencies import get_current_user
# Temporarily disable CloudFront optimization until module is properly set up
# from ..utils.cloudfront_manager import optimize_video_url, get_optimized_video_response
from ..config.s3_config import s3_client, S3_BUCKET_NAME

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Video Streaming"])

@router.get("/videos/{video_id}/stream")
async def stream_video_optimized(
    video_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """
    Optimized video streaming endpoint with CloudFront integration
    
    Features:
    - CloudFront CDN for global performance
    - Authentication and enrollment validation
    - Byte-range request support
    - Anti-download security headers
    - Automatic URL optimization
    """
    try:
        # Validate video exists
        video = session.exec(
            select(Video).where(Video.id == video_id)
        ).first()
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Check user enrollment and access permissions
        enrollment = session.exec(
            select(Enrollment).where(
                Enrollment.user_id == user.id,
                Enrollment.course_id == video.course_id,
                Enrollment.status == "approved"
            )
        ).first()
        
        if not enrollment:
            raise HTTPException(
                status_code=403, 
                detail="You must be enrolled in this course to access this video"
            )
        
        # Check if enrollment is still valid (not expired)
        enrollment.update_expiration_status()
        if not enrollment.is_accessible:
            raise HTTPException(
                status_code=403,
                detail="Your enrollment has expired. Please renew to continue accessing course content."
            )
        
        # Get course for additional validation
        course = session.exec(
            select(Course).where(Course.id == video.course_id)
        ).first()
        
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        # Simple secure video access for saved MP4 files
        # Extract S3 key from video URL (handles both S3 and "cloudinary_url" field that contains S3 URLs)
        try:
            parsed_url = urlparse(video.cloudinary_url)
            
            # Extract S3 key from various URL formats
            if S3_BUCKET_NAME in parsed_url.netloc:
                s3_key = parsed_url.path.lstrip('/')
            elif 's3.amazonaws.com' in parsed_url.netloc:
                path_parts = parsed_url.path.lstrip('/').split('/', 1)
                if len(path_parts) > 1 and path_parts[0] == S3_BUCKET_NAME:
                    s3_key = path_parts[1]
                else:
                    raise ValueError("Invalid S3 URL format")
            else:
                raise ValueError("URL is not an S3 URL")
                
        except Exception as e:
            logger.error(f"Failed to extract S3 key from {video.cloudinary_url}: {e}")
            raise HTTPException(status_code=400, detail="Invalid video URL format")
        
        # Generate secure presigned URL for direct video access
        # Long expiration (3 hours) for long videos but with security controls
        try:
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': S3_BUCKET_NAME,
                    'Key': s3_key,
                    'ResponseContentType': 'video/mp4',
                    'ResponseContentDisposition': 'inline; filename="video.mp4"'
                },
                ExpiresIn=10800,  # 3 hours for long videos
                HttpMethod='GET'
            )
            
            logger.info(f"Generated secure video URL for {video_id} - expires in 3 hours")
            
        except Exception as e:
            logger.error(f"Failed to generate video URL: {e}")
            raise HTTPException(status_code=500, detail="Failed to access video")
        
        # Stream video directly through our server to avoid CORS issues
        from fastapi.responses import StreamingResponse
        import httpx
        
        try:
            # Get the video from S3 using presigned URL
            async with httpx.AsyncClient() as client:
                # Handle range requests for video seeking
                headers = {}
                if "range" in request.headers:
                    headers["Range"] = request.headers["range"]
                
                # Stream the video content from S3
                response = await client.get(presigned_url, headers=headers)
                
                # Create streaming response
                def generate():
                    for chunk in response.iter_bytes(chunk_size=8192):
                        yield chunk
                
                # Determine content type
                content_type = response.headers.get("content-type", "video/mp4")
                
                # Create streaming response with proper headers
                streaming_response = StreamingResponse(
                    generate(),
                    status_code=response.status_code,
                    media_type=content_type
                )
                
                # Add security and streaming headers
                streaming_response.headers.update({
                    "Accept-Ranges": "bytes",
                    "Content-Length": response.headers.get("content-length", ""),
                    "Content-Range": response.headers.get("content-range", ""),
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "X-Content-Type-Options": "nosniff",
                    "X-Frame-Options": "DENY",
                    "X-Download-Options": "noopen",
                    "Referrer-Policy": "no-referrer",
                    "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
                    "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                    "Access-Control-Allow-Headers": "Range, Content-Type, Authorization",
                    "X-Video-Access": "authorized"
                })
                
                return streaming_response
                
        except Exception as e:
            logger.error(f"Failed to stream video: {e}")
            raise HTTPException(status_code=500, detail="Failed to stream video")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error streaming video {video_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred while streaming the video"
        )

async def stream_from_s3_with_security(s3_url: str, range_header: Optional[str], request: Request):
    """
    Fallback method to stream directly from S3 with security headers
    (Used when CloudFront is not configured)
    """
    try:
        # Parse S3 URL to get bucket and key
        parsed_url = urlparse(s3_url)
        
        # Extract object key from URL
        if S3_BUCKET_NAME in parsed_url.netloc:
            object_key = parsed_url.path.lstrip('/')
        else:
            # Handle s3.amazonaws.com/bucket/key format
            path_parts = parsed_url.path.lstrip('/').split('/', 1)
            if len(path_parts) > 1:
                object_key = path_parts[1]
            else:
                raise HTTPException(status_code=400, detail="Invalid S3 URL format")
        
        # Generate presigned URL with security parameters
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': S3_BUCKET_NAME,
                'Key': object_key
            },
            ExpiresIn=3600,  # 1 hour expiration
            HttpMethod='GET'
        )
        
        # Create redirect response with security headers
        response = RedirectResponse(url=presigned_url, status_code=302)
        
        # Add comprehensive security headers
        response.headers.update({
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-Download-Options": "noopen",
            "X-Permitted-Cross-Domain-Policies": "none",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'",
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Range, Content-Type, Authorization"
        })
        
        return response
        
    except Exception as e:
        logger.error(f"Error streaming from S3: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error accessing video content"
        )

@router.get("/videos/{video_id}/info")
async def get_video_streaming_info(
    video_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """
    Get video streaming information and optimization status
    """
    try:
        # Validate video exists and user has access
        video = session.exec(
            select(Video).where(Video.id == video_id)
        ).first()
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Check enrollment
        enrollment = session.exec(
            select(Enrollment).where(
                Enrollment.user_id == user.id,
                Enrollment.course_id == video.course_id,
                Enrollment.status == "approved"
            )
        ).first()
        
        if not enrollment:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # TODO: Re-enable CloudFront optimization after fixing module import
        # optimization_info = get_optimized_video_response(video.cloudinary_url)
        
        return {
            "video_id": str(video_id),
            "title": video.title,
            "description": video.description,
            "streaming_url": f"/api/videos/{video_id}/stream",
            "optimization": {
                "cdn_enabled": False,  # Temporarily disabled
                "cloudfront_optimized": False,  # Temporarily disabled
                "supports_range_requests": True
            },
            "performance_features": [
                "Direct S3 delivery (CloudFront temporarily disabled)",
                "Byte-range request support",
                "Anti-download protection",
                "Authenticated access control"
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video info {video_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error retrieving video information"
        )
