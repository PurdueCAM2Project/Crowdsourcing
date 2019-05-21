# Generated by Django 2.1.7 on 2019-05-21 01:28

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0021_auto_20190517_1938'),
    ]

    operations = [
        migrations.CreateModel(
            name='Answer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.CharField(max_length=64)),
                ('isFinal', models.BooleanField(default=False)),
                ('count', models.IntegerField(default=1)),
            ],
        ),
        migrations.CreateModel(
            name='Question',
            fields=[
                ('text', models.CharField(max_length=64, primary_key=True, serialize=False)),
                ('isFinal', models.BooleanField(default=False)),
                ('count', models.IntegerField(default=1)),
                ('imageID', models.CharField(max_length=64)),
                ('skipCount', models.IntegerField(default=0)),
            ],
        ),
        migrations.DeleteModel(
            name='NotSameVote',
        ),
        migrations.RemoveField(
            model_name='imagemodel',
            name='label',
        ),
        migrations.DeleteModel(
            name='Label',
        ),
        migrations.AddField(
            model_name='answer',
            name='question',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='users.Question'),
        ),
    ]
