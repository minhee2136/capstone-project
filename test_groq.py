import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'capstone_project.settings')
django.setup()

from artifacts.models import Artifact
from groq import Groq
from django.conf import settings

try:
    client = Groq(api_key=settings.GROQ_API_KEY)
    artifact = Artifact.objects.filter(cleveland_id=153385).first()
    print('Artifact:', artifact.title)

    base_info = f'제목: {artifact.title}\n종류: {artifact.type}\n제작 시기: {artifact.creation_date}\n문화/국가: {artifact.culture}\n'
    if artifact.description:
        base_info += f'기존 설명: {artifact.description}\n'
    if artifact.did_you_know:
        base_info += f'참고 지식: {artifact.did_you_know}\n'

    prompt = f'TEST {base_info}'

    completion = client.chat.completions.create(
        model='llama-3.3-70b-versatile',
        messages=[{'role': 'user', 'content': prompt}],
        temperature=0.7,
        max_tokens=10,
    )
    print('SUCCESS:', completion.choices[0].message.content.strip())
except Exception as e:
    import traceback
    traceback.print_exc()
