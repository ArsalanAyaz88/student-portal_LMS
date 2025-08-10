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
from ..utils.cloudfront_manager import get_optimized_video_response
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
        
        # Get optimized CloudFront URL for faster delivery
        optimized_response = get_optimized_video_response(video.cloudinary_url)
        optimized_url = optimized_response['url']
        
        # Log the optimization status
        if optimized_response['cdn_enabled']:
            logger.info(f"Serving video {video_id} via CloudFront CDN for faster delivery")
        else:
            logger.info(f"Serving video {video_id} directly from S3 (CloudFront fallback)")
        
        # Handle range requests for smooth streaming
        range_header = request.headers.get('range')
        
        # Temporarily disable CloudFront check
        if False:  # optimized_response['cdn_enabled']:
            # For CloudFront URLs, redirect with optimized headers
            response = RedirectResponse(
                url=optimized_url,
                status_code=302  # Temporary redirect to preserve range requests
            )
            
            # Add security headers to prevent download managers
            response.headers.update({
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "no-referrer",
                "X-Download-Options": "noopen",
                "X-Permitted-Cross-Domain-Policies": "none",
                "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
                "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                "Access-Control-Allow-Headers": "Range, Content-Type, Authorization"
            })
            
            return response
        else:
            # Fallback: Direct S3 streaming with security headers
            return await stream_from_s3_with_security(
                video.cloudinary_url, 
                range_header, 
                request
            )
            
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
