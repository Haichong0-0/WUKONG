import os
import json
import boto3
from botocore.exceptions import ClientError
from tickets.models import Ticket

AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')

try:
    client = boto3.client("bedrock-runtime", region_name="eu-west-2")
    print("✅ AWS Bedrock client initialized successfully.")
except Exception as e:
    raise RuntimeError(f"❌ Error initializing AWS Bedrock client: {e}")

model_id = "meta.llama3-70b-instruct-v1:0"

def query_bedrock(prompt):
    """
    Query AWS Bedrock's Meta Llama 3 70B Instruct model with a given prompt.
    """
    formatted_prompt = f"""
    <|begin_of_text|><|start_header_id|>user<|end_header_id|>
    {prompt}
    <|eot_id|>
    <|start_header_id|>assistant<|end_header_id|>
    """
    request_payload = {
        "prompt": formatted_prompt,
        "max_gen_len": 512,
        "temperature": 0.5,
    }

    try:
        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(request_payload)
        )
        response_body = json.loads(response["body"].read())
        generation = response_body.get("generation", "").strip()
        return generation

    except ClientError as e:
        print(f"AWS ClientError: {e}")
    except Exception as e:
        print(f"Unexpected error querying Bedrock: {e}")
    return ""

def classify_department(ticket_description):
    prompt = f"""
    Classify the following university student query into one of these departments: 
    {', '.join([d[0] for d in Ticket.DEPARTMENT_CHOICES])}.
    Return only the department name.
    
    Query: {ticket_description}
    """
    return query_bedrock(prompt)

def generate_ai_answer(ticket_description):
    prompt = f"You are a university program officer, reply the student's query in only two or three sentences, 60 words max. Please note down 3 things in your answer: 1. Output the response only. Do not include things like: Here is a concise response to the student's query, [Your Name], Dear, Sincerely,  or any reflection on the answer, etc. that are not related to the response itself. Just give the answer itself. 2. 60 words max. 3. Do not include any bold or italic formatting. Provide a concise answer for the following student query: '{ticket_description}'"
    return query_bedrock(prompt)
