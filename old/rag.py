 def rag_query(tokenizer, model, device, query):
    # Generate query embedding
    query_embedding = generate_embeddings(
        tokenizer=tokenizer, model=model, device=device, text=query
    )[1]

    # Retrieve relevant embeddings from the database
    retrieval_condition = get_retrieval_condition(query_embedding)

    conn = get_connection()
    register_vector(conn)
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT doc_fragment FROM embeddings WHERE {retrieval_condition} LIMIT 5"
    )
    retrieved = cursor.fetchall()

    rag_query = ' '.join([row[0] for row in retrieved])

    query_template = template.format(context=rag_query, question=query)

    input_ids = tokenizer.encode(query_template, return_tensors="pt")

    # Generate the response
    generated_response = model.generate(input_ids.to(device), max_new_tokens=50, pad_token_id=tokenizer.eos_token_id)
    return tokenizer.decode(generated_response[0][input_ids.shape[-1]:], skip_special_tokens=True)