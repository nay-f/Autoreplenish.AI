import os
import boto3
from dotenv import load_dotenv

load_dotenv()

region = os.getenv("AWS_REGION", "us-east-1")
client = boto3.client(
    "bedrock",
    region_name=region,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)

print(f"=== DAFTAR MODEL CLAUDE YANG AKTIF DI REGION {region} ===")
try:
    # 1. Cek Inference Profiles (Wajib untuk Claude 3.5 / 3.7 / versi terbaru)
    profiles = client.list_inference_profiles(typeEquals="SYSTEM_DEFINED")
    claude_profiles = [
        p["inferenceProfileId"]
        for p in profiles.get("inferenceProfileSummaries", [])
        if "claude" in p["inferenceProfileId"] and "sonnet" in p["inferenceProfileId"]
    ]
    
    print("\nInference Profile IDs yang bisa dipakai langsung:")
    for cp in claude_profiles:
        print(f"-> {cp}")

    # 2. Cek Foundation Models standar
    models = client.list_foundation_models(byProvider="Anthropic")
    print("\nFoundation Model IDs:")
    for m in models.get("modelSummaries", []):
        if "sonnet" in m["modelId"]:
            print(f"-> {m['modelId']}")

except Exception as e:
    print(f"Gagal memeriksa model: {e}")