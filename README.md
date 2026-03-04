# Serverless Stock Movers Pipeline

This project builds a fully serverless data pipeline on AWS that identifies the top performing stock from a watchlist each day and displays the last 7 days of results in a web dashboard.

The system automatically retrieves stock price data, calculates the largest percentage mover, stores the result in DynamoDB, and serves the data through an API and frontend interface.

# Architecture

    - EventBridge (daily cron)
    - Lambda (Ingestion)
    - External Stock API (Massive)
    - DynamoDB
    - Lambda (API)
    - API Gateway
    - Static Frontend (S3)

# Features

 Daily automated ingestion of stock data  
 Calculates largest percent change from a watchlist  
 Stores results in DynamoDB  
 REST API to retrieve the last 7 days of winners  
 Static frontend dashboard displaying results  
 Fully deployed using AWS CDK 


# Watchlist

The following stocks are analyzed daily:

    AAPL, MSFT, GOOGL, AMZN, TSLA, NVDA  

# Prerequisites

Install the following:

    Node.js  
    AWS CLI  
    AWS CDK  

Configure AWS credentials:
    aws configure

# Deployment


### 1. Install dependencies
    cd infra
    npm install

### 2. Bootstrap CDK (first time only)
    cdk bootstrap

### 3. Set your Massive API key
    export MASSIVE_API_KEY="your_api_key_here"

### 4. Deploy infrastructure
    cdk deploy
    
    After deployment, CDK outputs:
        - API URL  
        - Frontend URL

# API Endpoint
    GET /movers
    Returns the last 7 days of winning stocks.

# Frontend
    The frontend dashboard displays:

        - Date  
        - Winning stock ticker  
        - Percent change  
        - Closing price

    Data is fetched directly from the API Gateway endpoint.

# Error Handling

The ingestion Lambda includes:

    - Retry logic for API calls  
    - Timeouts for external requests  
    - Graceful handling of failed tickers  
    - Rate limit protection

    If one stock API call fails, the pipeline continues processing the remaining tickers.