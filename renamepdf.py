#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun  3 11:08:56 2024
@author: jgkarlin

This script renames PDF files to their citation based on Chicago bibliography style.
"""
import os
import re
import openai
import fitz  # PyMuPDF
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
openai.api_key = os.environ['OPENAI_API_KEY']

def extract_text_from_pdf(pdf_path, max_pages):
    """
    Extracts text from a PDF file.
    
    Args:
        pdf_path (str): Path to the PDF file.
        max_pages (int): Maximum number of pages to extract text from.
    
    Returns:
        str: Extracted text.
    """
    text = ""
    document = fitz.open(pdf_path)
    num_pages = min(len(document), max_pages)
    for page_num in range(num_pages):
        page = document.load_page(page_num)
        text += page.get_text()
    return text

def get_citation(text, filename):
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that generates citations in Chicago bibliography style. Ensure the citation is complete and accurate."},
            {"role": "user", "content": f"Find the citation for the following text in Chicago bibliography style. Use the provided text and search online to ensure the citation is complete and accurate. Return with only the citation. Omit webpage and DOI from the citation. The original filename is '{filename}'.\n\n{text}"}
        ]
    )
    citation = response.choices[0].message.content
    print()
    print(citation)
    return citation

def sanitize_filename(filename):
    # Remove invalid characters and replace spaces with underscores
    sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
    sanitized = sanitized.replace('..pdf', '.pdf')
    sanitized = sanitized.replace('*.pdf', '.pdf')
    sanitized = sanitized.replace(': ', '-')  # Replace colons with dashes
    sanitized = sanitized.replace(':', '-')  # Replace colons with dashes
    return sanitized

def process_pdf_files(directory, max_pages, max_filename_length):
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
        citation = get_citation(text, filename)
        citation = citation[:max_filename_length]  # Truncate to the specified maximum length
        citation = citation.replace("/", "-")  # Replace forward slashes with hyphens
        new_filename = sanitize_filename(f"{citation}.pdf")
        new_filepath = os.path.join(directory, new_filename)
        os.rename(filepath, new_filepath)
        print(f"\nRenamed: {filename} -> {new_filename}")

# Prompt user for the directory
directory = input("\nEnter the directory path containing the PDF files: ")

# Maximum number of pages to extract text from
max_pages = 10

# Maximum length of the generated citation filename
max_filename_length = 200

# Create the directory if it doesn't exist
os.makedirs(directory, exist_ok=True)

process_pdf_files(directory, max_pages, max_filename_length)