from unittest.mock import patch, mock_open
import unittest
import os
from fastapi.testclient import TestClient
from unittest.mock import patch
import uuid
from main import app  # Ensure 'main' is the correct import

client = TestClient(app)

class BaseTestAPI(unittest.TestCase):

    def mock_supabase_response(self, mock_table, data, status_code=200):
        """Helper method to mock Supabase table response."""
        mock_response = {"data": data, "status_code": status_code}
        mock_table.return_value.select.return_value.execute.return_value = mock_response
        return mock_response

    def make_get_request(self, endpoint):
        """Helper method to make a GET request."""
        return client.get(endpoint)

    def assert_response(self, response, expected_data):
        """Helper method to assert response status and JSON."""
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected_data)


class TestAPI(BaseTestAPI):

    @patch('main.supabase.table')
    def test_get_students(self, mock_table):
        mock_data = [
            {"Studentid": "067207b7-eb56-4e06-978f-d6a419e6ca20", "name": "Student4", "email": "student4@gmail.com"},
            {"Studentid": "4e071e5a-a0cb-410d-b7a9-6a0e3409915c", "name": "Student3", "email": "user3@example.com"}
        ]
        expected_response = self.mock_supabase_response(mock_table, mock_data)

        response = self.make_get_request("/students")
        self.assert_response(response, expected_response)

   

    @patch('main.supabase.table')
    def test_get_student(self, mock_table):
        test_uuid = "067207b7-eb56-4e06-978f-d6a419e6ca20"
        
        # Mock response from supabase
        mock_data = [
            {
                "Studentid": test_uuid,
                "name": "Student4",
                "email": "student4@gmail.com",
                "class": "58c3c152-4da2-40b7-9463-aeb908dc34cc"
            }
        ]
        
        # Simulate Supabase table select().eq().execute() method
        mock_table.return_value.select.return_value.eq.return_value.execute.return_value = {
            "data": mock_data,
            "count": None
        }
        
        # Expected response to compare against
        expected_response = {
            "data": mock_data,
            "count": None
        }
        
        # Make the request to your FastAPI endpoint
        response = self.make_get_request(f"/student/{test_uuid}")
        
        # Assert that the response matches the expected structure
        self.assert_response(response, expected_response)


    @patch('main.supabase.table')
    def test_get_classes(self, mock_table):
        mock_data = [
            {"class": "58c3c152-4da2-40b7-9463-aeb908dc34cc"},
            {"class": "25b45eb9-8c01-4872-a560-ada7d8406a02"}
        ]
        expected_response = self.mock_supabase_response(mock_table, mock_data)

        response = self.make_get_request("/classes")
        self.assert_response(response, expected_response)

    @patch('main.PROMPTS')
    def test_get_prompts(self, mock_prompts):
        mock_prompts_data = {
            '1': {'name': 'Sherlock Holmes'},
            '2': {'name': 'Romeo and Juliet'}
        }
        mock_prompts.values.return_value = mock_prompts_data.values()

        expected_response = {"prompts": ["Sherlock Holmes", "Romeo and Juliet"]}

        response = self.make_get_request("/prompts")
        self.assert_response(response, expected_response)

    @patch('main.supabase.table')
    def test_get_skills(self, mock_table):
        mock_data = [
            {"skillid": "e48659ad-fc3f-4548-85ee-c22c6d5d8e4b", "name": "Skill 1", "importance": "High"}
        ]
        expected_response = self.mock_supabase_response(mock_table, mock_data)

        response = self.make_get_request("/skills")
        self.assert_response(response, expected_response)

# get skills by ID --> not working need to be fixed
    @patch('main.supabase.table')
    def test_get_skill(self, mock_table):
        # Use the skillid from your JSON response example
        test_uuid = "d9c7e6a9-6cfe-4d57-828e-0d6b5afc6f63"
        
        # Mock response to match the new structure
        mock_data = [{"skillid": test_uuid, "name": "SkillA", "importance": "Normal"}]
        
        # Simulate Supabase table select().eq().execute() method
        mock_table.return_value.select.return_value.eq.return_value.execute.return_value = {
            "data": mock_data,
            "count": None
        }
        
        # Expected response to compare against
        expected_response = {
            "data": mock_data,
            "count": None
        }
        
        # Make the request to your FastAPI endpoint
        response = self.make_get_request(f"/skill/{test_uuid}")
        
        # Assert that the response matches the expected structure
        self.assert_response(response, expected_response)

    # Adding the test for /questionskills endpoint
    @patch('main.supabase.table')
    def test_get_questionskills(self, mock_table):
        mock_data = [
            {
                "QuestionID": "5c4c331b-f7cc-4b16-be71-00647ae1e403",
                "SkillID": "d9c7e6a9-6cfe-4d57-828e-0d6b5afc6f63"
            }
        ]
        expected_response = {
            "data": mock_data,
            "count": None
        }
        # Mock the Supabase table response
        mock_table.return_value.select.return_value.execute.return_value = {
            "data": mock_data,
            "count": None
        }
        # Make the GET request to the "/questionskills" endpoint
        response = self.make_get_request("/questionskills")

        # Assert that the response status code is 200
        self.assertEqual(response.status_code, 200)

        # Assert that the response matches the expected JSON structure
        self.assert_response(response, expected_response)

# not working yet
    @patch('main.supabase.table')
    def test_get_questionskills_by_id(self, mock_table):
        test_uuid = uuid.uuid4()
    
        mock_data = [{"skillid": str(test_uuid), "name": "Skill 1", "importance": "High"}]
        expected_response = self.mock_supabase_response(mock_table, mock_data)

        response = self.make_get_request(f"/skill/{test_uuid}")
        self.assert_response(response, expected_response)

    @patch('main.supabase.table')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data='This is the content of The Dumb Man.')
    def test_get_assessment_file_content(self, mock_open_file, mock_exists, mock_table):
        # The actual assessment ID and file to test
        assessment_id = "a3f97168-a785-496c-8631-cc03af6b4ddc"
        file_name = "The Dumb Man.txt"

        # Mocking Supabase response to return the Assessment with the ReadingFileName
        mock_data = [{"Assessmentid": assessment_id, "ReadingFileName": file_name}]
        mock_table.return_value.select.return_value.eq.return_value.execute.return_value = {
            "data": mock_data
        }

        # Mock the os.path.exists to return True (simulate that the file exists in the correct path)
        mock_exists.return_value = True

        # Make the GET request to the "/assessment/{assessment_id}/file" endpoint
        response = self.make_get_request(f"/assessment/{assessment_id}/file")

        # Assert the response is 200 and contains the correct file content
        expected_response = {"file_content": "This is the content of The Dumb Man."}
        self.assert_response(response, expected_response)

        # Check if the file path was correctly used (ensure it's under "backend/uploads")
        mock_open_file.assert_called_with(os.path.join("backend", "uploads", file_name), "r", encoding="utf-8")

if __name__ == '__main__':
    unittest.main()



