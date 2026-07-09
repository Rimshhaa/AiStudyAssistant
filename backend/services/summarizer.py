from transformers import pipeline

summarizer = None

def load_model():
    global summarizer
    if summarizer is None:
        summarizer = pipeline(
            task="summarization",
            model="facebook/bart-large-cnn"
        )

def generate_summary(text):
    load_model()
    result = summarizer(text, max_length=120, min_length=40)
    return result[0]['summary_text']