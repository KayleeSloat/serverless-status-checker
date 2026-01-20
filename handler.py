"""
AWS Lambda handlers for website status checker.
"""
import json
import time
import os
import ipaddress
from datetime import datetime
from urllib.parse import urlparse
import socket
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
import requests


# Initialize DynamoDB client (lazy initialization for testing)
_dynamodb = None
_table = None


def get_table():
    """Get or initialize DynamoDB table."""
    global _dynamodb, _table
    if _table is None:
        _dynamodb = boto3.resource('dynamodb')
        table_name = os.environ.get('DYNAMODB_TABLE', 'website-status-checks')
        _table = _dynamodb.Table(table_name)
    return _table


def validate_url(url):
    """
    Validate URL format and check for SSRF vulnerabilities.
    
    Args:
        url (str): URL to validate
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not url:
        return False, "URL is required"
    
    if not isinstance(url, str):
        return False, "URL must be a string"
    
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return False, "Invalid URL format"
        
        if result.scheme not in ['http', 'https']:
            return False, "URL must use http or https protocol"
        
        # Extract hostname (without port)
        hostname = result.hostname
        if not hostname:
            return False, "Invalid hostname"
        
        # Block localhost and loopback addresses
        if hostname.lower() in ['localhost', '127.0.0.1', '::1']:
            return False, "Access to localhost is not allowed"
        
        # Try to resolve hostname to IP and check for private ranges
        try:
            # Get IP address
            ip_str = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(ip_str)
            
            # Block private IP ranges (RFC 1918, RFC 4193)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False, "Access to private/internal IP addresses is not allowed"
        except socket.gaierror:
            # If DNS resolution fails, we'll let requests handle it
            # This allows the function to work even if the hostname doesn't exist yet
            pass
        except ValueError:
            # Invalid IP format - continue with validation
            pass
        
        return True, None
    except Exception as e:
        return False, f"Invalid URL: {str(e)}"


def check_website_status(event, context):
    """
    Lambda handler for POST endpoint to check website status.
    
    Expected input: {"url": "https://example.com"}
    
    Returns:
        dict: API Gateway response with status code and body
    """
    try:
        # Parse request body
        if 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            body = event
        
        url = body.get('url')
        
        # Validate URL
        is_valid, error_message = validate_url(url)
        if not is_valid:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': error_message
                })
            }
        
        # Perform HTTP GET request and measure latency
        start_time = time.time()
        try:
            response = requests.get(url, timeout=10, allow_redirects=True)
            latency_ms = (time.time() - start_time) * 1000
            status_code = response.status_code
            success = 200 <= status_code < 400
        except requests.exceptions.Timeout:
            latency_ms = (time.time() - start_time) * 1000
            status_code = 0
            success = False
            error_detail = "Request timeout"
        except requests.exceptions.RequestException as e:
            latency_ms = (time.time() - start_time) * 1000
            status_code = 0
            success = False
            error_detail = str(e)
        
        # Prepare item for DynamoDB
        timestamp = datetime.utcnow().isoformat() + 'Z'
        item = {
            'url': url,
            'timestamp': timestamp,
            'status_code': status_code,
            'latency_ms': round(latency_ms, 2),
            'success': success
        }
        
        if not success and 'error_detail' in locals():
            item['error'] = error_detail
        
        # Store in DynamoDB
        try:
            get_table().put_item(Item=item)
        except ClientError as e:
            print(f"DynamoDB error: {e}")
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Failed to store check result',
                    'details': str(e)
                })
            }
        
        # Return success response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Website status checked successfully',
                'result': item
            })
        }
        
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Invalid JSON in request body'
            })
        }
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal server error',
                'details': str(e)
            })
        }


def get_status_history(event, context):
    """
    Lambda handler for GET endpoint to retrieve status check history.
    
    Query parameters:
        - url (required): The URL to get history for
        - limit (optional): Number of recent checks to return (default: 10, max: 100)
    
    Returns:
        dict: API Gateway response with status code and body
    """
    try:
        # Parse query parameters
        query_params = event.get('queryStringParameters') or {}
        url = query_params.get('url')
        limit = query_params.get('limit', '10')
        
        # Validate URL
        if not url:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'URL parameter is required'
                })
            }
        
        # Validate limit
        try:
            limit = int(limit)
            if limit < 1 or limit > 100:
                raise ValueError("Limit must be between 1 and 100")
        except (ValueError, TypeError) as e:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': f'Invalid limit parameter: {str(e)}'
                })
            }
        
        # Query DynamoDB
        try:
            response = get_table().query(
                KeyConditionExpression=Key('url').eq(url),
                ScanIndexForward=False,  # Sort by timestamp descending (newest first)
                Limit=limit
            )
            
            items = response.get('Items', [])
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'url': url,
                    'count': len(items),
                    'checks': items
                })
            }
            
        except ClientError as e:
            print(f"DynamoDB error: {e}")
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Failed to query check history',
                    'details': str(e)
                })
            }
        
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal server error',
                'details': str(e)
            })
        }
