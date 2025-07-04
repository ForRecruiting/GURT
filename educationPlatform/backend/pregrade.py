from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename
from azure.cosmos import CosmosClient, exceptions
from azure.core.credentials import AccessToken
from azure.identity import DefaultAzureCredential
import tempfile
from flask_cors import CORS
import requests
import os
import time
import json


from azure.storage.blob import ContainerClient

# Load environment variables from .env file

class StaticTokenCredential:
    def __init__(self, token):
        self.token = token
    def get_token(self, *scopes, **kwargs):
        return AccessToken(self.token, float('inf'))

app = Flask(__name__)
CORS(app) 



def download_zip_blobs(container_url_with_sas):
    container_client = ContainerClient.from_container_url(container_url_with_sas)
    zip_files = []

    for blob in container_client.list_blobs():
        if blob.name.endswith('.zip'):
            blob_client = container_client.get_blob_client(blob)
            # Use tempfile to create a temporary file that works on all platforms
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_file:
                temp_file.write(blob_client.download_blob().readall())
                zip_files.append(temp_file.name)
    
    return zip_files

def send_to_grader(file_path):
    return grade_assign(file_path).get_json()
    # url = "http://localhost:5000/pregrade"  # or your deployed endpoint
    # with open(file_path, 'rb') as f:
    #     files = {'file': (file_path, f, 'application/zip')}
    #     response = requests.post(url, files=files)
    #     return response.json()
def get_link(name):
    print(f"🔍 Searching for user: {name}")
    # Define the Cosmos DB credentials and identifiers
    url = "https://ahmedkk2.documents.azure.com:443/"
    database_id = "cosmicworks"
    container_id = "ComputerScience"
    key = ""
    
    print(f"📡 Connecting to Cosmos DB: {url}")
    print(f"📂 Database: {database_id}, Container: {container_id}")
    
    # Initialize the Cosmos client
    client = CosmosClient(url, credential=key)

    try:
        # Get the database and container
        database = client.get_database_client(database_id)
        container = database.get_container_client(container_id)

        print("📋 Reading all items from container...")
        # Query all items in the container
        items = list(container.read_all_items())
        
        print(f"✅ Found {len(items)} items in container")
        
        # Print each item for debugging
        for i, item in enumerate(items):
            print(f"Item {i + 1}: {item}")
            if item.get('name') == name:
                print(f"✅ Found item with name '{name}'!")
                assignments_url = item.get('assignments')
                print(f"📦 Assignments URL: {assignments_url}")
                return assignments_url
                
        print(f"❌ No item found with name '{name}'")
        print("Available names in container:")
        for item in items:
            print(f"  - {item.get('name', 'NO_NAME_FIELD')}")
        return None
        
    except exceptions.CosmosHttpResponseError as e:
        print(f"❌ Cosmos DB HTTP Error: {e.status_code} - {e.message}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {type(e).__name__} - {str(e)}")
        return None
def full_performance(info):
    API_URL = 'https://lessonpipeline999-iwmhp.westus3.inference.ml.azure.com/score'
    API_KEY = 'ACKNNOAwagtPIp6HE0w8QeMvQCfxaEQuqsUYWJuFxbqUMfRFCJ0OJQQJ99BGAAAAAAAAAAAAINFRAZML1Dps'
    headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {API_KEY}'
        }
    prompt = f"""Please analyze the following student grading data and provide a comprehensive summary:

{str(info)}

Please provide insights into the grading patterns and overall performance assessment."""

    data = {
        "topic": prompt
    }
    response = requests.post(API_URL, headers=headers, json=data)
    try:
        if response.status_code == 200:
            result = response.json()
            return result["joke"]
        else:
            print(response.status_code, response.text)
    except Exception as e:
        print("gone wrong")

@app.route('/fullpipe', methods=['GET'])
def run_pipeline():
    print("🚀 Starting pipeline...")
    
    container_url_with_sas = get_link("Jeremy")
    print("Container URL with SAS:", container_url_with_sas)
    
    # Check if we got a valid URL
    if not container_url_with_sas:
        return jsonify({"error": "Failed to retrieve container URL from Cosmos DB"}), 500
    
    if not container_url_with_sas.startswith('https://'):
        return jsonify({"error": f"Invalid container URL received: {container_url_with_sas}"}), 500
    
    try:
        print("📥 Downloading ZIP files from blob storage...")
        zip_files = download_zip_blobs(container_url_with_sas)
        print(f"✅ Downloaded {len(zip_files)} ZIP files")
        
        if not zip_files:
            return jsonify({"error": "No ZIP files found in the container"}), 404
        
        all_feedback = dict()
        counter = 1
      
        for file_path in zip_files:
            print(f"🔍 Processing file {counter}: {file_path}")

            result = send_to_grader(file_path)

            if 'feedback' in result: 
                key = f"assignment_{counter}"
                all_feedback[key] = result["feedback"]
                counter += 1
            else:
                print(f"⚠️ No feedback received for file: {file_path}")

        if not all_feedback:
            return jsonify({"error": "No feedback was generated from any files"}), 500

        print("🤖 Generating performance summary...")
        summary = full_performance(all_feedback)
        print("📊 Summary of Feedback:", summary)
        
        return jsonify({
            "summary": summary,
            "files_processed": len(zip_files),
            "feedback_generated": len(all_feedback)
        })
        
    except Exception as e:
        print(f"❌ Pipeline error: {str(e)}")
        return jsonify({"error": f"Pipeline failed: {str(e)}"}), 500

@app.route('/criticalThinking', methods=['POST'])
def criticalThinking():
    info = request.get_json()
    API_URL = "https://helloworld3028727102.openai.azure.com/openai/deployments/gpt-4o-mini/chat/completions?api-version=2025-01-01-preview"
    API_KEY = "CqdeT4EbKfwBBmTzS8xm6C9zsHFcl37nDrSmu6rNKKFswgqAhHieJQQJ99BFACMsfrFXJ3w3AAAAACOG8ESR"
    headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {API_KEY}'
        }
    prompt = f"""
    Please answer the following question in a way the they are still using critical thinking skills. avoid givng direct answers/code, instead provide a thought process that leads to the answer or give them hints that point them to the right direction:
    {info['question']}
    """
    data = {
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 1000,
        "temperature": 0.7
    }
    response = requests.post(API_URL, headers=headers, json=data)
    try:
        if response.status_code == 200:
            result = response.json()
            # Extract just the message content from the response
            if 'choices' in result and len(result['choices']) > 0:
                message_content = result['choices'][0]['message']['content']
                print("AI Response:")
                return jsonify({"response": message_content})
            else:
                print("No response content found")
                return jsonify({"error": "No response content found"}), 500
        else:
            return jsonify({"error": f"Error {response.status_code}: {response.text}"}), response.status_code
    except Exception as e:
        print(f"Error occurred: {e}")

@app.route('/interest', methods=['POST'])
def interestBased():
    info = request.get_json()
    API_URL = "https://helloworld3028727102.openai.azure.com/openai/deployments/gpt-4o-mini/chat/completions?api-version=2025-01-01-preview"
    API_KEY = "CqdeT4EbKfwBBmTzS8xm6C9zsHFcl37nDrSmu6rNKKFswgqAhHieJQQJ99BFACMsfrFXJ3w3AAAAACOG8ESR"
    headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {API_KEY}'
        }
    prompt = f"Please explain {info['concept']} in the subject of {info['subject']} based on analogies about {info['analogy']}"
    data = {
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 1000,
        "temperature": 0.7
    }
    response = requests.post(API_URL, headers=headers, json=data)
    try:
        if response.status_code == 200:
            result = response.json()
            # Extract just the message content from the response
            if 'choices' in result and len(result['choices']) > 0:
                message_content = result['choices'][0]['message']['content']
                print("AI Response:")
                print(message_content)
                return jsonify({"response": message_content})
            else:
                print("No response content found")
                return jsonify({"error": "No response content found"}), 500
        else:
            print(f"Error {response.status_code}: {response.text}")
            return jsonify({"error": f"Error {response.status_code}: {response.text}"}), response.status_code
    except Exception as e:
        print(f"Error occurred: {e}")
        return jsonify({"error": f"Error occurred: {e}"}), 500




@app.route('/pregrade', methods=['POST'])
def grade_assign(zip_path = ""):
    # Check if file is in request
    if not zip_path:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400

    
    # Base URL for the API
    base_url = "https://hellocool.services.ai.azure.com/api/projects/firstProject"
    assistant_id = "asst_Uuq12LzVsvizVcBCBj7UVGFT"
    
    # Get the Azure AI access token
    credential = DefaultAzureCredential()
    token = credential.get_token("https://ai.azure.com/.default").token
    
    if not token:
        return jsonify({"error": "Azure AI access token not configured"}), 500

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Step 1: Upload the file
    print("📁 Step 1: Uploading zip file...")
    file_id = upload_file(base_url, token, zip_path)
    if not file_id:
        return jsonify({"error": "File upload failed"}), 500
    
    # Step 2: Create a thread
    print("🧵 Step 2: Creating a new thread...")
    thread_id = create_thread(base_url, headers)
    if not thread_id:
        return jsonify({"error": "Thread creation failed"}), 500
    
    # Step 3: Send message with file attachment
    print("💬 Step 3: Sending message with file attachment...")
    message_id = send_message(base_url, headers, thread_id, file_id)
    if not message_id:
        return jsonify({"error": "Message sending failed"}), 500
    
    # Step 4: Run the assistant
    print("🚀 Step 4: Running ZipAnalysis assistant...")
    run_id = run_assistant(base_url, headers, thread_id, assistant_id)
    if not run_id:
        return jsonify({"error": "Assistant run failed"}), 500
    
    # Step 5: Poll for completion and get response
    print("⏳ Step 5: Waiting for assistant to complete analysis...")
    feedback = get_assistant_response(base_url, headers, thread_id, run_id)
    if not feedback:
        return jsonify({"error": "Failed to get assistant response"}), 500
    info = feedback
    print(info)
    return jsonify({"feedback": feedback})

def upload_file(base_url, token, zip_path=""):
    url = f"{base_url}/files?api-version=v1"
    headers = {
        "Authorization": f"Bearer {token}"
    }

    # If zip_path is provided and is a string, treat as local file upload
    if zip_path and isinstance(zip_path, str):
        if not zip_path.lower().endswith('.zip'):
            print("❌ File must be a zip file")
            return None
        try:
            with open(zip_path, "rb") as f:
                files = {
                    "file": (os.path.basename(zip_path), f, "application/zip")
                }
                data = {"purpose": "assistants"}
                response = requests.post(url, headers=headers, files=files, data=data, timeout=60)
        except Exception as e:
            print(f"❌ Error opening file: {e}")
            return None
    # Otherwise, handle Flask file upload
    elif 'file' in request.files:
        file = request.files['file']
        if not file.filename.lower().endswith('.zip'):
            print("❌ File must be a zip file")
            return None
        files = {
            "file": (secure_filename(file.filename), file.stream, "application/zip")
        }
        data = {"purpose": "assistants"}
        response = requests.post(url, headers=headers, files=files, data=data, timeout=60)
    else:
        print("❌ No file provided")
        return None

    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        file_data = response.json()
        file_id = file_data.get('id')
        print(f"✅ File uploaded with ID: {file_id}")
        return file_id
    else:
        print("❌ File upload failed:", response.text)
        return None

def create_thread(base_url, headers):
    url = f"{base_url}/threads?api-version=v1"
    
    try:
        response = requests.post(url, headers=headers, json={}, timeout=30)
        
        if response.status_code == 200:
            thread_data = response.json()
            thread_id = thread_data.get('id')
            print(f"✅ Thread created with ID: {thread_id}")
            return thread_id
        else:
            print("❌ Thread creation failed:", response.text)
            return None
    except Exception as e:
        print(f"❌ Error creating thread: {e}")
        return None

def send_message(base_url, headers, thread_id, file_id):
    url = f"{base_url}/threads/{thread_id}/messages?api-version=v1"
    
    message_data = {
        "role": "user",
        "content": "Please analyze this zip file containing code and provide a detailed grade and feedback.",
        "attachments": [
            {
                "file_id": file_id,
                "tools": [{"type": "code_interpreter"}]
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=message_data, timeout=30)
        
        if response.status_code == 200:
            message_data = response.json()
            message_id = message_data.get('id')
            print(f"✅ Message sent with ID: {message_id}")
            return message_id
        else:
            print("❌ Message sending failed:", response.text)
            return None
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return None

def run_assistant(base_url, headers, thread_id, assistant_id):
    url = f"{base_url}/threads/{thread_id}/runs?api-version=v1"
    
    run_data = {
        "assistant_id": assistant_id
    }
    
    try:
        response = requests.post(url, headers=headers, json=run_data, timeout=30)
        
        if response.status_code == 200:
            run_data = response.json()
            run_id = run_data.get('id')
            print(f"✅ Assistant run started with ID: {run_id}")
            return run_id
        else:
            print("❌ Assistant run failed:", response.text)
            return None
    except Exception as e:
        print(f"❌ Error running assistant: {e}")
        return None

def get_assistant_response(base_url, headers, thread_id, run_id):
    run_url = f"{base_url}/threads/{thread_id}/runs/{run_id}?api-version=v1"
    messages_url = f"{base_url}/threads/{thread_id}/messages?api-version=v1"
    
    # Poll for completion
    max_attempts = 60  # 5 minutes with 5-second intervals
    attempt = 0
    
    while attempt < max_attempts:
        try:
            # Check run status
            response = requests.get(run_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                run_data = response.json()
                status = run_data.get('status')
                print(f"🔄 Run status: {status}")
                
                if status == 'completed':
                    print("✅ Assistant completed the analysis!")
                    break
                elif status in ['failed', 'cancelled', 'expired']:
                    print(f"❌ Assistant run {status}")
                    return
                else:
                    print("⏳ Still processing... waiting 5 seconds")
                    time.sleep(5)
                    attempt += 1
            else:
                print("❌ Error checking run status:", response.text)
                return
                
        except Exception as e:
            print(f"❌ Error polling run status: {e}")
            return
    
    if attempt >= max_attempts:
        print("⏰ Timeout waiting for assistant to complete")
        return
    
    # Get the messages to see the response
    try:
        response = requests.get(messages_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            messages_data = response.json()
            messages = messages_data.get('data', [])
     
            # print("\n" + "="*50)
            # print("🎯 ZIPANALYSIS ASSISTANT RESPONSE:")
            # print("="*50)

            # Find the assistant's response (most recent message from assistant)
            for message in messages:
                if message.get('role') == 'assistant':
                    content = message.get('content', [])
                    for content_item in content:
                        if content_item.get('type') == 'text':
                            text_content = content_item.get('text', {}).get('value', '')
                            print("\n" + "="*50)
                            return text_content
                    break
            else:
                print("No assistant response found in messages")
        else:
            print("❌ Error retrieving messages:", response.text)
    except Exception as e:
        print(f"❌ Error getting assistant response: {e}")

if __name__ == '__main__':
    app.run(debug=True)
