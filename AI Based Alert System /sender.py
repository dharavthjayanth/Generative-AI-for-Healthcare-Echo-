import pika
import json
import pandas as pd
import time
import boto3
from io import StringIO

AWS_ACCESS_KEY_ID = 
AWS_SECRET_ACCESS_KEY = 
AWS_BUCKET_NAME = 
AWS_REGION = 
OBJECT_KEY = "Person_A_-_Heart_Stroke_at_6_Minutes__5PM_to_6PM_.csv"  


print("[INFO] Connecting to S3 and downloading the dataset...")

s3_client = boto3.client(
    's3',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

response = s3_client.get_object(Bucket=AWS_BUCKET_NAME, Key=OBJECT_KEY)
csv_content = response['Body'].read().decode('utf-8')
df = pd.read_csv(StringIO(csv_content))

print(f"[INFO] Loaded {len(df)} rows from S3")

print("[INFO] Connecting to RabbitMQ...")

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue='health_data')

print("[INFO] Sending health data every 2 minutes...")

for index, row in df.iterrows():
    try:
        data = {
            "timestamp": row["timestamp"],
            "spo2": int(row["spo2"]),
            "heart_rate": int(row["heart_rate"]),
            "bp_sys": int(row["bp_sys"]),
            "bp_dia": int(row["bp_dia"])
        }
        message = json.dumps(data)
        channel.basic_publish(exchange='', routing_key='health_data', body=message)
        print(f"[SENT] {message}")
        time.sleep(120)  
    except Exception as e:
        print(f"[ERROR] Failed to send row {index}: {e}")

connection.close()
print("[INFO] Sender script finished.")
