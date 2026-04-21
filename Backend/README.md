# Backend
backend

# preprocess.py - understanding Tokenization
What does it return: A list of dictionaries that contain a few respective keys allowing for easier look up via the llm processing, ‘file’ that holds the respective file, ‘page’ that holds the type of page being looked at, ‘text’ : text(text contained in the document).


Why?

Unlike modern llm’s we do not have an API that reads files so you have to develop a helper method for that exact purpose of allowing it to read the text from a image-like file (pdf,csv,xlsx etc)
