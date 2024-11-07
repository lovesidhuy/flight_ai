import os
from dotenv import load_dotenv
import requests
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores.faiss import FAISS
from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain.schema import HumanMessage, AIMessage
from langchain_core.prompts import MessagesPlaceholder
from langchain.chains.history_aware_retriever import create_history_aware_retriever

# Load environment variables from .env file
load_dotenv()

def get_amadeus_token():
    auth_url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    try:
        response = requests.post(auth_url, data={
            "grant_type": "client_credentials",
            "client_id": os.getenv("AMADEUS_API_KEY"),
            "client_secret": os.getenv("AMADEUS_API_SECRET")
        })
        response.raise_for_status()
        token = response.json().get("access_token")
        if token:
            print("Token fetched successfully.")
            return token
        else:
            print("Failed to fetch token.")
            return None
    except requests.exceptions.RequestException as e:
        print("Error fetching Amadeus token:", e)
        return None

def get_flight_options(origin, destination, departure_date):
    try:
        token = get_amadeus_token()
        if not token:
            print("Error: Amadeus API token retrieval failed.")
            return []

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        response = requests.get(
            "https://test.api.amadeus.com/v2/shopping/flight-offers",
            headers=headers,
            params={
                "originLocationCode": origin,
                "destinationLocationCode": destination,
                "departureDate": departure_date,
                "adults": 1
            }
        )
        print("Flight API response status:", response.status_code)
        response.raise_for_status()
        return response.json().get("data", [])
    except requests.exceptions.RequestException as e:
        print("Error calling flight API:", e)
        return []

def format_flight_offers(flight_data):
    response = "Here are the best flight options I found:\n\n"
    for offer in flight_data:
        response += f"Flight Offer ID: {offer['id']}\n"
        for itinerary in offer['itineraries']:
            response += f"Total Duration: {itinerary['duration']}\n"
            for segment in itinerary['segments']:
                response += (
                    f"Flight {segment['carrierCode']} {segment['number']} from "
                    f"{segment['departure']['iataCode']} (Terminal {segment['departure'].get('terminal', 'N/A')}) "
                    f"to {segment['arrival']['iataCode']} (Terminal {segment['arrival'].get('terminal', 'N/A')})\n"
                    f"Departure: {segment['departure']['at']} - Arrival: {segment['arrival']['at']}\n"
                    f"Duration: {segment['duration']}\n"
                )
            response += f"Price: {offer['price']['grandTotal']} {offer['price']['currency']}\n\n"
    return response

def get_documents_from_web(url):
    if 'USER_AGENT' not in os.environ:
        os.environ['USER_AGENT'] = 'Mozilla/5.0 (compatible; MyBot/1.0)'

    loader = WebBaseLoader(url)
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=200,
        chunk_overlap=20
    )
    split_docs = splitter.split_documents(docs)
    print(f"Number of split documents: {len(split_docs)}")
    return split_docs

def create_db(docs):
    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    vector_store = FAISS.from_documents(docs, embedding=embedding_model)
    return vector_store

def create_chain(vector_store):
    # Updated prompt with MessagesPlaceholder for chat history
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Answer the user's question based on the context: {context}"),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}")
    ])

    model = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="llama3-8b-8192",
        temperature=0.7
    )

    combine_docs_chain = create_stuff_documents_chain(
        llm=model,
        prompt=prompt
    )

    retriever_prompt = ChatPromptTemplate.from_messages([
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        ("human", "given the above ..")
    ])

    retriever = vector_store.as_retriever()

    history_aware_retriever = create_history_aware_retriever(
        llm=model,
        retriever=retriever,
        prompt=retriever_prompt
    )

    retriever_chain = create_retrieval_chain(
        retriever=history_aware_retriever,
        combine_docs_chain=combine_docs_chain
    )

    return retriever_chain

def process_chat(chain, question, chat_history):
    if "flight options" in question.lower():
        origin = "NYC"  # Replace with extracted user input
        destination = "LAX"  # Replace with extracted user input
        departure_date = "2024-12-25"  # Replace with extracted user input
        flight_data = get_flight_options(origin, destination, departure_date)
        
        # Format and return the response for the user
        return format_flight_offers(flight_data)

    # Continue with other chatbot functionality
    response = chain.invoke({"input": question, "chat_history": chat_history})
    return response.get("answer", "No answer found")

if __name__ == "__main__":
    docs = get_documents_from_web("https://phet-dev.colorado.edu/html/build-an-atom/0.0.0-3/simple-text-only-test-page.html")
    vectorStore = create_db(docs)
    chain = create_chain(vectorStore)

    chat_history = []

    while True:
        user_input = input("You: ")
        if user_input.lower() == 'exit':
            break

        response = process_chat(chain, user_input, chat_history)
        chat_history.append(HumanMessage(content=user_input))
        chat_history.append(AIMessage(content=response))

        print("buddy:", response)