import cohere
from typing import List, Dict, Any, Callable
import json
from tqdm import tqdm

def load_jsonl(file_path: str) -> List[Dict[str, Any]]:
    with open(file_path, 'r') as file:
        return [json.loads(line) for line in file]

def chunk_to_content(chunk: Dict[str, Any]) -> str:
    original_content = chunk['metadata']['original_content']
    contextualized_content = chunk['metadata']['contextualized_content']
    return f"{original_content}\n\nContext: {contextualized_content}" 

def retrieve_rerank(query: str, db, k: int) -> List[Dict[str, Any]]:
    co = cohere.Client(os.getenv("COHERE_API_KEY"))
    
    # Retrieve more results than we normally would
    semantic_results = db.search(query, k=k*10)
    
    # Extract documents for reranking, using the contextualized content
    documents = [chunk_to_content(res) for res in semantic_results]

    response = co.rerank(
        model="rerank-english-v3.0",
        query=query,
        documents=documents,
        top_n=k
    )
    time.sleep(0.1)
    
    final_results = []
    for r in response.results:
        original_result = semantic_results[r.index]
        final_results.append({
            "chunk": original_result['metadata'],
            "score": r.relevance_score
        })
    
    return final_results

def evaluate_retrieval_rerank(queries: List[Dict[str, Any]], retrieval_function: Callable, db, k: int = 20) -> Dict[str, float]:
    total_score = 0
    total_queries = len(queries)
    
    for query_item in tqdm(queries, desc="Evaluating retrieval"):
        query = query_item['query']
        golden_chunk_uuids = query_item['golden_chunk_uuids']
        
        golden_contents = []
        for doc_uuid, chunk_index in golden_chunk_uuids:
            golden_doc = next((doc for doc in query_item['golden_documents'] if doc['uuid'] == doc_uuid), None)
            if golden_doc:
                golden_chunk = next((chunk for chunk in golden_doc['chunks'] if chunk['index'] == chunk_index), None)
                if golden_chunk:
                    golden_contents.append(golden_chunk['content'].strip())
        
        if not golden_contents:
            print(f"Warning: No golden contents found for query: {query}")
            continue
        
        retrieved_docs = retrieval_function(query, db, k)
        
        chunks_found = 0
        for golden_content in golden_contents:
            for doc in retrieved_docs[:k]:
                retrieved_content = doc['chunk']['original_content'].strip()
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

def evaluate_db_advanced(db, original_jsonl_path, k):
    original_data = load_jsonl(original_jsonl_path)
    
    def retrieval_function(query, db, k):
        return retrieve_rerank(query, db, k)
    
    results = evaluate_retrieval_rerank(original_data, retrieval_function, db, k)
    print(f"Pass@{k}: {results['pass_at_n']:.2f}%")
    print(f"Average Score: {results['average_score']}")
    print(f"Total queries: {results['total_queries']}")
    return results
