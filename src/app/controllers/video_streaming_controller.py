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

import os
from ..db.session import get_db
from ..models.user import User
from ..models.video import Video
from ..models.enrollment import Enrollment
from ..models.course import Course
from ..utils.dependencies import get_current_user
from ..utils.cloudfront_setup import generate_signed_cookies

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Video Streaming"])

@router.get("/videos/{video_id}/hls-stream")
async def stream_hls_video(
    video_id: uuid.UUID,
    response: Response,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db)
):
    """
    Securely serves HLS video streams by setting signed CloudFront cookies
    and redirecting to the HLS manifest.
    """
    try:
        # Validate video exists
        video = session.exec(select(Video).where(Video.id == video_id)).first()
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

        if not enrollment or not enrollment.is_accessible:
            raise HTTPException(status_code=403, detail="You do not have access to this course.")

        if not video.public_id:
            raise HTTPException(status_code=500, detail="Video is not configured for streaming.")

        # Define the resource path for the HLS stream
        # This assumes HLS files are in 'hls/<video_public_id>/'
        resource_path = f"hls/{video.public_id}/*"
        manifest_url = f"https://{os.getenv('CLOUDFRONT_DOMAIN')}/hls/{video.public_id}/playlist.m3u8"

        # Generate and set signed cookies
        cookies = generate_signed_cookies(resource_path)
        for key, value in cookies.items():
            response.set_cookie(
                key=key,
                value=str(value),
                domain=cookies["Domain"],
                expires=cookies["Expires"],
                httponly=True,
                secure=True,  # Use True in production
                samesite='strict'
            )
        
        # Redirect to the HLS manifest URL
        return RedirectResponse(url=manifest_url)

    except ValueError as e:
        logger.error(f"CloudFront configuration error for HLS stream: {e}")
        raise HTTPException(status_code=500, detail="Streaming service is not configured.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing HLS stream for video {video_id}: {e}")
        raise HTTPException(status_code=500, detail="Could not process video stream request.")

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
