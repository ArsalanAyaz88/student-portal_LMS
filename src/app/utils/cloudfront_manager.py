"""
CloudFront URL Manager for Fast Video Streaming

This module provides functions to generate optimized CloudFront URLs for instant video playback.
"""
import os
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class CloudFrontManager:
    def __init__(self):
        """Initialize CloudFront configuration for fast video delivery"""
        self.domain = os.getenv('CLOUDFRONT_DOMAIN', 'd1x3zj6gsrmrll.cloudfront.net')
        self.s3_bucket_name = os.getenv('S3_BUCKET_NAME', 'sabiry')
        
    def get_cloudfront_url(self, s3_url):
        """
        Convert S3 URL to CloudFront URL for faster delivery
        
        Args:
            s3_url (str): The S3 URL to convert
            
        Returns:
            str: CloudFront URL for instant playback
        """
        try:
            if not s3_url or not self.domain:
                logger.warning("Missing CloudFront domain or S3 URL")
                return s3_url
                
            # Parse the S3 URL to extract the object key
            parsed = urlparse(s3_url)
            
            # Handle different S3 URL formats
            if self.s3_bucket_name in parsed.netloc:
                # Format: https://sabiry.s3.amazonaws.com/path/to/video.mp4
                path = parsed.path.lstrip('/')
            elif 's3.amazonaws.com' in parsed.netloc:
                # Format: https://s3.amazonaws.com/sabiry/path/to/video.mp4
                path_parts = parsed.path.lstrip('/').split('/', 1)
                if len(path_parts) > 1 and path_parts[0] == self.s3_bucket_name:
                    path = path_parts[1]
                else:
                    path = parsed.path.lstrip('/')
            else:
                # Fallback: use the path as-is
                path = parsed.path.lstrip('/')
            
            # Construct CloudFront URL for instant delivery
            cloudfront_url = f"https://{self.domain}/{path}"
            
            logger.info(f"Converted S3 URL to CloudFront: {s3_url} -> {cloudfront_url}")
            return cloudfront_url
            
        except Exception as e:
            logger.error(f"Error generating CloudFront URL: {str(e)}")
            return s3_url

# Create a singleton instance
cloudfront_manager = CloudFrontManager()

def get_optimized_video_response(video_url):
    """
    Get optimized video response with CloudFront URL for instant playback
    
    Args:
        video_url (str): Original S3 video URL
        
    Returns:
        dict: Dictionary containing optimized CloudFront URL and CDN status
    """
    try:
        if not video_url:
            return {
                'url': '',
                'cdn_enabled': False,
                'optimization': 'no_url'
            }
            
        # Get CloudFront URL for faster delivery
        cdn_url = cloudfront_manager.get_cloudfront_url(video_url)
        
        # Check if CloudFront optimization was applied
        cdn_enabled = cdn_url != video_url and 'cloudfront.net' in cdn_url
        
        return {
            'url': cdn_url,
            'cdn_enabled': cdn_enabled,
            'optimization': 'cloudfront_enabled' if cdn_enabled else 'direct_s3',
            'original_url': video_url
        }
        
    except Exception as e:
        logger.error(f"Error optimizing video URL: {str(e)}")
        return {
            'url': video_url,
            'cdn_enabled': False,
            'optimization': 'error_fallback',
            'error': str(e)
        }
