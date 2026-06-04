from openai import OpenAI
import os
from dotenv import load_dotenv
import json
import re

load_dotenv()

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY")
)

def clean_json_response(content):
    """Extract JSON from various LLM output formats."""
    content = re.sub(r'```json\s*', '', content)
    content = re.sub(r'```\s*', '', content)
    content = content.strip()

    start = content.find('{')
    end = content.rfind('}')

    if start != -1 and end != -1:
        content = content[start:end+1]

    return content

def analyze_job(description):
    """Analyze job description using LLM."""
    prompt = f"""You are an expert job filter for a candidate with these skills:
- Python, Django, FastAPI
- AI/ML, LLMs, RAG, Fine-tuning
- 3-4 years experience (Mid-level)

Target: Singapore, Malaysia, or Remote roles that welcome foreigners.

Analyze this job description and return STRICT JSON:
{{
  "fit_score": <0-100, how well skills match>,
  "should_apply": <true/false, auto-apply only if strong match AND visa likely>,
  "visa_sponsorship": "<likely/unlikely/unclear>",
  "seniority": "<junior/mid/senior>",
  "summary": [
    "<key point 1>",
    "<key point 2>",
    "<key point 3>"
  ],
  "concerns": [
    "<any red flags or concerns>"
  ]
}}

Job Description:
{description[:5000]}
"""

    try:
        response = client.chat.completions.create(
            model="meta/llama-3.3-70b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=500
        )

        content = response.choices[0].message.content
        print("\nRAW LLM RESPONSE:")
        print(content[:500])

        cleaned = clean_json_response(content)
        parsed = json.loads(cleaned)

        # Validate required fields
        required = ["fit_score", "should_apply", "visa_sponsorship", "seniority", "summary"]
        for field in required:
            if field not in parsed:
                parsed[field] = "unknown" if field != "fit_score" else 0
                if field == "should_apply":
                    parsed[field] = False
                if field == "summary":
                    parsed[field] = []

        return parsed

    except Exception as e:
        print(f"LLM Error: {e}")
        return {
            "fit_score": 0,
            "should_apply": False,
            "visa_sponsorship": "unclear",
            "seniority": "unknown",
            "summary": ["Analysis failed"],
            "concerns": [str(e)]
        }