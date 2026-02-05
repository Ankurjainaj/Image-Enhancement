"""
S3 Storage Service for Image Enhancement
Handles uploading/downloading images from AWS S3 with audit trail support
"""
import os
import logging
from typing import Optional, Tuple
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from urllib.parse import urlparse
from dotenv import load_dotenv
logger = logging.getLogger(__name__)

load_dotenv()

class S3Service:
    """Service for managing images in AWS S3"""
    
    def __init__(
        self,
        bucket: str,
        region: str = "ap-south-1",
        endpoint_url: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        """
        Initialize S3 service
        
        Args:
            bucket: S3 bucket name
            region: AWS region
            endpoint_url: Custom S3 endpoint (for MinIO, etc.)
            access_key: AWS access key ID
            secret_key: AWS secret access key
        """
        self.bucket = bucket
        self.region = region
        
        # Use provided credentials or environment variables
        access_key = access_key or os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = secret_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        
        try:
            if endpoint_url:
                # For custom S3-compatible services (MinIO, etc.)
                self.s3_client = boto3.client(
                    "s3",
                    region_name=region,
                    endpoint_url=endpoint_url,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                )
            else:
                # For AWS S3
                self.s3_client = boto3.client(
                    "s3",
                    region_name=region,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                )
            
            # Verify bucket exists
            self.s3_client.head_bucket(Bucket=bucket)
            logger.info(f"✅ S3 connection successful - bucket: {bucket}")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "404":
                raise ValueError(f"S3 bucket '{bucket}' not found")
            elif error_code == "403":
                raise ValueError(f"Access denied to S3 bucket '{bucket}'")
            else:
                raise Exception(f"Failed to connect to S3: {str(e)}")
    
    def upload_image(
        self,
        file_bytes: bytes,
        key: str,
        content_type: str = "image/jpeg",
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Upload image to S3
        
        Args:
            file_bytes: Image data in bytes
            key: S3 object key (path in bucket)
            content_type: MIME type
            metadata: Custom metadata dict
        
        Returns:
            S3 object URL
        """
        try:
            extra_args = {
                "ContentType": content_type,
                "ServerSideEncryption": "AES256",
            }
            
            # Add metadata if provided
            if metadata:
                extra_args["Metadata"] = {
                    str(k): str(v) for k, v in metadata.items()
                }
            
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=file_bytes,
                **extra_args,
            )
            
            s3_url = f"s3://{self.bucket}/{key}"
            logger.info(f"✅ Uploaded to S3: {s3_url}")
            return s3_url
        except ClientError as e:
            error_msg = f"Failed to upload to S3: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def download_image(self, key: str) -> bytes:
        """
        Download image from S3
        
        Args:
            key: S3 object key
        
        Returns:
            Image data in bytes
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
            file_bytes = response["Body"].read()
            logger.info(f"✅ Downloaded from S3: {key}")
            return file_bytes
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise FileNotFoundError(f"Image not found in S3: {key}")
            error_msg = f"Failed to download from S3: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def get_s3_url(self, key: str) -> str:
        """Get S3 URL for an object"""
        return f"s3://{self.bucket}/{key}"
    
    def get_https_url(self, key: str, cloudfront_domain: Optional[str] = None) -> str:
        """
        Get HTTPS URL for an object
        
        Args:
            key: S3 object key
            cloudfront_domain: Optional CloudFront domain to use instead of S3 direct
                Can be with or without https:// prefix
        
        Returns:
            HTTPS URL
        """
        # If a CloudFront domain is provided, prefer it (strip any scheme)
        # if cloudfront_domain:
        #     domain = cloudfront_domain.replace('https://', '').replace('http://', '')
        #     return f"https://{domain}/{key}"

        # Use boto3 client's endpoint to construct the HTTPS URL in a region-aware way
        try:
            endpoint = getattr(self.s3_client, 'meta').endpoint_url
            if endpoint:
                parsed = urlparse(endpoint)
                host = parsed.netloc
                # Construct virtual-hosted-style URL: https://{bucket}.{s3-host}/{key}
                return f"https://{self.bucket}.{host}/{key}"
        except Exception:
            # Fallback to deterministic format
            pass

        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"
    
    def get_presigned_url(
        self,
        key: str,
        expiration: int = 3600,
    ) -> str:
        """
        Generate presigned URL for temporary access
        
        Args:
            key: S3 object key
            expiration: Expiration time in seconds
        
        Returns:
            Presigned HTTPS URL
        """
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expiration,
            )
            return url
        except ClientError as e:
            error_msg = f"Failed to generate presigned URL: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def delete_image(self, key: str) -> bool:
        """
        Delete image from S3
        
        Args:
            key: S3 object key
        
        Returns:
            True if deleted successfully
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=key)
            logger.info(f"✅ Deleted from S3: {key}")
            return True
        except ClientError as e:
            error_msg = f"Failed to delete from S3: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def get_object_metadata(self, key: str) -> dict:
        """
        Get metadata for an S3 object
        
        Args:
            key: S3 object key
        
        Returns:
            Metadata dictionary
        """
        try:
            response = self.s3_client.head_object(Bucket=self.bucket, Key=key)
            return {
                "size_bytes": response.get("ContentLength", 0),
                "content_type": response.get("ContentType", ""),
                "last_modified": response.get("LastModified"),
                "etag": response.get("ETag", "").strip('"'),
                "metadata": response.get("Metadata", {}),
            }
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                raise FileNotFoundError(f"Object not found in S3: {key}")
            error_msg = f"Failed to get object metadata: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def is_available(self) -> bool:
        """Check if S3 storage is available"""
        return self.s3_client is not None
