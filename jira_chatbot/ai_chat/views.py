from django.shortcuts import render
from django.http import StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from .chat_service import ChatService
import uuid

@csrf_exempt
def ai_chat(request):
    """Main chat interface view"""
    if request.method == "POST":
        user_input = request.POST["user_input"]
        
        # Get or create session ID
        session_id = request.session.get('chat_session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            request.session['chat_session_id'] = session_id
        
        # Process message through chat service
        chat_service = ChatService(session_id)
        
        def response_generator():
            response = chat_service.process_message(user_input)
            for char in response:
                yield char
        
        return StreamingHttpResponse(response_generator(), content_type='text/plain')
    
    return render(request, "ai_chat/chat.html")
