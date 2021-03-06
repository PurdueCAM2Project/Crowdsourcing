from csgame.views import over

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models.expressions import Case, F, Value, When
from users.models import CustomUser, ImageModel, Attribute, PhaseBreak, Phase01_instruction, Phase02_instruction, \
    Phase03_instruction, TextInstruction, Question, Answer, Feature

from django.contrib.auth.admin import UserAdmin

from django.http import HttpResponse

from django.shortcuts import render, redirect

import boto3
# from operator import attrgetter, itemgetter
import csv, os
import botocore
from botocore.client import Config
import random
import requests
import json
from more_itertools import chunked, padded
from users.forms import featureForm, MyForm

# self-defined decorators for crowd worker and admin/staff be able to work
from ..decorators import player_required
from .roundsgenerator import pushPostList, popGetList, step2_push, step2_pop

from ..models import Phase

from django.views.decorators.csrf import csrf_exempt

# We should set up in backend manually
KEYRING = settings.KEYRING
OBJECT_NAME_PLURAL = settings.OBJECT_NAME_PLURAL
NUMROUNDS = settings.NUMROUNDS
PRODUCTION = settings.IS_PRODUCTION_SITE

old_csvPath = os.path.join(settings.BASE_DIR, 'Q & A - Haobo.csv')
new_csvPath = os.path.join(settings.BASE_DIR, 'test_att.csv')

from ..reducer.client import send__receive_data


@player_required
@csrf_exempt
def phase01a(request, previewMode=False):
    # assignmentID for front-end submit javascript
    assignmentId = request.GET.get('assignmentId')
    # Need to check
    if request.method == 'POST':
        postList = pushPostList(request)

        # Get the Q and Ans for the current question, they should be at least one Q&A for all of the set
        questions = request.POST.getlist('data_q[]')
        answers = request.POST.getlist('data_a[]')

        # print("I got questions: ", questions)
        # print("I got answers: ", answers)
        # retrieve the json data for updating skip count for the previous questions
        validation_list = request.POST.getlist('data[]')

        correct_qs = []
        for q in questions:
            text = q.replace(' ', '+')
            url = f'https://api.textgears.com/check.php?text={text}&key=SFCKdx4GHmSC1j6H'
            response = requests.get(url)
            wordsC = response.json()
            # print(wordsC)
            for err in wordsC['errors']:
                bad = err['bad']
                good = err['better']
                if good:
                    q = q.replace(bad, good[0])
            correct_qs.append(q)

        # Query list for the old data in the table
        old_Qs = list(Question.objects.filter(isFinal=True).values_list('text', 'id'))
        # print("old questions", old_Qs)

        questions = Question.objects.bulk_create([Question(text=que, isFinal=False,
                                                           imageID=list(ImageModel.objects.filter(id__in=postList)),
                                                           hit_id=assignmentId) for que in correct_qs])
        new_Qs = [(que.text, que.id) for que in
                  questions]  # list(map(attrgetter('text', 'id'), questions)) # don't know which is better speedwise
        # print("new question", new_Qs)

        # Call the NLP function and get back with results, it should be something like wether it gets merged or kept
        # backend call NLP and get back the results, it should be a boolean and a string telling whether the new entry will be created or not
        # exist_q should be telling which new question got merged into
        acceptedList, id_merge, id_move = [que.id for que in questions], {}, {}
        id_merge = {int(k): v for k, v in id_merge.items()}
        id_move = {int(k): v for k, v in id_move.items()}
        # print("acceptedList is: ", acceptedList)
        # print("id_merge is: ", id_merge)
        # print("id_move is: ", id_move)

        Question.objects.filter(id__in=acceptedList).update(isFinal=True)
        # Question.objects.filter(id__in=[que.id for que in questions if que.id not in id_merge]).update(isFinal=True)

        # Store id_merge under mergeParent in the database
        id_merge_sql = Case(*[When(id=new, then=Value(old)) for new, old in id_merge.items()])
        Question.objects.filter(id__in=id_merge).update(mergeParent=id_merge_sql)

        answers = Answer.objects.bulk_create(
            [Answer(question_id=id_merge.get(que.id, que.id), text=ans, hit_id=assignmentId, imgset=-1) for que, ans in
             zip(questions, answers)])

        with transaction.atomic():
            id_move_sql = Case(*[When(question_id=bad, then=Value(good)) for bad, good in id_move.items()])
            Answer.objects.filter(question_id__in=id_move).update(question_id=id_move_sql)
            id_move_sql = Case(*[When(id=bad, then=Value(good)) for bad, good in id_move.items()])
            Question.objects.filter(id__in=id_move).update(isFinal=False, mergeParent=id_move_sql)
            Question.objects.filter(id__in=id_move.values()).update(isFinal=True)

        return HttpResponse(status=201)

    # Get rounds played in total and by the current player
    rounds, roundsnum = popGetList(ImageModel.objects.filter(img__startswith=KEYRING).values_list('id', flat=True))

    if len(rounds.post) >= ImageModel.objects.filter(img__startswith=KEYRING).count():
        # push all to waiting page
        return over(request, 'phase01a', assignmentId)

    # Single image that will be sent to front-end, will expire in 300 seconds (temporary)
    # sending 4 images at a time
    data = [i.img.url for i in ImageModel.objects.filter(id__in=roundsnum)]
    data.extend([None] * (3 - len(data)))

    if all([d is None for d in data]):
        return over(request, 'phase01a', assignmentId)
    # print("I got: ",     serving_img_url)
    # Previous all question pairs that will be sent to front-end

    # Get all the instructions
    instructions = Phase01_instruction.get_queryset(Phase01_instruction) or ['none']

    # Get all of the questions
    previous_questions = list(Question.objects.filter(isFinal=True).values_list('text', flat=True))

    return render(request, 'phase01a.html',
                  {'url': data, 'imgnum': roundsnum, 'questions': previous_questions, 'assignmentId': assignmentId,
                   'previewMode': previewMode, 'instructions': instructions, 'NUMROUNDS': NUMROUNDS[phase01a.__name__],
                   'object': OBJECT_NAME_PLURAL})


'''
View for phase 01 b
Output to front-end: list of all questions and 4 images without overlapping (similar to what we did before)
POST = method that retrieve the QA dictionary from the crowd workers
'''


@player_required
@csrf_exempt
def phase01b(request, previewMode=False):
    # Only show people all the question and the answer. Keep in mind that people have the chance to click skip for different questions
    # There should be an array of question that got skipped. Each entry should the final question value
    assignmentId = request.GET.get('assignmentId')
    if request.method == 'POST':
        # Get the answer array for different
        # Update the rounds posted for phase 01b
        imgsets = step2_push(request)
        # pushPostList(request, '²')
        dictionary = json.loads(request.POST.get('data[dict]'))

        # get the dictionary from the front-end back
        print("I got the QA dict: ", dictionary)

        for imgset, (question, answer) in zip(imgsets, dictionary):
            print("Answer: ", answer)
            # if the answer is not empty, add into database
            que = Question.objects.get(text=question, isFinal=True)
            new_Ans = Answer.objects.create(text=answer, question=que, hit_id=assignmentId, imgset=imgset)

        return HttpResponse(status=201)

    # Get rounds played in total and by the current player
    roundsnum, imin, questions, stopGame = step2_pop(NUMROUNDS[phase01b.__name__])

    if stopGame or not questions:
        return over(request, 'phase01b')

    # sending 4 images at a time
    data = [[i.img.url for i in ImageModel.objects.filter(id__in=rounds)] for rounds in roundsnum]
    data.extend([None] * (6 - len(data)))

    # Get all the insturctions sets
    instructions = Phase02_instruction.get_queryset(Phase02_instruction) or ['none']

    # allQuestions = dict(Question.objects.filter(id__in=[*ids for ids in questions]).values_list('id', 'text'))
    # questions = [[allQuestions[id] for id in ids] for ids in questions]

    questions = [q for q in questions if q]
    question_list = [q.text for q in questions]
    qlist = list(chunked(padded(enumerate(question_list), n=2, next_multiple=True), 2))
    print(qlist)
    return render(request, 'phase01b.html',
                  {'phase': 'PHASE 01b', 'image_url': data, 'imgnum': imin, 'question_list': question_list,
                   'display_list': qlist, 'assignmentId': assignmentId, 'previewMode': previewMode,
                   'instructions': instructions,
                   'answer_list': [[i for i in q.answers.distinct().values_list('text', flat=True) if i != ''] for q in
                                   questions]})
    # The NLP server will be updated later?


# function that should be accessible only with admin
@player_required
@csrf_exempt
def phase02(request, previewMode=False):
    if request.user.is_superuser or request.user.is_staff:
        print("This is admin")
        information = "Please press the button to process the redundant answers for each questions"
    else:
        print("The user should not process the homepage")
        information = "Thank you for your support and please wait until we finish process and release the next phase"
    return render(request, 'over.html', {'info': information})


NUMROUNDS_3 = 50


# View for phase3
@player_required
@csrf_exempt
def phase03(request, previewMode=False):
    # Update count
    if request.method == 'POST':
        words = request.POST.getlist('data[]')
        Attribute.objects.filter(word__in=words).update(count=F('count') - 1)

        return HttpResponse(status=201)
    else:
        assignmentId = request.GET.get('assignmentId')

        with transaction.atomic():
            rounds = Phase.objects.select_for_update().get_or_create(phase='3')[0]
            getList = rounds.get
            attrs = Attribute.objects.exclude(answer_id__in=getList).order_by('answer_id')[:NUMROUNDS_3]
            attributes = list(attrs.values_list('word', flat=True))
            if len(attrs) == NUMROUNDS_3:
                getList.extend(attrs.values_list('answer_id', flat=True))
            else:
                attrs2 = Attribute.objects.all().order_by('answer_id')[:NUMROUNDS_3 - len(attrs)]
                getList[:] = attrs2.values_list('answer_id', flat=True)
                attributes.extend(attrs2.values_list('word', flat=True))
            rounds.save()

        random.shuffle(attributes)
        display_list = list(chunked(attributes, 5))
        instructions = Phase03_instruction.get_queryset(Phase03_instruction) or ['none']
        return render(request, 'phase03.html',
                      {'statements': attributes, 'display_list': display_list, 'instructions': instructions,
                       'assignmentId': assignmentId, 'previewMode': previewMode})


from ..models import Feature


# View for step01
@player_required
@csrf_exempt
def step01(request, previewMode=False):
    url_list = []
    if request.method == 'POST':
        # result = request.POST.getlist('features[]')
        result = request.POST.getlist('data[]')
        feature = Feature.objects.all().order_by('feature')
        feature_list = list(feature.values_list('feature', flat=True))
        for feature in result:
            if feature not in feature_list:
                Feature.objects.bulk_create([
                    Feature(feature=feature, count=0, is_bias=0)])
        print("post result: ", result)
        # replace this with either payment or going on to the next round
        messages.success(request, 'Submitted!')
        return render(request, 'feedback.html')
    else:
        # form = featureForm()

        # Get rounds played in total and by the current player
        rounds, roundsnum = popGetList(ImageModel.objects.filter(img__startswith=KEYRING).values_list('id', flat=True))

        if len(rounds.post) >= ImageModel.objects.filter(img__startswith=KEYRING).count():
            # push all to waiting page
            return over(request, 'step01')

        # Single image that will be sent to front-end, will expire in 300 seconds (temporary)
        # sending 4 images at a time
        data = [i.img.url for i in ImageModel.objects.filter(id__in=roundsnum)]
        data.extend([None] * (9 - len(data)))
        instructions = Phase01_instruction.get_queryset(Phase01_instruction) or ['none']
    return render(request, 'step01.html', {'url': data, 'previewMode': previewMode,'instructions': instructions, 'NUMROUNDS': NUMROUNDS[step01.__name__],'imgnum': roundsnum})


# View for step02
@player_required
@csrf_exempt
def step02(request, previewMode=False):
    feature = Feature.objects.all().order_by('feature')
    feature_list = list(feature.values_list('feature', flat=True))
    if request.method == 'POST':
        form = MyForm(request.POST)
        if form.is_valid():
            chosen_features = form.cleaned_data.values()
            print(chosen_features)
            for item in chosen_features:
                chosen_list = (list(item.values_list('feature', flat=True)))
                for f in chosen_list:
                    Feature.objects.filter(feature=f).update(is_bias=F('is_bias') - 1)
        return render(request, 'feedback.html')
    else:
        form = MyForm()

    form.feature = feature
    form.feature_list = feature_list
    instructions = Phase02_instruction.get_queryset(Phase02_instruction) or ['none']
    return render(request, 'step02.html', {'form': form, 'previewMode': previewMode, 'instructions': instructions})


# View for step03
@player_required
@csrf_exempt
def step03(request, previewMode=False):
    url_list = []
    assignmentId = request.GET.get('assignmentId')
    feature = Feature.objects.filter(is_bias__gt = -3).order_by('feature')
    feature_list = list(feature.values_list('feature', flat=True))
    print(feature_list)

    if request.method == 'POST':
        result = int(request.POST.get('data'))
        round = int(request.POST.get('round'))
        Feature.objects.filter(feature=feature_list[round]).update(count=F('count') + result)
        print("round:", round, " feature:", feature_list[round], " post result:", result, len(feature_list) - 1)
        if round < len(feature_list) - 1:
            return HttpResponse(status=201)
        else:
            return render(request, 'feedback.html')
    else:

        # Get rounds played in total and by the current player
        rounds, roundsnum = popGetList(ImageModel.objects.filter(img__startswith=KEYRING).values_list('id', flat=True), count=21, phase=3)

        if len(rounds.post) >= ImageModel.objects.filter(img__startswith=KEYRING).count():
            # push all to waiting page
            return over(request, 'step03')

        # Single image that will be sent to front-end, will expire in 300 seconds (temporary)
        # sending 21 images at a time
        data = [i.img.url for i in ImageModel.objects.filter(id__in=roundsnum)]
        data.extend([None] * (21 - len(data)))
        instructions = Phase03_instruction.get_queryset(Phase03_instruction) or ['none']

    return render(request, 'step03.html',
                  {'feature': feature_list, 'image_url': data, 'roundnum': len(feature_list), 'previewMode': previewMode, 'instructions': instructions})
