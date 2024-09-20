import urllib.request
import re

url = ("https://raw.githubusercontent.com/rasbt/"
       "LLMs-from-scratch/main/ch02/01_main-chapter-code/"
       "the-verdict.txt")
file_path = "the-verdict.txt"
urllib.request.urlretrieve(url, file_path)

class SimpleTokenizerV1:
    def __init__(self, vocab):
        self.str_to_int = vocab
        self.int_to_str = {i:s for s,i in vocab.items()}

    def encode(self, text):
        preprocessed = re.split(r'([,.?_!"()\']|--|\\s)', text)
        preprocessed = [
            item.strip() for item in preprocessed if item.strip()
        ]
        ids = [self.str_to_int[s] for s in preprocessed]
        return ids

    def decode(self, ids):
        text = " ".join([self.int_to_str[i] for i in ids]) 

        text = re.sub(r'\s+([,.?!"()\\'])', r'\\1', text)
        return text


# Function to read the content of a file
def read_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

# Function to tokenize text using regular expressions
def tokenize_text(text):
    return re.split(r'(\s)', text)

# Main function
def main():
    # Load the text data
    file_path = 'the_verdict.txt'
    text = read_file(file_path)
    
    # Print the total number of characters and the first 100 characters
    print(f"Total number of characters: {len(text)}")
    print(f"First 100 characters: {text[:100]}")
    
    # Tokenize the text
    tokens = tokenize_text(text)
    
    # Print the first 20 tokens for illustration
    print(f"First 20 tokens: {tokens[:20]}")

if __name__ == "__main__":
    main()
