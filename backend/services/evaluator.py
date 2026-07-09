from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def evaluate_answer(student, correct):
    vectorizer = TfidfVectorizer()

    vectors = vectorizer.fit_transform([student, correct])
    score = cosine_similarity(vectors[0], vectors[1])[0][0]

    return round(score * 100, 2)