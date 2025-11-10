import chromadb
from google import genai
from google.api_core import retry


def get_genai_client():
    """Prompt user for a Google API key and validate it until correct."""
    while True:

        api_key = input("Enter your Google API key: ").strip()

        try:
            genai_client = genai.Client(api_key=api_key)
            genai_client.models.list()
            return genai_client
        except genai.errors.APIError as e:
            print("Please enter a valid API key.\n")


genai_client = get_genai_client()


# Non-persistent client
chroma_client = chromadb.Client()
# We can create a persistent client by passing a path to the database
# chroma_client = chromadb.PersistentClient(path="chroma-db")

# --- Reservation & Booking Rules ---
with open("data/reservation.txt", "r") as f:
    rules = f.read().splitlines()
# --- Operational and Backend Process Steps ---
with open("data/operational.txt", "r") as f:
    rules.extend(f.read().splitlines())


collection = chroma_client.create_collection(name="railways_qa")


# Now let's add the data to the collection
collection.add(
    ids=[str(i) for i in range(len(rules))],
    documents=rules,
    metadatas=[{"rule_no": i + 1} for i in range(len(rules))],
)
# print(collection.peek())

questions = [
    "How can I book the railway tickets?",
    "When the online booking window for tatkal tickets opens?",
    "In how many days I can get refund if the confirm ticket is not issued?",
    # "What is the ticket fare from Mumbai to Pune?",
    # "Which animal is referred to as the 'king of the forest'?",
]

results = collection.query(query_texts=questions, n_results=5)

prompt = f"""You are a helpful and informative bot that answers questions related to railway reservation and railway working using text from the reference passage included below. 
Be sure to respond in a complete sentence, being comprehensive, including all relevant background information. 
However, you are talking to a non-technical audience, so be sure to break down complicated concepts and 
strike a friendly and converstional tone. If the passage is irrelevant to the answer, you may ignore it. 
If question is not related to the railway reservation or ticket booking or queries related to railway system, answer with "I am allowed to response the questions related to railway reservation only. You can user other General Purpose models".
If question is related to the railway reservation but not given in the passage, answer with "I can't find the answer in the given passages. Searching for the web for best prediction". And then try to response the question using the web.
"""


# Helper to retry when per-minute quota is reached.
is_retriable = lambda e: (isinstance(e, genai.errors.APIError) and e.code in {429, 503})


@retry.Retry(predicate=is_retriable)
def get_response(prompt):
    return genai_client.models.generate_content(
        model="gemini-2.0-flash", contents=prompt
    )


for i, question in enumerate(questions):
    prompt += f"QUESTION: {question}\n"
    for result in results["documents"][i]:
        prompt += f"PASSAGE: {result}\n"

    answer = get_response(prompt)
    print(f"\nQuestion: {question}\n Answer: {answer.text}")
