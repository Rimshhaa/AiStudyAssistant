import os
import json
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-2.5-flash")

def generate_mcqs(text):

    prompt = f"""
You are a university examiner.

Generate 10 HIGH QUALITY concept-based MCQs.

STRICT RULES:

- Do NOT generate grammar questions.
- Do NOT generate fill-in-the-blanks.
- Do NOT ask vocabulary questions.
- Focus on concepts, definitions, architecture, applications, advantages, disadvantages and workflows.
- Every question must have 4 options.
- Include correct answer.
- Return JSON ONLY.

Format:

[
 {{
   "question":"",
   "options":["","","",""],
   "answer":""
 }}
]

CONTENT:

{text[:8000]}
"""

    response = model.generate_content(prompt)
    response = model.generate_content(prompt)
    content = response.text
    print("===== GEMINI MCQ RESPONSE =====")
    print(content)
    print("============================")
    content = content.replace("```json", "")
    content = content.replace("```", "")
    content = content.strip()
    return json.loads(content)

def generate_descriptive(text):

    prompt = f"""
Generate 5 university-level descriptive questions.

Rules:
- Based only on supplied content.
- Conceptual questions.
- No grammar questions.

Return JSON only.

CONTENT:

{text[:8000]}
"""

    response = model.generate_content(prompt)
    content = response.text
    print("\n===== GEMINI RESPONSE =====")
    print(content)
    print("==========================\n")
    content = content.replace("```json", "")
    content = content.replace("```", "")
    content = content.strip()

    try:
        start = content.find("[")
        end = content.rfind("]") + 1

        if start != -1 and end != -1:
            content = content[start:end]

        return json.loads(content)

    except Exception as e:
        print("JSON PARSE ERROR:", str(e))
        print(content)
        raise