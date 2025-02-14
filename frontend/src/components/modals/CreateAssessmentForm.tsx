// src/components/CreateAssessmentForm.tsx

import { randomUUID } from "crypto";
import { useRouter } from "next/router";
import React, { use, useEffect, useState } from "react";
import Loading from "../Loading";
import Error from "next/error";
import mammoth from "mammoth";
import * as pdfjsLib from "pdfjs-dist/build/pdf";
import "pdfjs-dist/build/pdf.worker.entry";

const CreateAssessmentForm: React.FC = () => {
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [fileContent, setFileContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const router = useRouter();

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setError(null);
      setFile(e.target.files[0]);
    } else {
      setError("Please upload a file");
    }
  };

  useEffect(() => {
    if (file) {
      const fileExtension = file.name.split(".").pop()?.toLowerCase();

      const reader = new FileReader();

      if (fileExtension === "txt") {
        reader.onload = (e) => {
          setFileContent(e.target?.result as string);
        };
        reader.readAsText(file);
      } else if (fileExtension === "docx") {
        reader.onload = async (e) => {
          const arrayBuffer = e.target?.result as ArrayBuffer;
          const { value } = await mammoth.extractRawText({ arrayBuffer });
          setFileContent(value);
        };
        reader.readAsArrayBuffer(file);
      } else if (fileExtension === "pdf") {
        reader.onload = async (e) => {
          const typedArray = new Uint8Array(e.target?.result as ArrayBuffer);
          const pdf = await pdfjsLib.getDocument({ data: typedArray }).promise;

          let text = "";
          for (let i = 0; i < pdf.numPages; i++) {
            const page = await pdf.getPage(i + 1);
            const textContent = await page.getTextContent();

            const pageText = textContent.items
              .map((item: { str: string }) => item.str)
              .join(" ");
            text += pageText + "\n";
          }
          setFileContent(text);
        };
        reader.readAsArrayBuffer(file);
      } else {
        setError(
          "Unsupported file type. Please upload a .txt, .docx, or .pdf file."
        );
      }
    }
  }, [file]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // Handle form submission logic
    if (file) {
      setError(null);
      console.log({ title, topic, dueDate, file });
      const new_assessment = JSON.stringify({
        title: title,
        topic: topic,
        class_id: "5cbb6db4-8601-4b16-a834-a5085437c707",
        due_date: dueDate as string,
        reading_file_name: file?.name,
      });

      await fetch("/api/postassessment", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: new_assessment,
      });

      await fetch("/api/upload", {
        method: "POST",
        body: file?.name + "\n" + fileContent,
      });

      router.reload(); //reloads to display added assessment
    } else {
      setError("Please upload a file");
    }
  };

  return (
    <>
      {loading ? (
        <Loading />
      ) : (
        <form onSubmit={handleSubmit} className="text-black">
          <div className="mb-4">
            <label className="block mb-2">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded"
              required
            />
          </div>
          <div className="mb-4">
            <label className="block mb-2">Topic</label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded"
              required
            />
          </div>
          <div className="mb-4">
            <label className="block mb-2">Due Date</label>
            <input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded"
              required
            />
          </div>

          <div className="mb-4">
            <label className="block mb-2">Reading Material</label>
            <div className="border border-gray-300 rounded p-4 text-center">
              <div className="flex flex-col space-y-4   ...">
                {file ? (
                  <p>{file.name}</p>
                ) : (
                  <div>
                    <b>Upload file here</b>
                  </div>
                )}
                <div className="place-content-center">
                  <label
                    htmlFor="file-upload"
                    className="bg-primary text-white  w-48 mt-10 px-4 py-2 rounded cursor-pointer hover:bg-primary-dark"
                  >
                    Upload File
                  </label>
                  <input
                    id="file-upload"
                    type="file"
                    onChange={handleFileChange}
                    className="hidden "
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="flex justify-between">
            <p className="text-red-500">{error}</p>
            <button
              type="submit"
              className={
                `px-4 py-2 rounded ` +
                (error
                  ? "bg-gray-200 text-gray-400 cursor-not-allowed"
                  : "bg-secondary text-black hover:bg-secondary-dark")
              }
              disabled={Boolean(error)}
            >
              Create
            </button>
          </div>
        </form>
      )}
    </>
  );
};

export default CreateAssessmentForm;