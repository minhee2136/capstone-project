from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_sessions', '0006_session_visit_time_knowledge_update'),
    ]

    operations = [
        migrations.AddField(
            model_name='session',
            name='interest_tag',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='관심 태그'),
        ),
    ]
