from google import genai
from google.genai.errors import ClientError
import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def generate_answer(question: str, context: str):

    prompt = f"""
You are an academic assistant for college students.

Strict Rules:
- Use ONLY the provided context.
- Do NOT invent information.
- If answer is not present in context, say exactly:
  "This information is not available in the provided documents."

SPECIAL RESULT RULE:
If the question is asking for a student's result, marks, performance, or semester result,
you MUST return ONLY the following fields (if available):

Name: <Student Name>
Semester: <Semester>
GPA: <GPA>
Total Marks: <Total Marks>
Result: <Pass/Fail>

Important:
- Do NOT include any other fields.
- Do NOT include explanations.
- Do NOT include bullet points.
- Do NOT include tables.
- Output must be exactly 5 lines in this format.
- If any field is not present in context, omit that line.

For all other questions:
- Format answer clearly using bullet points.
- Use tables only if necessary and follow strict Markdown rules.

Table Rules (if used):
- Use ONLY single pipes (|)
- Exactly one header row
- Exactly one separator row
- Do NOT use double pipes (||)
- Do NOT add extra pipes
- All rows must match header column count

Context:
{context}

Question:
{question}

Answer:
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        return response.text

    except ClientError as e:
        if e.status_code == 429:
            return (
                "⚠️ AI service quota exceeded.\n\n"
                "Please wait a few seconds and try again."
            )

        return "⚠️ AI service error occurred."

    except Exception:
        return "⚠️ Unexpected AI system error occurred."
