# Load your transformed dataset
with open('data/codebase_chunks.json', 'r') as f:
    transformed_dataset = json.load(f)

# Initialize the VectorDB
base_db = VectorDB("base_db")

# Load and process the data
base_db.load_data(transformed_dataset)
