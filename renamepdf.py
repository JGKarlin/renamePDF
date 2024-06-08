#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 3 11:08:56 2024
Updated on Fri Jun 9 11:08:56 2024 by Jason G. Karlin

This script renames PDF files to their citation based on Chicago bibliography style and adds the citation to the PDF metadata.
"""
import os
import re
import openai
import fitz  # PyMuPDF
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
openai.api_key = os.environ['OPENAI_API_KEY']

def extract_text_from_pdf(pdf_path, max_pages):
    text = ""
    document = fitz.open(pdf_path)
    num_pages = min(len(document), max_pages)
    for page_num in range(num_pages):
        page = document.load_page(page_num)
        text += page.get_text()
    return text

def get_citation(text, filename):
    prompt = f"""
    Generate a JSON object for the provided text that includes the following fields: 'description', 'author', 'title', 'subject', and 'keywords'. 
    
    - 'description': The full citation of the text; not a description of the text; omit webpage urls and DOI.
    - 'author': The author(s) of the text.
    - 'title': The title of the text.
    - 'subject': A one-sentence summary based on the text.
    - 'keywords': A list of keywords, if available in the text.
    
    The original filename is '{filename}'.
    
    Text: {text}
    """
    
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that generates citations in JSON format. Ensure the citation is complete and accurate."},
            {"role": "user", "content": prompt}
        ]
    )
    
    citation_json = response.choices[0].message.content.strip()

    # Remove unwanted backticks and any other formatting issues
    citation_json = citation_json.lstrip("```json").rstrip("```")

    if not citation_json.startswith('{'):
        print(f"Invalid JSON response for {filename}: {citation_json}")
        return None

    return citation_json

def sanitize_filename(filename):
    sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
    sanitized = sanitized.replace('..pdf', '.pdf').replace('*.pdf', '.pdf').replace(': ', '-').replace(':', '-')
    sanitized = sanitized.replace(u'\u201c', '"').replace(u'\u201d', '"').replace(u'\u2018', "'").replace(u'\u2019', "'")
    return sanitized

def add_metadata_to_pdf(pdf_path, title, author, subject, keywords):
    document = fitz.open(pdf_path)
    
    # Ensure keywords are in the correct format
    if isinstance(keywords, list):
        keywords = ', '.join(keywords)
    elif not isinstance(keywords, str):
        keywords = ""

    # Ensure each metadata field is a string and handle any unexpected types
    title = str(title) if title else ""
    author = str(author) if author else ""
    subject = str(subject) if subject else ""
    keywords = str(keywords) if keywords else ""

    # Debug print statements
    print(f"Title: {title}")
    print(f"Author: {author}")
    print(f"Subject: {subject}")
    print(f"Keywords: {keywords}")
    
    # Add metadata to the document
    document.set_metadata({
        "title": title,
        "author": author,
        "subject": subject,
        "keywords": keywords
    })
    
    new_pdf_path = pdf_path.replace(".pdf", "_with_metadata.pdf")
    document.save(new_pdf_path)
    document.close()
    os.replace(new_pdf_path, pdf_path)

def process_pdf_files(directory, max_pages, max_filename_length, option):
    while True:
        if not os.path.isdir(directory):
            print(f"\nError: The directory '{directory}' does not exist.")
            directory = input("\nPlease enter a valid directory path containing the PDF files: ")
            continue

        pdf_files = [f for f in os.listdir(directory) if f.endswith(".pdf")]
        num_files = len(pdf_files)
        print(f"\nFound {num_files} PDF files in the directory.")
        confirm = input("\nDo you want to proceed with processing the files? (y/n): ")
        if confirm.lower() != 'y':
            print("\nProcessing canceled.")
            return

        for filename in pdf_files:
            filepath = os.path.join(directory, filename)
            text = extract_text_from_pdf(filepath, max_pages)
            citation_json = get_citation(text, filename)
            
            if not citation_json:
                print(f"\nFailed to get a valid JSON response for {filename}. The response was empty or invalid.")
                continue
            
            try:
                citation_metadata = json.loads(citation_json)
            except json.JSONDecodeError as e:
                print(f"\nFailed to decode JSON for {filename}: {e}")
                print(f"Response was: {citation_json}")
                continue

            title = citation_metadata.get("title", "")
            author = citation_metadata.get("author", "")
            subject = citation_metadata.get("subject", "")
            keywords = citation_metadata.get("keywords", "")
            description = citation_metadata.get("description", "")

            citation_str = description[:225].replace("/", "-")

            if option in ["1", "3"]:
                new_filename = sanitize_filename(f"{citation_str}.pdf")
                new_filepath = os.path.join(directory, new_filename)
                os.rename(filepath, new_filepath)
                filepath = new_filepath
                print(f"\nRenamed: {filename} -> {new_filename}")

            if option in ["2", "3"]:
                add_metadata_to_pdf(filepath, title, author, subject, keywords)
                print(f"\nAdded metadata to: {filename}")
        break

if __name__ == "__main__":
    directory = input("\nEnter the directory path containing the PDF files: ")
    max_pages = 3
    max_filename_length = 250

    print("\nWhat bibliographic information would you like to add:")
    print("1. File name")
    print("2. Metadata")
    print("3. Both")
    print("4. Quit")
    option = input("\nEnter your choice (1, 2, 3, 4): ")

    if option in ["1", "2", "3"]:
        process_pdf_files(directory, max_pages, max_filename_length, option)
    else:
        print("\nExiting.")
