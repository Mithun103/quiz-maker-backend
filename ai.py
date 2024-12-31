import json
import fitz
from groq import Groq
import random
import string
import json
import os
# Initialize the Groq client
client = Groq(api_key="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")
def add_topic_and_qid_to_json(json_data, topic, qid):
    """
    Add a topic and qid to the top of the JSON array.
    
    :param json_data: The original JSON array (list of dictionaries)
    :param topic: The topic to be added
    :param qid: The question ID to be added
    :return: A new JSON array with the topic and qid at the top
    """
    # Create the new item with topic and qid
    new_item = {
        "topic": topic,
        "qid": qid
    }
    
    # Add the new item to the top of the array
    new_json_data = [new_item] + json_data
    
    return new_json_data
# Function to send question to the LLM and stream response
def generate_unique_uid():
    """
    Generate a unique 4-character UID that does not exist in the existing JSON data.
    
    :param existing_data: The original JSON array (list of dictionaries)
    :return: A unique 4-character UID
    """
    with open('./existing_ids.json', 'r') as file:  
      existing_data = json.load(file)
    # Generate a random 4-character UID
    def generate_uid():
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    
    # Check if the UID already exists in the existing JSON data
    existing_uids = {entry.get("uid") for entry in existing_data if "uid" in entry}
    
    # Generate a unique UID
    new_uid = generate_uid()
    while new_uid in existing_uids:
        new_uid = generate_uid()
    
    # Add the new UID to the existing data (assuming each item should have a unique UID)
    existing_data.append({"uid": new_uid})
    with open('./existing_ids.json', 'w') as file:
        json.dump(existing_data, file, indent=4)
                  
    return new_uid

def get_llm_response(question):
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": "You are a very helpful assistant you generate a JSON format directly.without any support messages"
            },
            {
                "role": "user",
                "content": question
            }
        ],
        temperature=1,
        max_tokens=4096,
        top_p=0.65,
        stream=True,
        stop=None,
    )
    
    response_content = ""
    for chunk in completion:
        delta = chunk.choices[0].delta.content
        if delta:
            print(delta, end="", flush=True)
            response_content += delta
    print()
    return response_content.strip()

# Extract text from PDF
def extract_text_from_pdf(pdf_path):
    with fitz.open(pdf_path) as pdf:
        text = "".join(page.get_text() for page in pdf)
    return text
import re

def strip_between_backticks(input_text):
    # Use regular expression to find content between triple backticks starting with 'json'
    matches = re.findall(r'```json(.*?)```', input_text, re.DOTALL)

    # If there's a match, strip the content and return
    if matches:
        extracted_text = matches[0].strip()  # Remove leading and trailing whitespace/newlines
        return extracted_text
    return None
  # Return None if no match is found
# Generate MCQs from extracted PDF text
def generate_mcqs_from_pdf(pdf_path):
    # Extract text from the PDF
    text = extract_text_from_pdf(pdf_path)
    
    # Extract topic from pdf_path more safely
    try:
        # Handle both Windows and Unix-style paths
        filename = os.path.basename(pdf_path)
        topic = os.path.splitext(filename)[0]
    except Exception as e:
        print(f"Error extracting topic from path: {e}")
        topic = "general"  # fallback topic name
    
    # Construct the prompt for the LLM
    question = (
        f"Analyze the following text and create only {10} multiple-choice questions randomly with the following structure without support messages: "
        "Return a JSON array of list of objects where each question contains: question_no, question, 4 choices (A, B, C, D), and the correct answer.\n"
        f"Text: {text}"
    )
    example=[{
        "question_no": "..",
        "question": ".........",
        "A": "........",
        "B": "..............",
        "C": "................",
        "D": "...............",
        "correct_answer": "......",
    }]
    # Get the response from the LLM
    response = get_llm_response(question+json.dumps(example))
    
    # Parse the response into a JSON object
    try:
        mcqs = json.loads(response)  # Convert the string response into a JSON object
    except json.JSONDecodeError:
        print("Error decoding JSON response.")
        return None

    # Generate unique ID and add topic metadata
    uid = generate_unique_uid()
    fin = add_topic_and_qid_to_json(mcqs, topic, uid)
    return fin


# Evaluate user response based on MCQs
def evaluate_grades(questions):
    """
    Evaluate the grades based on user answers and correct answers.
    
    Parameters:
        questions (list): A list of question objects with 'user_answer' and 'correct_answer'.
    
    Returns:
        dict: The grade and the total number of questions.
    """
    total_questions = len(questions)
    correct_answers = 0

    for question in questions:
        if question.get('user_answer') == question.get('correct_answer'):
            correct_answers += 1

    return{
        'grade': correct_answers,
        'out_of': total_questions
}
def evaluate(sample):
    """
    Evaluate the user's responses and get feedback and recommendations using an LLM.

    Parameters:
        sample (list): The list of quiz questions and metadata.

    Returns:
        dict: Contains qid, grade, out_of, feedback, and recommendation.
    """
    # Extract metadata and questions
    metadata = sample[0]
    qid = metadata.get('qid', 'Unknown QID')
    questions = sample[1:]

    # Ensure user answers exist in the questions
    for question in questions:
        if 'user_answer' not in question:
            question['user_answer'] = None

    # Get the grade evaluation
    grade_result = evaluate_grades(questions)

    # Construct the prompt for the LLM
    llm_prompt = (
        "Analyze the following response and provide feedback concisely without any grade or score strictly. "
        "Return a JSON object where feedback contains: three lines of feedback without mentioning the grade scored, "
        "and in recommendation: suggestions for improving. "
        f"Questions: {json.dumps(questions)},strictly follow the example"
    )
    example2={
  "feedback": [
    "You have a good understanding of the material.",
    "Consider reviewing the concepts related to advanced topics."
  ],
  "recommendation": {
    "additional_resources": [
      "Advanced React Documentation",
      "Frontend Masters - React Advanced Course"
    ]}}

    # Simulated LLM response (replace with actual LLM call)
    response = get_llm_response(llm_prompt+json.dumps(example2))
    print(response)
    # Parse the response
    try:
        evaluation = json.loads(response)
    except json.JSONDecodeError:
        evaluation = {"feedback": "Unable to evaluate response.", "recommendation": "Retry with valid input."}

    # Return the result
    return {
        'qid': qid,
        'grade': grade_result['grade'],
        'out_of': grade_result['out_of'],
        'feedback': evaluation.get("feedback"),
        'recommendation': evaluation.get("recommendation")
    }


# Sample MCQ JSON data for user evaluation
sample_json = [
    {
        "question_no": 1,
        "question": "What is the primary function of an Operating System?",
        "A": "To manage hardware resources",
        "B": "To manage software resources",
        "C": "To act as an interface between the user and the computer hardware",
        "D": "To manage network resources",
        "correct_answer": "C",
        "user_answer": "C"
    },
    {
        "question_no": 2,
        "question": "What is Memory Management in an Operating System?",
        "A": "Managing secondary memory",
        "B": "Managing primary memory",
        "C": "Managing virtual memory",
        "D": "Managing cache memory",
        "correct_answer": "B",
        "user_answer": "A"
    },
    {
        "question_no": 3,
        "question": "What is the main difference between Multiprogrammed Batch Systems and Time-Sharing Systems?",
        "A": "Multiprogrammed Batch Systems maximize processor use, while Time-Sharing Systems minimize response time",
        "B": "Multiprogrammed Batch Systems minimize response time, while Time-Sharing Systems maximize processor use",
        "C": "Multiprogrammed Batch Systems use multiple processors, while Time-Sharing Systems use a single processor",
        "D": "Multiprogrammed Batch Systems use a single processor, while Time-Sharing Systems use multiple processors",
        "correct_answer": "A",
        "user_answer": "B"
    },
    {
        "question_no": 4,
        "question": "What is a Distributed Operating System?",
        "A": "An operating system that runs on a single processor",
        "B": "An operating system that runs on multiple processors",
        "C": "An operating system that manages a network of computers",
        "D": "An operating system that manages a single computer",
        "correct_answer": "B",
        "user_answer": "B"
    },
    {
        "question_no": 5,
        "question": "What is the primary purpose of a Network Operating System?",
        "A": "To manage a single computer",
        "B": "To manage a network of computers",
        "C": "To manage a distributed system",
        "D": "To manage a real-time system",
        "correct_answer": "B",
        "user_answer": "B"
    },
    {
        "question_no": 6,
        "question": "What is a Real-Time Operating System?",
        "A": "An operating system that responds to inputs in a short time interval",
        "B": "An operating system that responds to inputs in a long time interval",
        "C": "An operating system that manages a network of computers",
        "D": "An operating system that manages a single computer",
        "correct_answer": "A",
        "user_answer": "A"
    },
    {
        "question_no": 7,
        "question": "What is the difference between Hard Real-Time Systems and Soft Real-Time Systems?",
        "A": "Hard Real-Time Systems guarantee critical tasks complete on time, while Soft Real-Time Systems do not",
        "B": "Soft Real-Time Systems guarantee critical tasks complete on time, while Hard Real-Time Systems do not",
        "C": "Hard Real-Time Systems use multiple processors, while Soft Real-Time Systems use a single processor",
        "D": "Soft Real-Time Systems use multiple processors, while Hard Real-Time Systems use a single processor",
        "correct_answer": "A",
        "user_answer": "B"
    },
    {
        "question_no": 8,
        "question": "What is the interface between a process and an operating system?",
        "A": "System calls",
        "B": "API calls",
        "C": "Library calls",
        "D": "Function calls",
        "correct_answer": "A",
        "user_answer": "C"
    },
    {
        "question_no": 9,
        "question": "What are the five types of system calls?",
        "A": "Process Control, File Management, Device Management, Information Maintenance, and Communication",
        "B": "Process Control, File Management, Device Management, Information Maintenance, and Synchronization",
        "C": "Process Control, File Management, Device Management, Information Maintenance, and Networking",
        "D": "Process Control, File Management, Device Management, Information Maintenance, and Security",
        "correct_answer": "A",
        "user_answer": "A"
    },
    {
        "question_no": 10,
        "question": "What is the purpose of the CreateProcess() system call in Windows?",
        "A": "To create a new process",
        "B": "To terminate a process",
        "C": "To read from a file",
        "D": "To write to a file",
        "correct_answer": "A",
        "user_answer": "A"
    }
]
