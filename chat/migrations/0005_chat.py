from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0004_alter_feedback_feedback_type'),
        ('user_sessions', '0007_session_interest_tag'),
    ]

    operations = [
        migrations.CreateModel(
            name='Chat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('history', models.JSONField(default=list, verbose_name='방문 유물 ID 리스트')),
                ('feedback_history', models.JSONField(default=list, verbose_name='피드백 이력')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('session', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='chats',
                    to='user_sessions.session',
                    verbose_name='세션',
                )),
            ],
            options={
                'verbose_name': '채팅',
                'verbose_name_plural': '채팅 목록',
                'db_table': 'chats',
            },
        ),
    ]
