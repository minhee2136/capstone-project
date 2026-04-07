from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_user_interest_embedding'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='interest_embedding',
        ),
        migrations.AddField(
            model_name='user',
            name='interest_embedding',
            field=models.JSONField(blank=True, null=True, verbose_name='관심사 임베딩 벡터'),
        ),
    ]