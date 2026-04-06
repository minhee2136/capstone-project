from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_sessions', '0002_alter_session_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='session',
            name='history_embedding',
            field=models.JSONField(blank=True, null=True, verbose_name='히스토리 임베딩 벡터'),
        ),
    ]
