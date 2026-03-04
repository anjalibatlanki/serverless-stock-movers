import os
import json
import boto3
import decimal
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource("dynamodb")

def decimal_default(obj):
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    raise TypeError

def main(event, context):
    table_name = os.environ["MOVERS_TABLE_NAME"]
    pk_value = os.environ.get("MOVERS_TABLE_PK", "MOVERS")
    table = dynamodb.Table(table_name)

    resp = table.query(
        KeyConditionExpression=Key("pk").eq(pk_value),
        ScanIndexForward=False,
        Limit=7
    )

    items = resp.get("Items", [])
    items = sorted(items, key=lambda x: x.get("date", ""))

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(items, default=decimal_default),
    }
