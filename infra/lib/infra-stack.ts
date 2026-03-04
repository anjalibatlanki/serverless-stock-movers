import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';

import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';

import * as path from 'path';

export class InfraStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

   
    //DynamoDB Table
    

    const moversTable = new dynamodb.Table(this, 'MoversTable', {
      partitionKey: { name: 'pk', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'date', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    
    //Ingestion Lambda
    

    const ingestFn = new lambda.Function(this, 'IngestMoverFn', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'handler.main',
      code: lambda.Code.fromAsset(
        path.join(__dirname, '../../services/ingestion')
      ),
      timeout: cdk.Duration.seconds(90),
      memorySize: 256,
      environment: {
        MOVERS_TABLE_NAME: moversTable.tableName,
        MOVERS_TABLE_PK: 'MOVERS',
        WATCHLIST: 'AAPL,MSFT,GOOGL,AMZN,TSLA,NVDA',
        MASSIVE_API_KEY: process.env.MASSIVE_API_KEY ?? '',
      },
    });

    moversTable.grantWriteData(ingestFn);

    
    //EventBridge Daily Cron
    

    const dailyRule = new events.Rule(this, 'DailyIngestionRule', {
      schedule: events.Schedule.cron({
        minute: '0',
        hour: '23',
      }),
    });

    dailyRule.addTarget(new targets.LambdaFunction(ingestFn));

    
    //API Lambda
    

    const apiFn = new lambda.Function(this, 'GetMoversFn', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'handler.main',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../services/api')),
      timeout: cdk.Duration.seconds(10),
      environment: {
        MOVERS_TABLE_NAME: moversTable.tableName,
        MOVERS_TABLE_PK: 'MOVERS',
      },
    });

    moversTable.grantReadData(apiFn);

    
    //API Gateway
    

    const api = new apigw.RestApi(this, 'StocksApi', {
      restApiName: 'stocks-serverless-pipeline',
      defaultCorsPreflightOptions: {
        allowOrigins: apigw.Cors.ALL_ORIGINS,
        allowMethods: ['GET', 'OPTIONS'],
      },
    });

    const movers = api.root.addResource('movers');

    movers.addMethod('GET', new apigw.LambdaIntegration(apiFn));

    
    //Frontend Hosting (S3)
    

    const siteBucket = new s3.Bucket(this, 'FrontendBucket', {
      websiteIndexDocument: 'index.html',
      websiteErrorDocument: 'index.html',
      publicReadAccess: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,

      blockPublicAccess: new s3.BlockPublicAccess({
        blockPublicAcls: true,
        ignorePublicAcls: true,
        blockPublicPolicy: false,
        restrictPublicBuckets: false,
      }),
    });

    new s3deploy.BucketDeployment(this, 'DeployFrontend', {
      sources: [
        s3deploy.Source.asset(path.join(__dirname, '../../frontend')),
      ],
      destinationBucket: siteBucket,
    });

    
    //Outputs
    

    new cdk.CfnOutput(this, 'ApiUrl', {
      value: api.url,
    });

    new cdk.CfnOutput(this, 'FrontendUrl', {
      value: siteBucket.bucketWebsiteUrl,
    });
  }
}