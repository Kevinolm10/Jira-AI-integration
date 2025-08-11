from django.shortcuts import render

# Create your views here.

def ai_chat(request):
    """Main chat interface view"""
    return render(request, 'ai_chat/chat.html')
def ai_chat(request):
    context = {}
    return render(request, 'chat.html', context)