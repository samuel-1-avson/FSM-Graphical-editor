api_key = "sk-98ac3821d6ff40b0bf83d5ed3b944a2a"

import os
import requests

# Retrieve API key from environment variable
API_KEY = os.getenv("sk-98ac3821d6ff40b0bf83d5ed3b944a2a")
API_URL = "https://api.deepseek.com/v1/your_endpoint_here"  # Replace with the actual API endpoint

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Example request payload
payload = {
    "query": "Your input data here"
}

# Make the API request
response = requests.post(API_URL, headers=headers, json=payload)

# Handle the response
if response.status_code == 200:
    print("API Response:", response.json())
else:
    print("Error:", response.status_code, response.text)