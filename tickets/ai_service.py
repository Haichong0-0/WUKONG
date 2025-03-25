import os
import json
import boto3
from botocore.exceptions import ClientError
from tickets.models import Ticket, AITicketProcessing, MergedTicket

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")

try:
    client = boto3.client("bedrock-runtime", region_name="eu-west-2")
    print("✅ AWS Bedrock client initialized successfully.")
except Exception as e:
    raise RuntimeError(f"❌ Error initializing AWS Bedrock client: {e}")

model_id = "meta.llama3-70b-instruct-v1:0"


# code to query the model format the prompt and return the response
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
            modelId=model_id, body=json.dumps(request_payload)
        )
        response_body = json.loads(response["body"].read())
        generation = response_body.get("generation", "").strip()
        return generation

    except ClientError as e:
        pass
    except Exception as e:
        pass

    return ""  # Return an empty string if the query fails


def classify_department(ticket_description):
    prompt = f"""
    Classify the following university student query into one of these departments: 
    {', '.join([d[0] for d in Ticket.DEPARTMENT_CHOICES])}.
    Return only the department name.
    
    Query: {ticket_description}
    """
    return query_bedrock(prompt)


def predict_priority(ticket_description):
    prompt = f"""
    Predict the priority level for the following university student query: 
    {', '.join([d[0] for d in Ticket.PRIORITY_CHOICES])}.
    Return only the priority level.
    
    Query: {ticket_description}
    """
    return query_bedrock(prompt)


def generate_ai_answer(ticket_description):
    prompt = f"You are a university program officer, reply the student's query in only two or three sentences, 60 words max. Please note down 3 things in your answer: 1. Output the response only. Do not include things like: Here is a concise response to the student's query, [Your Name], Dear, Sincerely,  or any reflection on the answer, etc. that are not related to the response itself. Just give the answer itself. 2. 60 words max. 3. Do not include any bold or italic formatting. Provide a concise answer for the following student query: '{ticket_description}'"
    return query_bedrock(prompt)


# code to process the ticket and update the model with the AI response, department and priority
def ai_process_ticket(ticket):
    """
    Classifies the department and generates an AI response for the ticket description.
    """
    ai_department = classify_department(ticket.description)
    ai_answer = generate_ai_answer(ticket.description)
    ai_priority = predict_priority(ticket.description)

    ai_ticket_processing, created = AITicketProcessing.objects.get_or_create(
        ticket=ticket,
        defaults={
            "ai_generated_response": ai_answer,
            "ai_assigned_department": ai_department,
            "ai_assigned_priority": ai_priority,
        },
    )

    if not created:
        ai_ticket_processing.ai_generated_response = ai_answer
        ai_ticket_processing.ai_assigned_department = ai_department
        ai_ticket_processing.ai_assigned_priority = ai_priority
        # ai_ticket_processing.save()

    ticket.priority = ai_ticket_processing.ai_assigned_priority


def find_potential_tickets_to_merge(ticket):

    # Fetch open tickets that are not the current ticket
    # only same department tickets to save processing time
    ai_assigned_department = ticket.ai_processing.ai_assigned_department
    potential_tickets = Ticket.objects.filter(
        status="in_progress",
        ai_processing__ai_assigned_department=ai_assigned_department,
    ).exclude(id=ticket.id)

    # Generate a prompt to compare the current ticket's description with other ticket descriptions
    similar_tickets = []

    for potential_ticket in potential_tickets:
        prompt = f"""
        Determine whether the following tickets should be merged. Consider their similarity.
        The current ticket: '{ticket.title}' - {ticket.description}
        The potential ticket: '{potential_ticket.title}' - {potential_ticket.description}
        Should these tickets be merged? Return "Yes" or "No".
        """

        result = query_bedrock(prompt)

        if result.lower() == "yes":
            similar_tickets.append(potential_ticket)

    # Create a new MergedTicket entry with the primary ticket and the suggested tickets
    if similar_tickets:
        merged_ticket, created = MergedTicket.objects.get_or_create(
            primary_ticket=ticket
        )
        merged_ticket.suggested_merged_tickets.set(similar_tickets)
        merged_ticket.save()

    return similar_tickets
