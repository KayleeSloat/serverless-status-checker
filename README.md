# Serverless Status Checker

A serverless AWS Lambda application that checks website status and stores results in DynamoDB. The service provides HTTP endpoints to trigger website checks and retrieve historical data.

## Features

- **POST /check** - Check a website's status by providing a URL
  - Validates URL format
  - Performs HTTP GET request
  - Measures response latency
  - Stores results in DynamoDB (status code, timestamp, latency)
  
- **GET /history** - Retrieve recent check history for a URL
  - Query by URL
  - Configurable limit (1-100 records)
  - Returns sorted results (newest first)

- Comprehensive input validation
- Error handling for network failures and timeouts
- CORS enabled for cross-origin requests

## Project Structure

```
serverless-status-checker/
├── handler.py           # Lambda function handlers
├── serverless.yml       # Serverless Framework configuration
├── requirements.txt     # Python dependencies
├── README.md           # This file
└── .gitignore          # Git ignore rules
```

## Prerequisites

- Python 3.9+
- Node.js 14+ (for Serverless Framework)
- AWS Account with appropriate permissions
- AWS CLI configured with credentials

## Setup

1. **Install Serverless Framework**
   ```bash
   npm install -g serverless
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure AWS credentials**
   ```bash
   aws configure
   # Or set environment variables:
   # export AWS_ACCESS_KEY_ID=your_access_key
   # export AWS_SECRET_ACCESS_KEY=your_secret_key
   ```

## Deployment

Deploy to AWS using the Serverless Framework:

```bash
# Deploy to dev stage (default)
serverless deploy

# Deploy to production stage
serverless deploy --stage prod

# Deploy to specific region
serverless deploy --region us-west-2
```

After deployment, the command will output the API endpoints:

```
endpoints:
  POST - https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/dev/check
  GET - https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/dev/history
```

## API Usage

### Check Website Status (POST /check)

**Request:**
```bash
curl -X POST https://your-api-url/dev/check \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

**Response (Success):**
```json
{
  "message": "Website status checked successfully",
  "result": {
    "url": "https://example.com",
    "timestamp": "2026-01-20T16:30:00.000Z",
    "status_code": 200,
    "latency_ms": 145.23,
    "success": true
  }
}
```

**Response (Error):**
```json
{
  "error": "Invalid URL format"
}
```

### Get Check History (GET /history)

**Request:**
```bash
# Get last 10 checks (default)
curl "https://your-api-url/dev/history?url=https://example.com"

# Get last 50 checks
curl "https://your-api-url/dev/history?url=https://example.com&limit=50"
```

**Response:**
```json
{
  "url": "https://example.com",
  "count": 10,
  "checks": [
    {
      "url": "https://example.com",
      "timestamp": "2026-01-20T16:30:00.000Z",
      "status_code": 200,
      "latency_ms": 145.23,
      "success": true
    },
    ...
  ]
}
```

## Testing

### Local Testing

Test the Lambda functions locally using Python:

```python
# test_local.py
import json
from handler import check_website_status, get_status_history

# Test check status
event = {
    'body': json.dumps({'url': 'https://example.com'})
}
result = check_website_status(event, None)
print(json.dumps(json.loads(result['body']), indent=2))
```

### Testing Deployed Endpoints

**Test POST /check:**
```bash
curl -X POST https://your-api-url/dev/check \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

**Test GET /history:**
```bash
curl "https://your-api-url/dev/history?url=https://example.com&limit=5"
```

### Input Validation Tests

```bash
# Test invalid URL
curl -X POST https://your-api-url/dev/check \
  -H "Content-Type: application/json" \
  -d '{"url": "not-a-url"}'

# Test missing URL
curl -X POST https://your-api-url/dev/check \
  -H "Content-Type: application/json" \
  -d '{}'

# Test invalid limit
curl "https://your-api-url/dev/history?url=https://example.com&limit=200"
```

## Running Locally

To run and test functions locally without deploying:

1. **Set up environment variables:**
   ```bash
   export DYNAMODB_TABLE=website-status-checks-dev
   ```

2. **Use Serverless Offline (optional plugin):**
   ```bash
   npm install serverless-offline --save-dev
   serverless offline
   ```

3. **Or test with AWS SAM Local:**
   ```bash
   sam local start-api
   ```

## Monitoring and Logs

View function logs:
```bash
# View logs for checkStatus function
serverless logs -f checkStatus

# Tail logs in real-time
serverless logs -f checkStatus --tail

# View logs for specific time range
serverless logs -f checkStatus --startTime 1h
```

## Cleanup

Remove all deployed resources:
```bash
serverless remove

# Remove specific stage
serverless remove --stage prod
```

## Configuration

### Environment Variables

- `DYNAMODB_TABLE` - DynamoDB table name (automatically set by serverless.yml)

### DynamoDB Table Structure

- **Primary Key:** `url` (String) - The website URL
- **Sort Key:** `timestamp` (String) - ISO 8601 timestamp
- **Attributes:**
  - `status_code` (Number) - HTTP status code
  - `latency_ms` (Number) - Response time in milliseconds
  - `success` (Boolean) - Whether the check succeeded
  - `error` (String, optional) - Error message if check failed

## Error Handling

The application handles various error scenarios:

- Invalid URL format (400 Bad Request)
- Missing required parameters (400 Bad Request)
- Network timeouts (stores with status_code: 0)
- Connection errors (stores with error message)
- DynamoDB errors (500 Internal Server Error)
- Invalid JSON (400 Bad Request)

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
