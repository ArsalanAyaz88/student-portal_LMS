"""
AWS CloudFront Distribution Setup for Video Streaming Optimization

This script creates a CloudFront distribution for your S3 bucket to enable:
- Global edge caching for faster video loading
- Byte-range request support for better streaming
- Reduced latency and improved user experience
"""

import boto3
import json
import logging
import os
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from botocore.signers import CloudFrontSigner
from ..config.s3_config import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_NAME

logger = logging.getLogger(__name__)

class CloudFrontManager:
    def __init__(self):
        """Initialize CloudFront client"""
        self.cloudfront_client = boto3.client(
            'cloudfront',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        self.s3_bucket_name = S3_BUCKET_NAME
    
    def create_distribution(self):
        """
        Create CloudFront distribution optimized for video streaming
        """
        try:
            # CloudFront distribution configuration optimized for video streaming
            distribution_config = {
                'CallerReference': f'lms-video-distribution-{S3_BUCKET_NAME}',
                'Comment': f'LMS Video Streaming Distribution for {S3_BUCKET_NAME}',
                'DefaultRootObject': '',
                'Origins': {
                    'Quantity': 1,
                    'Items': [
                        {
                            'Id': f'{S3_BUCKET_NAME}-origin',
                            'DomainName': f'{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com',
                            'S3OriginConfig': {
                                'OriginAccessIdentity': ''
                            }
                        }
                    ]
                },
                'DefaultCacheBehavior': {
                    'TargetOriginId': f'{S3_BUCKET_NAME}-origin',
                    'ViewerProtocolPolicy': 'redirect-to-https',
                    'MinTTL': 0,
                    'DefaultTTL': 86400,  # 24 hours
                    'MaxTTL': 31536000,   # 1 year
                    'ForwardedValues': {
                        'QueryString': True,
                        'Cookies': {
                            'Forward': 'none'
                        },
                        'Headers': {
                            'Quantity': 3,
                            'Items': ['Range', 'Origin', 'Access-Control-Request-Method']
                        }
                    },
                    'TrustedSigners': {
                        'Enabled': False,
                        'Quantity': 0
                    },
                    'Compress': True,
                    'AllowedMethods': {
                        'Quantity': 7,
                        'Items': ['GET', 'HEAD', 'OPTIONS', 'PUT', 'POST', 'PATCH', 'DELETE'],
                        'CachedMethods': {
                            'Quantity': 2,
                            'Items': ['GET', 'HEAD']
                        }
                    }
                },
                'CacheBehaviors': {
                    'Quantity': 1,
                    'Items': [
                        {
                            'PathPattern': 'videos/*',
                            'TargetOriginId': f'{S3_BUCKET_NAME}-origin',
                            'ViewerProtocolPolicy': 'redirect-to-https',
                            'MinTTL': 0,
                            'DefaultTTL': 86400,
                            'MaxTTL': 31536000,
                            'ForwardedValues': {
                                'QueryString': True,
                                'Cookies': {
                                    'Forward': 'none'
                                },
                                'Headers': {
                                    'Quantity': 4,
                                    'Items': ['Range', 'Origin', 'Access-Control-Request-Method', 'Authorization']
                                }
                            },
                            'TrustedSigners': {
                                'Enabled': False,
                                'Quantity': 0
                            },
                            'Compress': False,  # Don't compress videos
                            'AllowedMethods': {
                                'Quantity': 3,
                                'Items': ['GET', 'HEAD', 'OPTIONS'],
                                'CachedMethods': {
                                    'Quantity': 2,
                                    'Items': ['GET', 'HEAD']
                                }
                            }
                        }
                    ]
                },
                'Enabled': True,
                'PriceClass': 'PriceClass_All'
            }
            
            # Create the distribution
            response = self.cloudfront_client.create_distribution(
                DistributionConfig=distribution_config
            )
            
            distribution_id = response['Distribution']['Id']
            domain_name = response['Distribution']['DomainName']
            
            logger.info(f"CloudFront distribution created successfully!")
            logger.info(f"Distribution ID: {distribution_id}")
            logger.info(f"Domain Name: {domain_name}")
            logger.info(f"Status: {response['Distribution']['Status']}")
            
            return {
                'distribution_id': distribution_id,
                'domain_name': domain_name,
                'status': response['Distribution']['Status']
            }
            
        except ClientError as e:
            logger.error(f"Error creating CloudFront distribution: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
    
    def get_distribution_status(self, distribution_id):
        """
        Check the status of a CloudFront distribution
        """
        try:
            response = self.cloudfront_client.get_distribution(Id=distribution_id)
            return {
                'id': distribution_id,
                'status': response['Distribution']['Status'],
                'domain_name': response['Distribution']['DomainName'],
                'enabled': response['Distribution']['DistributionConfig']['Enabled']
            }
        except ClientError as e:
            logger.error(f"Error getting distribution status: {e}")
            raise
    
    def list_distributions(self):
        """
        List all CloudFront distributions
        """
        try:
            response = self.cloudfront_client.list_distributions()
            distributions = []
            
            if 'Items' in response['DistributionList']:
                for dist in response['DistributionList']['Items']:
                    distributions.append({
                        'id': dist['Id'],
                        'domain_name': dist['DomainName'],
                        'status': dist['Status'],
                        'enabled': dist['Enabled'],
                        'comment': dist.get('Comment', '')
                    })
            
            return distributions
        except ClientError as e:
            logger.error(f"Error listing distributions: {e}")
            raise

def setup_cloudfront_for_lms():
    """
    Main function to set up CloudFront for LMS video streaming
    """
    try:
        cf_manager = CloudFrontManager()
        
        # Check if distribution already exists
        existing_distributions = cf_manager.list_distributions()
        lms_distribution = None
        
        for dist in existing_distributions:
            if S3_BUCKET_NAME in dist.get('comment', ''):
                lms_distribution = dist
                logger.info(f"Found existing LMS distribution: {dist['id']}")
                break
        
        if lms_distribution:
            logger.info("Using existing CloudFront distribution")
            return lms_distribution
        else:
            logger.info("Creating new CloudFront distribution...")
            return cf_manager.create_distribution()
            
    except Exception as e:
        logger.error(f"Failed to set up CloudFront: {e}")
        raise

def rsa_signer(message, key):
    private_key = serialization.load_pem_private_key(
        key.encode(),
        password=None,
    )
    return private_key.sign(message, padding.PKCS1v15(), hashes.SHA1())

def generate_signed_cloudfront_url(resource_key: str) -> str:
    """
    Generates a signed URL for a CloudFront resource.
    """
    cloudfront_domain = os.getenv('CLOUDFRONT_DOMAIN')
    key_id = os.getenv('CLOUDFRONT_KEY_PAIR_ID')
    private_key = os.getenv('CLOUDFRONT_PRIVATE_KEY')

    if not all([cloudfront_domain, key_id, private_key]):
        logger.error("CloudFront environment variables for signing are not fully configured.")
        raise ValueError("CloudFront is not configured for signing URLs.")

    resource_url = f"https://{cloudfront_domain}/{resource_key}"
    expire_date = datetime.utcnow() + timedelta(hours=1)  # URL is valid for 1 hour

    cloudfront_signer = CloudFrontSigner(key_id, rsa_signer)

    signed_url = cloudfront_signer.generate_presigned_url(
        resource_url, date_less_than=expire_date
    )
    return signed_url

if __name__ == "__main__":
    # Run the setup
    result = setup_cloudfront_for_lms()
    print(f"CloudFront setup complete: {json.dumps(result, indent=2)}")
