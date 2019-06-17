from django.http import *
from django.shortcuts import render_to_response,redirect,render

def profile(request):
    return render(request, 'profile.html')

def over(request, phase=None):
    return render(request, 'over.html', {'phase': phase})

def feedback(request):
    return render(request, 'feedback.html')

def about(request):
    return render(request, 'about.html')

def handler404(request, *args, **argv):
    return render(request, '404.html', status=404)

def handler500(request, *args, **argv):
    return render(request, '500.html', status=500)

def phase01b(request):
    return render(request, 'phase01b.html')

def stop(request):
    return render(request, 'stop.html')
