from sklearn.feature_extraction.text import TfidfVectorizer

def extract_topics(text):
    vectorizer = TfidfVectorizer(max_features=5, stop_words='english')
    vectorizer.fit([text])

    return list(vectorizer.get_feature_names_out())