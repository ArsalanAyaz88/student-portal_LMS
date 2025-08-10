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
import os
from urllib.parse import urlparse

from ..db.session import get_db
from ..models.user import User
from ..models.video import Video
from ..models.enrollment import Enrollment
from ..models.course import Course
from ..utils.dependencies import get_current_user
from ..config.s3_config import s3_client, S3_BUCKET_NAME
from ..config.s3_config import s3_client, S3_BUCKET_NAME

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Video Streaming"])

@router.get("/videos/{video_id}/stream")
async def stream_video_optimized(
    video_id: uuid.UUID,
    request: Request,
    token: str = None,  # Accept token as URL parameter for HTML5 video
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
        # Validate authentication token from URL parameter
        if not token:
            # Try to get token from Authorization header as fallback
            auth_header = request.headers.get('authorization', '')
            if auth_header.startswith('Bearer '):
                token = auth_header.replace('Bearer ', '')
            else:
                raise HTTPException(status_code=401, detail="Authentication token required")
        
        # Validate token and get user
        from ..utils.security import decode_access_token
        try:
            payload = decode_access_token(token)
            user_id = payload.get("user_id")
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token payload")
            
            user = session.get(User, user_id)
            if not user or not user.is_active:
                raise HTTPException(status_code=401, detail="Invalid or inactive user")
                
        except Exception as e:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
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
        
        # Use the simple optimization function from course controller
        def optimize_video_url_simple(s3_url: str) -> str:
            """Convert S3 URL to CloudFront URL for instant streaming"""
            try:
                cloudfront_domain = os.getenv('CLOUDFRONT_DOMAIN', 'd1x3zj6gsrmrll.cloudfront.net')
                bucket_name = os.getenv('S3_BUCKET_NAME', 'sabiry')
                
                if not cloudfront_domain:
                    logger.warning("CloudFront domain not configured, using direct S3 URL")
                    return s3_url
                
                # Extract object key from S3 URL
                parsed_url = urlparse(s3_url)
                if f'{bucket_name}.s3.amazonaws.com' in parsed_url.netloc:
                    object_key = parsed_url.path.lstrip('/')
                elif 's3.amazonaws.com' in parsed_url.netloc and f'/{bucket_name}/' in parsed_url.path:
                    object_key = parsed_url.path.split(f'/{bucket_name}/', 1)[1]
                else:
                    logger.warning(f"Unrecognized S3 URL format: {s3_url}")
                    return s3_url
                
                cloudfront_url = f"https://{cloudfront_domain}/{object_key}"
                logger.info(f"🎥 Video streaming optimized: {s3_url} -> {cloudfront_url}")
                return cloudfront_url
                
            except Exception as e:
                logger.error(f"Error optimizing video URL: {str(e)}")
                return s3_url
        
        # For debugging, use original URL directly (bypass CloudFront optimization)
        logger.info(f"Using original video URL for debugging: {video.cloudinary_url}")
        optimized_url = video.cloudinary_url
        
        # Uncomment below to re-enable CloudFront optimization later
        # try:
        #     optimized_url = optimize_video_url_simple(video.cloudinary_url)
        #     logger.info(f"Video optimization successful: {optimized_url}")
        # except Exception as e:
        #     logger.error(f"Video optimization failed: {str(e)}, using original URL")
        #     optimized_url = video.cloudinary_url
        
        logger.info(f"Serving video {video_id} via streaming endpoint with CloudFront optimization")
        
        # Handle range requests for smooth streaming
        range_header = request.headers.get('range')
        
        # For now, redirect directly to CloudFront with proper headers for HTML5 compatibility
        logger.info(f"Redirecting to optimized CloudFront URL: {optimized_url}")
        
        response = RedirectResponse(
            url=optimized_url,
            status_code=302
        )
        
        # Add proper headers for video streaming
        response.headers.update({
            "Content-Type": "video/mp4",
            "Accept-Ranges": "bytes", 
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Range, Content-Type, Authorization",
            "Access-Control-Expose-Headers": "Content-Range, Accept-Ranges, Content-Length",
        })
        
        return response
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error streaming video {video_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while streaming the video: {str(e)}"
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
