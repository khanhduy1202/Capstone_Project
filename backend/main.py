from fastapi import FastAPI, Request, status, HTTPException
from decouple import config
from supabase import create_client, Client
from postgrest import APIError
import uuid
from uuid import UUID
from pydantic import BaseModel, EmailStr
from google.generativeai import GenerativeModel
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import google.generativeai as genai
import json
import os
import io
from datetime import date
from datetime import datetime
from enum import Enum
from typing import List, Optional
app = FastAPI()

#Supabase Credentials:
url = config("SUPABASE_URL")
key = config("SUPABASE_KEY")

supabase: Client = create_client(url,key)

#AI GEMINI Credentials:
API_KEY = "AIzaSyA8l6_LJc_cJzwzOVBFA2zu1z8Tg1-3zWM"
MODEL_NAME = "gemini-1.5-pro"

with open("prompts.json", "r") as f:
    PROMPTS = json.load(f)

config = {
    "temperature": 0.9,
    "top_k": 1,
    "top_p": 1,
    "max_output_tokens": 2048,
}

safety_settings = [
    {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
    {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
    {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
    {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE},
]

genai.configure(api_key=API_KEY)
model = GenerativeModel(
    model_name=MODEL_NAME,
    generation_config=config,
    safety_settings=safety_settings,
)

if not os.path.exists("uploads"):
    os.makedirs("uploads")
if not os.path.exists("questions"):
    os.makedirs("questions")

def save_response(response_data, prompt_name):
    file_path = None

    if prompt_name == "Analyse Reading Material":
        file_path = "analysis.json"
        response_data = {"filename": response_data.get("file_name"), "analysis": response_data.get("questions")}
    elif prompt_name == "10 Short Answers":
        file_path = "questions/shortAns.json"
    elif prompt_name == "10 Multiple Choices":
        file_path = "questions/multiChoices.json"
    elif prompt_name in ["10 True/False", "10 Agree/Disagree", "10 Correct/Incorrect"]:
        file_path = "questions/cards.json"
    elif prompt_name == "10 Highlight":
        file_path = "questions/highlights.json"

    if file_path:
        response_file_content = json.dumps(response_data, indent=3)
        supabase.storage.from_("upload").upload(file_path, response_file_content.encode("utf-8"))
    else:
        print(f"Unknown prompt name: {prompt_name}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown prompt name: {prompt_name}")
    
    return response_data



uploaded_file = None


#AI API endpoints
@app.get("/prompts")
def get_prompts():
    return {"prompts": [prompt["name"] for prompt in PROMPTS.values()]}

uploaded_file = None

@app.post("/upload")
async def upload_file(request: Request):
    global uploaded_file
    print("Backend - Receiving File Content...")
    try:
        body_text = (await request.body()).decode("utf-8")
        file_name, file_content = body_text.split("\n", 1)  

        uploaded_file = file_name
        print(uploaded_file)
        
        #Supabase bucket config + connect
        supabase: Client = create_client(url, key)
        bucket_name = "upload"
        
        # Check if the file already exists in Supabase Storage
        existing_file = supabase.storage.from_(bucket_name).list(path=file_name)
        if existing_file:
            return {"error": f"File with name '{file_name}' already exists"}
        
        #Upload file to Supabase storage
        file_path = f"texts/{file_name}"
        supabase.storage.from_("upload").upload(file_path, file_content.encode("utf-8"))
        return {"message": f"File content received and saved as {file_name}"}

    except Exception as e:
        print("Backend - General Error:", e)
        return {"error": f"An error occurred: {str(e)}"}

@app.get("/generate")
async def generate_response(prompt_key: str, assessmentId: str):
    global uploaded_file
    print("Backend - Generating Response...")

    try:
        print("Prompt Key:", prompt_key)

        selected_prompt = next(
            (p for p in PROMPTS.values() if p["name"] == prompt_key), None
        )
        if selected_prompt is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="prompt not found")
        
        print("Retrieve file content from assessmentId..")        
        file_content = get_assessment_file_content(assessmentId)["file_content"]

        response = model.generate_content(contents=[file_content.decode("utf-8"), selected_prompt["content"], 
        "Determine whether the following questions are literal (answer can be found directly in the text) or inferential (require thinking and reasoning beyond the text) based on their provided answers. Output the result as a key after 'answer', like this: {...'answer': 'answer 1', 'category': 'literal/inferential'}, {...'answer': 'answer 2', 'category': 'literal/inferential'}"
        ])
        print("Raw Response Text:", response.text) 
        
        response_text = response.text

        response_data = {
            "prompt": selected_prompt["name"],
            "questions": response_text,
            "file_name": uploaded_file,
        }

        response_final = save_response(response_data, prompt_key) 

        return {"response": response_final}
    except Exception as e:
        print("Backend - General Error:", e)
        raise HTTPException(status_code=500, detail=str(e))

    
@app.post("/save_questions", status_code=status.HTTP_201_CREATED)
async def save_questions(request: Request):
    """ Saves the selected questions to a JSON file and then to the Supabase database. """
    try:
        questions_text = (await request.body()).decode("utf-8")
        print("Backend - Received Questions Text:", questions_text)

        questions = json.loads(questions_text)
        if not questions:
            return {"error": "No questions received"}

        print("Backend - Parsed Questions:", questions)

        # Save questions to local JSON file
        file_path = os.path.join(os.path.dirname(__file__), "questionsDtb.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(questions, f, indent=3)

        # Save questions to Supabase database
        for question in questions:
            # Check if the question already exists
            existing_question = supabase.table("Question").select("*").eq("Question", question["Question"]).execute()
            if existing_question.data:
                print(f"Question '{question['Question']}' already exists, skipping...")
                continue

            # Insert new question into Supabase
            try:
                result = supabase.table("Question").insert(question).execute()
                if not result.data:
                    raise HTTPException(status_code=500, detail="Failed to create question")
            except APIError as e:
                if "foreign key constraint" in str(e).lower():
                    if "assessmentid" in str(e).lower():
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Assessment with ID {question.get('assessmentID', None)} does not exist")
                    else:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Foreign key constraint failed")
                else:
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

        return {"message": "Questions saved successfully!"}
    except Exception as e:
        print(f"Error saving questions: {e}")
        return {"error": f"An error occurred: {str(e)}"}
    
@app.post("/submit_quiz")
async def submit_quiz(request: Request):
    try:
        quiz_data = await request.json()
        print("Quiz Data Received:", quiz_data)

        return {"message": "Quiz received successfully!"}

    except Exception as e:
        print("Backend - General Error:", e)
        return {"error": f"An error occurred: {str(e)}"}

#--------------------------------------------------------------------------------------#

#Supabase endpoints:

#Get all students
@app.get("/students")
def get_students():
    students = supabase.table("student").select("*").execute()
    return students

#Get specific student based on UUID
@app.get("/student/{id}")
def get_student(id:UUID):
    student = supabase.table("student").select("*").eq("Studentid",id).execute()
    return student

@app.get("/class/students")
def get_class_students(class_id:UUID):
    try:
        students = supabase.table("student").select("*").eq("class",class_id).execute()
        print(students)
        return students
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

#Get all classes
@app.get("/classes")
def get_classes():
    classes = supabase.table("Class").select("*").execute()
    return classes

#Get specifc class based on UUID
@app.get("/class/{id}")
def get_class(id:UUID):
    specificClass = supabase.table("Class").select("*").eq("ClassNumber",id).execute()
    return specificClass

#Get all assessments
@app.get("/assessments")
def get_assessments():
    assessments = supabase.table("Assessment").select("*").execute()
    return assessments

#Get specific assessment based on UUID
@app.get("/assessment/{id}")
def get_assessment(id:UUID):
    assessment = supabase.table("Assessment").select("*").eq("Assessmentid",id).execute()
    return assessment

#Get all questions
@app.get("/questions")
def get_questions():
    questions = supabase.table("Question").select("*").execute()
    return questions

#Get specific question based on UUID
@app.get("/question/{id}")
def get_question(id:UUID):
    question = supabase.table("Question").select("*").eq("QuestionID",id).execute()
    return question

#Get specific questions based on assessment id
@app.get("/question/assessment/{id}")
def get_question(id:UUID):
    question = supabase.table("Question").select("*").eq("AssessmentID",id).execute()
    return question

#Get all skills
@app.get("/skills")
def get_skills():
    skills = supabase.table("skill").select("*").execute()
    return skills

#Get specific skill:
@app.get("/skill/{id}")
def get_skill(id:UUID):
    skill = supabase.table("skill").select("*").eq("skillid",id).execute()
    return skill

#Get all question skill:
@app.get("/questionskills")
def get_qnsk():
    qnsk = supabase.table("QuestionSkill").select("*").execute()
    return qnsk

#Get specific question skill:
@app.get("/questionskill/{id}")
def get_qnsk(id:UUID):
    qnsk = supabase.table("QuestionSkill").select("*").eq("QuestionID",id).execute()
    return qnsk

#Get all answers
@app.get("/studentanswers")
def get_answers():
    answers = supabase.table("StudentAnswer").select("*").execute()
    return answers

#Get answer based on answer id
@app.get("/studentanswerid/{answerid}")
def get_answer_answerid(answerid:UUID):
    answer = supabase.table("StudentAnswer").select("*").eq("AnswerID",answerid).execute()
    return answer

#Get answer based on question id
@app.get("/answerquesid/{questionid}")
def get_answer_questionid(questionid:UUID):
    answer = supabase.table("Question").select("Answer").eq("QuestionID",questionid).execute()
    return answer

#Get all results
@app.get("/results")
def get_results():
    results = supabase.table("AssessmentResults").select("*").execute()
    return results

#Get result based on result id
@app.get("/resultid/{id}")
def get_result_resultid(id:UUID):
    result = supabase.table("AssessmentResults").select("*").eq("ResultID",id).execute()
    return result

#Get result based on student id
@app.get("/resultstudentid/{id}")
def get_result_studentid(id:UUID):
    result = supabase.table("AssessmentResults").select("*").eq("StudentID",id).execute()
    return result

#Create student
class StudentSchema(BaseModel):
    name: str
    email: EmailStr
    class_id: str

@app.post("/student/", status_code=status.HTTP_201_CREATED)
def create_student(student:StudentSchema):
    #UUID for student id
    student_id = str(uuid.uuid4())

    #prepare data
    new_student = {
        "Studentid": student_id,
        "name": student.name,
        "email": student.email,
        "class": student.class_id
    }

    try:
        #insert new student into supa
        result = supabase.table("student").insert(new_student).execute()

        #check insertion
        if result.data:
            return {"message": "Student created successfully", "student": result.data[0]}
        else:
            raise HTTPException(status_code=500, detail="Failed to create student")
    except APIError as e:
        if "foreign key constraint" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Class with ID {student.class_id} does not exist")
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

#Create assessment:
class AssessmentSchema(BaseModel):
    title: str
    topic: str
    class_id: str
    due_date: str
    reading_file_name: str


@app.post("/assessment/", status_code=status.HTTP_201_CREATED)
def create_assessment(assessment: AssessmentSchema):
    # Generate uuid for assessmentid
    assessment_id = str(uuid.uuid4())

    # Convert due_date string to datetime object
    due_date = datetime.strptime(assessment.due_date, '%Y-%m-%d')

    # Prepare data
    new_assessment = {
        "Assessmentid": assessment_id,
        "Title": assessment.title,
        "Topic": assessment.topic,
        "Class": assessment.class_id,
        "dueDate": due_date.strftime('%Y-%m-%d'),
        "ReadingFileName": assessment.reading_file_name
    }

    try:
        # Insert new assessment into Supabase
        result = supabase.table("Assessment").insert(new_assessment).execute()
        # Check insertion
        if result.data:
            return {"message": "Assessment created successfully", "assessment": result.data[0]}
        else:
            raise HTTPException(status_code=500, detail="Failed to create assessment")
    except APIError as e:
        if "foreign key constraint" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Class with ID {assessment.class_id} does not exist")
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.put("/update_assessment")
def update_assessment(assessment_id: str, title: Optional[str] = None, topic: Optional[str] = None, due_date: Optional[str] = None):

    updated_assessment = {}

    if title:
        updated_assessment["Title"] = title

    if topic:
        updated_assessment["Topic"] = topic
    
    if due_date:
        try:
            formatted_due_date = datetime.strptime(due_date, '%Y-%m-%d')
            updated_assessment["dueDate"] = formatted_due_date.isoformat()
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format. Use 'YYYY-MM-DD' format")

    print("updated_assessment:", updated_assessment)

    try:
        if updated_assessment == {}: 
            raise HTTPException(status_code=status.HTTP_200_OK, detail="No fields to update")
        else:
            print("Updating assessment...")
            result = supabase.table("Assessment").update(updated_assessment).eq("Assessmentid", assessment_id).execute()
            if result.data:
                return {"message": "Assessment updated successfully", "assessment": result.data[0]}
            else:
                raise HTTPException(status_code=500, detail="Failed to update assessment")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.delete("/delete_assessment")
def delete_assessment(assessment_id: str):
    try:
        result = supabase.table("Assessment").delete().eq("Assessmentid", assessment_id).execute()
        if result.data:
            return {"message": "Assessment deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Assessment not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
#Retrieve file content from assessmentId
@app.get("/assessment/{assessment_id}/file")
def get_assessment_file_content(assessment_id: str):
    try:
        # Retrieve assessment based on assessment_id from Supabase
        assessment = supabase.table("Assessment").select("*").eq("Assessmentid", assessment_id).execute()
        if not assessment.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
        
        # Retrieve file name from table
        reading_file_name = assessment.data[0]['ReadingFileName']
        
        # Construct the file path within the "texts" folder
        file_path = f"texts/{reading_file_name}"
        
        # Retrieve file content from Supabase Storage
        file_content = supabase.storage.from_("upload").download(file_path)
        
        return {"file_content": file_content}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# Create Assessment Result
class ResultSchema(BaseModel):
    assessmentID: str
    studentID: str
    analysis: str
    marks: int

@app.post("/assessmentResults/", status_code=status.HTTP_201_CREATED)
def create_assessmentResult(result: ResultSchema):
    result_id = str(uuid.uuid4())
    new_result = {
        "ResultID": result_id,
        "AssessmentID": result.assessmentID,
        "StudentID": result.studentID,
        "Analysis": result.analysis,
        "Marks": result.marks
    }
    try:
        result = supabase.table("AssessmentResults").insert(new_result).execute()
        if result.data:
            return {"message": "Result created successfully", "result": result.data[0]}
        else:
            raise HTTPException(status_code=500, detail="Failed to create result")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Create Class
@app.post("/class/", status_code=status.HTTP_201_CREATED)
def create_class():
    class_id = str(uuid.uuid4())
    new_class = {
        "ClassNumber": class_id,
    }
    try:
        result = supabase.table("Class").insert(new_class).execute()
        if result.data:
            return {"message": "Class created successfully", "class": result.data[0]}
        else:
            raise HTTPException(status_code=500, detail="Failed to create class")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
#Create StudentAnswer
class StudentAnswerSchema(BaseModel):
    question_id: str
    student_id: str
    answer: str
@app.post("/student_answer/", status_code=status.HTTP_201_CREATED)
def create_student_answer(student_answer: StudentAnswerSchema):
    # Generate UUID for AnswerID
    answer_id = str(uuid.uuid4())
    
    #Prepare data
    new_student_answer = {
        "AnswerID": answer_id,
        "QuestionID": student_answer.question_id,
        "StudentID": student_answer.student_id,
        "Answer": student_answer.answer
    }
    
    try:
        # Insert new student answer into Supabase
        result = supabase.table("StudentAnswer").insert(new_student_answer).execute()
    # Check insertion
        if result.data:
            return {"message": "Student answer created successfully", "student_answer": result.data[0]}
        else:
            raise HTTPException(status_code=500, detail="Failed to create student answer")
    except APIError as e:
        if "foreign key constraint" in str(e).lower():
            if "questionid" in str(e).lower():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Question with ID {student_answer.question_id} does not exist")
            elif "studentid" in str(e).lower():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Student with ID {student_answer.student_id} does not exist")
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

#Create skill
class SkillImportance(str, Enum):
    HIGH = "High"
    NORMAL = "Normal"
    LOW = "Low"

class SkillSchema(BaseModel):
    name: str
    importance: SkillImportance

@app.post("/skill/", status_code=status.HTTP_201_CREATED)
def create_skill(skill: SkillSchema):
    # Generate UUID for skillid
    skill_id = str(uuid.uuid4())

    # Prepare data
    new_skill = {
        "skillid": skill_id,
        "name": skill.name,
        "importance": skill.importance.value
    }

    try:
        # Insert new skill into Supabase
        result = supabase.table("skill").insert(new_skill).execute()

        # Check insertion
        if result.data:
            return {"message": "Skill created successfully", "skill": result.data[0]}
        else:
            raise HTTPException(status_code=500, detail="Failed to create skill")
    except APIError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

#Create question  skill
class QuestionSkillSchema(BaseModel):
    question_id: str
    skill_id: str
@app.post("/question_skill/", status_code=status.HTTP_201_CREATED)
def create_question_skill(question_skill: QuestionSkillSchema):
    # Prepare data
    new_question_skill = {
        "QuestionID": question_skill.question_id,
        "SkillID": question_skill.skill_id
    }

    try:
        # Insert new question skill into Supabase
        result = supabase.table("QuestionSkill").insert(new_question_skill).execute()

        # Check insertion
        if result.data:
            return {"message": "Question skill created successfully", "question_skill": result.data[0]}
        else:
            raise HTTPException(status_code=500, detail="Failed to create question skill")
    except APIError as e:
        if "foreign key constraint" in str(e).lower():
            if "questionid" in str(e).lower():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Question with ID {question_skill.question_id} does not exist")
            elif "skillid" in str(e).lower():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Skill with ID {question_skill.skill_id} does not exist")
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

#Create questions
class QuestionType(str, Enum):
    MCQ = "MCQ"
    FC = "FC"
    HL = "HL"
    SA = "SA"

class Category(str, Enum):
    LITERAL = "Literal"
    INFERENTIAL = "Inferential"
    
class QuestionSchema(BaseModel):
    AssessmentID: str
    Question: str
    Category: Category
    Type: QuestionType
    Options: List[str]
    Answer: str

@app.post("/question/", status_code=status.HTTP_201_CREATED)
def create_question(question: QuestionSchema):
    # Generate UUID for QuestionID
    question_id = str(uuid.uuid4())

    # Prepare data
    new_question = {
        "QuestionID": question_id,
        "AssessmentID": question.AssessmentID,
        "Question": question.Question,
        "Category": question.Category.value,
        "Type": question.Type.value,
        "Options": question.Options,
        "Answer": question.Answer
    }

    try:
        # Insert new question into Supabase
        result = supabase.table("Question").insert(new_question).execute()
        # Check insertion
        if result.data:
            return {"message": "Question created successfully", "question": result.data[0]}
        else:
            raise HTTPException(status_code=500, detail="Failed to create question")
    except APIError as e:
        if "foreign key constraint" in str(e).lower():
            if "assessmentid" in str(e).lower():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Assessment with ID {question.AssessmentID} does not exist")
            else:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Foreign key constraint failed")
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))