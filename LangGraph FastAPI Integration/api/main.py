import os
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic_models import QueryInput, QueryResponse, DocumentInfo, DeleteFileRequest
from db_utils import insert_chat_history, get_chat_history, get_all_documents, insert_document_record, delete_document_record
from chroma_utils import index_document_to_chroma, delete_doc_from_chroma
from langgraph_agent import agent
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
import logging
import shutil
from utils import get_or_create_session_id, history_to_lc_messages, append_message
from langchain_utils import contextualise_chain
logging.basicConfig(filename='app.log', level=logging.INFO)
app = FastAPI()

# Load environment variables from .env file
load_dotenv(override=True)

@app.post("/chat", response_model=QueryResponse)
def chat(query_input: QueryInput):
    """
    Main chat endpoint using the LangGraph agent with routing, RAG, and web search capabilities.
    """
    session_id = get_or_create_session_id(query_input.session_id)
    logging.info(f"Session ID: {session_id}, User Query: {query_input.question}, Model: {query_input.model.value}")

    try:
        # Convert chat history to LangChain messages
        chat_history = get_chat_history(session_id)
        messages = history_to_lc_messages(chat_history)
        # Add current user message

                # 2. Generate a stand-alone question
        standalone_q = contextualise_chain.invoke({
            "chat_history": messages,
            "input": query_input.question,
        })

        messages = append_message(messages, HumanMessage(content=standalone_q))
        # Invoke the LangGraph agent
        # config = {"configurable": {"thread_id": session_id}}
        result = agent.invoke(
            {"messages": messages}
        )

        # Get the last AI message
        last_message = next((m for m in reversed(result["messages"])
                           if isinstance(m, AIMessage)), None)

        if last_message:
            answer = last_message.content
        else:
            answer = "I apologize, but I couldn't generate a response at this time."

        # Store the conversation
        insert_chat_history(session_id, query_input.question, answer, query_input.model.value)
        logging.info(f"Session ID: {session_id}, AI Response: {answer}")

        return QueryResponse(answer=answer, session_id=session_id, model=query_input.model)

    except Exception as e:
        logging.error(f"Error in chat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

from fastapi import UploadFile, File, HTTPException

@app.post("/upload-doc")
def upload_and_index_document(file: UploadFile = File(...)):
    allowed_extensions = ['.pdf', '.docx', '.html']
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed types are: {', '.join(allowed_extensions)}")
    
    temp_file_path = f"temp_{file.filename}"
    
    try:
        # Save the uploaded file to a temporary file
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        file_id = insert_document_record(file.filename)
        success = index_document_to_chroma(temp_file_path, file_id)
        
        if success:
            return {"message": f"File {file.filename} has been successfully uploaded and indexed.", "file_id": file_id}
        else:
            delete_document_record(file_id)
            raise HTTPException(status_code=500, detail=f"Failed to index {file.filename}.")
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@app.get("/list-docs", response_model=list[DocumentInfo])
def list_documents():
    return get_all_documents()

@app.post("/delete-doc")
def delete_document(request: DeleteFileRequest):
    # Delete from Chroma
    chroma_delete_success = delete_doc_from_chroma(request.file_id)

    if chroma_delete_success:
        # If successfully deleted from Chroma, delete from our database
        db_delete_success = delete_document_record(request.file_id)
        if db_delete_success:
            return {"message": f"Successfully deleted document with file_id {request.file_id} from the system."}
        else:
            return {"error": f"Deleted from Chroma but failed to delete document with file_id {request.file_id} from the database."}
    else:
        return {"error": f"Failed to delete document with file_id {request.file_id} from Chroma."}
