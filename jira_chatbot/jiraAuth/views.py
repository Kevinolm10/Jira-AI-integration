from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

# Create your views here.
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('chat')
        else:
            messages.error(request, 'Authentication failed. Please check your JIRA email and API token. If you have MFA enabled, you must use an API token instead of your password.')

    return render(request, 'auth/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')