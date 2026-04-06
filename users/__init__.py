from django.db import migrations, models
import django.contrib.postgres.fields
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('nickname', models.CharField(max_length=50, verbose_name='닉네임')),
                ('gender', models.CharField(
                    blank=True,
                    choices=[('M', '남성'), ('F', '여성'), ('N', '선택 안 함')],
                    max_length=1,
                    null=True,
                    verbose_name='성별',
                )),
                ('birth_year', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='출생년도')),
                ('interest_tags', django.contrib.postgres.fields.ArrayField(
                    base_field=models.CharField(max_length=50),
                    blank=True,
                    default=list,
                    size=None,
                    verbose_name='관심 키워드',
                )),
                ('knowledge_level', models.CharField(
                    blank=True,
                    choices=[('beginner', '초급'), ('intermediate', '중급'), ('advanced', '고급')],
                    max_length=20,
                    null=True,
                    verbose_name='지식 수준',
                )),
                ('view_time_minutes', models.PositiveIntegerField(blank=True, null=True, verbose_name='관람 희망 시간(분)')),
                ('interest_embedding', models.JSONField(blank=True, null=True, verbose_name='관심사 임베딩 벡터')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='생성일시')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='수정일시')),
            ],
            options={
                'verbose_name': '사용자',
                'verbose_name_plural': '사용자 목록',
                'db_table': 'users',
            },
        ),
        migrations.AddIndex(
            model_name='user',
            index=models.Index(fields=['created_at'], name='users_created_at_idx'),
        ),
    ]