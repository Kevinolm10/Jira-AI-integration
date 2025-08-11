from django.shortcuts import render

# Create your views here.

def ai_chat(request):
    """Main chat interface view"""
    context = {}
    return render(request, 'ai_chat/chat.html', context)