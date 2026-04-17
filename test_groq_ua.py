import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'capstone_project.settings')
django.setup()

from groq import Groq
from django.conf import settings
import httpx

try:
    http_client = httpx.Client(headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"})
    client = Groq(api_key=settings.GROQ_API_KEY, http_client=http_client)

    completion = client.chat.completions.create(
        model='llama-3.3-70b-versatile',
        messages=[{'role': 'user', 'content': 'Test'}],
        temperature=0.7,
        max_tokens=10,
    )
    print('SUCCESS:', completion.choices[0].message.content.strip())
except Exception as e:
    import traceback
    traceback.print_exc()
