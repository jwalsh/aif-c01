import matplotlib.pyplot as plt
from sklearn.manifold import TSNE
from gensim.models import Word2Vec
import re
# Build a Large Language Model (From Scratch) (chapter-2) by Sebastian Raschka
# poetry add gensim scikit-learn matplotlib

# Sample data
sentences = [
    "sparrow robin eagle",
    "cat dog lion",
    "paris london newyork",
    "freedom love happiness"
]

# Preprocess the data
def preprocess(sentences):
    processed_sentences = []
    for sentence in sentences:
        words = re.sub("[.,:;'\"!?()]+", "", sentence.lower()).split()
        processed_sentences.append(words)
    return processed_sentences

# Preprocess the sentences
processed_sentences = preprocess(sentences)

# Train the Word2Vec model
model = Word2Vec(sentences=processed_sentences, vector_size=100, window=5, min_count=1, workers=4)

# Words to visualize
words = ["sparrow", "robin", "eagle", "cat", "dog", "lion", "paris", "london", "newyork", "freedom", "love", "happiness"]

# Get word vectors
word_vectors = [model.wv[word] for word in words]

# Reduce dimensions using t-SNE
tsne = TSNE(n_components=2, random_state=0)
word_vectors_2d = tsne.fit_transform(word_vectors)

# Plotting
plt.figure(figsize=(10, 10))
for i, word in enumerate(words):
    plt.scatter(word_vectors_2d[i, 0], word_vectors_2d[i, 1])
    plt.annotate(word, xy=(word_vectors_2d[i, 0], word_vectors_2d[i, 1]), xytext=(5, 2), textcoords='offset points', ha='right', va='bottom')
plt.show()
