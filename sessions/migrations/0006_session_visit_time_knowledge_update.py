from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_sessions', '0005_session_interest_embedding'),
    ]

    operations = [
        migrations.AddField(
            model_name='session',
            name='visit_hour',
            field=models.IntegerField(blank=True, null=True, verbose_name='관람 희망 시간(시)'),
        ),
        migrations.AddField(
            model_name='session',
            name='visit_minute',
            field=models.IntegerField(blank=True, null=True, verbose_name='관람 희망 시간(분)'),
        ),
        migrations.AlterField(
            model_name='session',
            name='knowledge_level',
            field=models.CharField(
                blank=True,
                choices=[('초급', '초급'), ('중급', '중급'), ('전문가', '전문가')],
                max_length=20,
                null=True,
                verbose_name='지식 수준',
            ),
        ),
    ]
