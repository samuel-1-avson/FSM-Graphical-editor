import os
import requests

# Set your API key (preferably use environment variables for security)
api_key = "sk-98ac3821d6ff40b0bf83d5ed3b944a2a"  # Replace with your actual API key

# Define the API endpoint (replace with the correct DeepSeek API endpoint)
API_URL = "https://api.deepseek.com/v1/chat/completions"  # Example endpoint

# Set up headers
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# Define the request payload (update based on DeepSeek API requirements)
payload = {
    "model": "deepseek-chat",  # Replace with the correct model name
    "messages": [
        {"role": "user", "content": "Hello, how can I use the DeepSeek API?"}
    ]
}

# Make the API request
response = requests.post(API_URL, headers=headers, json=payload)

# Handle the response
if response.status_code == 200:
    print("API Response:", response.json())
else:
    print("Error:", response.status_code, response.text)