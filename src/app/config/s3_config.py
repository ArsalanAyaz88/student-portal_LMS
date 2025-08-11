import boto3
import os
import logging
from dotenv import load_dotenv
from botocore.exceptions import NoCredentialsError, ClientError
from botocore.client import Config

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')

# Check for missing required configuration
missing_vars = []
if not AWS_ACCESS_KEY_ID:
    missing_vars.append('AWS_ACCESS_KEY_ID')
if not AWS_SECRET_ACCESS_KEY:
    missing_vars.append('AWS_SECRET_ACCESS_KEY')
if not S3_BUCKET_NAME:
    missing_vars.append('S3_BUCKET_NAME')
if not AWS_REGION:
    missing_vars.append('AWS_REGION')

if missing_vars:
    logger.error(f"Missing required AWS S3 configuration: {', '.join(missing_vars)}")
    logger.error("Please set these environment variables in your .env file")
    s3_client = None
else:
    # Initialize S3 client
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
            config=Config(s3={'use_accelerate_endpoint': True})
        )
        
        # Test the connection
        s3_client.head_bucket(Bucket=S3_BUCKET_NAME)
        logger.info(f"S3 client initialized successfully for bucket: {S3_BUCKET_NAME}")
        
    except NoCredentialsError:
        logger.error("AWS credentials not found. Please check your environment variables.")
        s3_client = None
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchBucket':
            logger.error(f"S3 bucket '{S3_BUCKET_NAME}' does not exist in region '{AWS_REGION}'")
        elif error_code == 'AccessDenied':
            logger.error(f"Access denied to S3 bucket '{S3_BUCKET_NAME}'. Check IAM permissions.")
        else:
            logger.error(f"S3 client error: {str(e)}")
        s3_client = None
    except Exception as e:
        logger.error(f"Failed to initialize S3 client: {str(e)}")
        s3_client = None 