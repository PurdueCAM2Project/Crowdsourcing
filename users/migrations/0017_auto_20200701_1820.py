# Generated by Django 2.2.10 on 2020-07-01 22:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0016_feature'),
    ]

    operations = [
        migrations.AlterField(
            model_name='feature',
            name='is_bias',
            field=models.IntegerField(verbose_name='Bias count'),
        ),
    ]