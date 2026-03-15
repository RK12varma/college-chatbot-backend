from fastapi import FastAPI
from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

@app.get("/")
def home():
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Explain logistic regression in simple terms."
    )
    return {"response": response.text}
