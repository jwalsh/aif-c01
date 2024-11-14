import json
from typing import List, Dict, Any, Callable, Union
from tqdm import tqdm

def load_jsonl(file_path: str) -> List[Dict[str, Any]]:
    """Load JSONL file and return a list of dictionaries."""
    with open(file_path, 'r') as file:
        return [json.loads(line) for line in file]

def evaluate_retrieval(queries: List[Dict[str, Any]], retrieval_function: Callable, db, k: int = 20) -> Dict[str, float]:
    total_score = 0
    total_queries = len(queries)
    
    for query_item in tqdm(queries, desc="Evaluating retrieval"):
        query = query_item['query']
        golden_chunk_uuids = query_item['golden_chunk_uuids']
        
        # Find all golden chunk contents
        golden_contents = []
        for doc_uuid, chunk_index in golden_chunk_uuids:
            golden_doc = next((doc for doc in query_item['golden_documents'] if doc['uuid'] == doc_uuid), None)
            if not golden_doc:
                print(f"Warning: Golden document not found for UUID {doc_uuid}")
                continue
            
            golden_chunk = next((chunk for chunk in golden_doc['chunks'] if chunk['index'] == chunk_index), None)
            if not golden_chunk:
                print(f"Warning: Golden chunk not found for index {chunk_index} in document {doc_uuid}")
                continue
            
            golden_contents.append(golden_chunk['content'].strip())
        
        if not golden_contents:
            print(f"Warning: No golden contents found for query: {query}")
            continue
        
        retrieved_docs = retrieval_function(query, db, k=k)
        
        # Count how many golden chunks are in the top k retrieved documents
        chunks_found = 0
        for golden_content in golden_contents:
            for doc in retrieved_docs[:k]:
                retrieved_content = doc['metadata'].get('original_content', doc['metadata'].get('content', '')).strip()
                if retrieved_content == golden_content:
                    chunks_found += 1
                    break
        
        query_score = chunks_found / len(golden_contents)
        total_score += query_score
    
    average_score = total_score / total_queries
    pass_at_n = average_score * 100
    return {
        "pass_at_n": pass_at_n,
        "average_score": average_score,
        "total_queries": total_queries
    }

def retrieve_base(query: str, db, k: int = 20) -> List[Dict[str, Any]]:
    """
    Retrieve relevant documents using either VectorDB or ContextualVectorDB.
    
    :param query: The query string
    :param db: The VectorDB or ContextualVectorDB instance
    :param k: Number of top results to retrieve
    :return: List of retrieved documents
    """
    return db.search(query, k=k)

def evaluate_db(db, original_jsonl_path: str, k):
    # Load the original JSONL data for queries and ground truth
    original_data = load_jsonl(original_jsonl_path)
    
    # Evaluate retrieval
    results = evaluate_retrieval(original_data, retrieve_base, db, k)
    print(f"Pass@{k}: {results['pass_at_n']:.2f}%")
    print(f"Total Score: {results['average_score']}")
    print(f"Total queries: {results['total_queries']}")
