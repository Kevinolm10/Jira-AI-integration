import ollama

def generate_response(prompt):
    stream = ollama.chat(
        model='llama3:latest',
        messages = [{'role': 'user', 
                     'content': prompt}],
        stream=True,
    )
    for chunk in stream:
        yield chunk['message']['content']
