from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0005_chat'),
    ]

    operations = [
        migrations.AddField(
            model_name='chat',
            name='share_token',
            field=models.UUIDField(blank=True, null=True, unique=True, verbose_name='공유 토큰'),
        ),
    ]
