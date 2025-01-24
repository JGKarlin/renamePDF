#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun 3 11:08:56 2024
Updated on Fri Jun 9 11:08:56 2024 by Jason G. Karlin

This script renames PDF files to their citation based on Chicago bibliography style and adds the citation to the PDF metadata.
"""
import os
import re
import tempfile
import shutil
import openai
import fitz  # PyMuPDF
import json
from dotenv import load_dotenv
from habanero import Crossref
import pyperclip

# Load environment variables from .env file
load_dotenv()
openai.api_key = os.environ['OPENAI_API_KEY']

def extract_text_from_pdf(pdf_path, max_pages):
    text = ""
    relevant_metadata = {}
    document = fitz.open(pdf_path)
    
    # Extract and filter relevant metadata
    full_metadata = document.metadata
    relevant_fields = ['title', 'author']
    
    for field in relevant_fields:
        if field in full_metadata and full_metadata[field]:
            relevant_metadata[field] = full_metadata[field]
    
    # Extract text from pages
    num_pages = min(len(document), max_pages)
    for page_num in range(num_pages):
        page = document.load_page(page_num)
        text += page.get_text()
    
    document.close()
    
    return text, relevant_metadata

def get_citation(text, filename, metadata):
    cr = Crossref()

    # Step 1: Extract citation data from PDF text
    prompt = f"""
    Extract bibliographic information from the provided text and return it in valid JSON format.
    Use exactly this JSON structure:
    {{
        "title": "extracted title",
        "author": "extracted author names",
        "year": "publication year",
        "publisher": "publisher name",
        "journal": "journal title",
        "other_info": "any other relevant information"
    }}

    Text from first page: {text}
    """
    
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert at extracting bibliographic information. Always respond with valid JSON."},
            {"role": "user", "content": prompt}
        ]
    )

    try:
        response_content = response.choices[0].message.content
        pdf_data = json.loads(response_content)
    except json.JSONDecodeError:
        pdf_data = {
            'title': metadata.get('title', '').strip('[]'),
            'author': metadata.get('author', ''),
            'year': '',
            'publisher': '',
            'journal': ''
        }

    # Supplement missing metadata
    metadata_title = metadata.get('title', '').strip('[]')
    metadata_author = metadata.get('author', '')
    
    if not pdf_data.get('title') and metadata_title:
        pdf_data['title'] = metadata_title
    if not pdf_data.get('author') and metadata_author:
        pdf_data['author'] = metadata_author

    # Use Crossref if data is incomplete
    if not all([pdf_data.get('title'), pdf_data.get('author'), pdf_data.get('year'), pdf_data.get('publisher')]):
        search_query = f"{pdf_data.get('title', '')} {pdf_data.get('author', '')}"
        try:
            results = cr.works(query=search_query, limit=1)
            if results['message']['total-results'] > 0:
                item = results['message']['items'][0]
                crossref_data = {
                    'title': item.get('title', [pdf_data.get('title', '')])[0],
                    'author': ', '.join([f"{author.get('given', '')} {author.get('family', '')}" for author in item.get('author', [])]) or pdf_data.get('author', ''),
                    'year': item.get('published-print', {}).get('date-parts', [[""]])[0][0] or item.get('published-online', {}).get('date-parts', [[""]])[0][0] or pdf_data.get('year', ''),
                    'publisher': item.get('publisher', '') or pdf_data.get('publisher', ''),
                    'journal': item.get('container-title', [''])[0],
                    'volume': item.get('volume', ''),
                    'issue': item.get('issue', ''),
                    'page': item.get('page', '')
                }
                pdf_data.update(crossref_data)
        except Exception:
            pass

    return json.dumps(pdf_data)

def build_filename(author, year, title, journal=None, max_length=225):
    """Constructs a filename using author, year, and title, separated by periods."""
    components = []
    if author:
        # Remove any trailing period if "et al." is used
        author_part = author.split(",")[0].strip() + (" et al" if "," in author else "")
        components.append(author_part)
    if year:
        components.append(year)
    if title:
        components.append(title.strip())

    base_name = ".".join(components)
    truncated = base_name[:max_length - 4].strip()
    final_name = truncated + ".pdf"
    print(f"Debug - build_filename output: {final_name}")
    return final_name

def sanitize_filename(filename):
    # Remove any existing file extension to clean the base name
    base = os.path.splitext(filename)[0]
    
    # Sanitize the filename
    sanitized = re.sub(r'[<>:"/\\|?*]', '', base)
    sanitized = sanitized.replace(': ', '-').replace(':', '-')
    
    # Always add .pdf extension
    sanitized = sanitized + ".pdf"
    print(f"Debug - sanitize_filename output: {sanitized}")  # Debug print
    return sanitized

def add_metadata_to_pdf(pdf_path, title, author, subject, keywords):
    document = fitz.open(pdf_path)

    if isinstance(keywords, list):
        keywords = ', '.join(keywords)
    elif not isinstance(keywords, str):
        keywords = ""

    metadata = {
        "title": str(title) if title else "",
        "author": str(author) if author else "",
        "subject": str(subject) if subject else "",
        "keywords": str(keywords) if keywords else ""
    }

    metadata = {k: v for k, v in metadata.items() if v}

    try:
        document.set_metadata(metadata)
        temp_dir = tempfile.mkdtemp()
        new_pdf_path = os.path.join(temp_dir, os.path.basename(pdf_path))
        document.save(new_pdf_path, garbage=4, deflate=True, clean=True)
        document.close()
        shutil.move(new_pdf_path, pdf_path)
    except Exception:
        document.close()

def process_pdf_files(directory):
    print(f"Starting to process directory: {directory}")
    
    if not os.path.isdir(directory):
        print(f"Error: {directory} is not a valid directory")
        return

    pdf_files = [f for f in os.listdir(directory) if f.endswith(".pdf")]
    print(f"Found PDF files: {pdf_files}")

    for filename in pdf_files:
        print(f"\nProcessing file: {filename}")
        filepath = os.path.join(directory, filename)
        text, metadata = extract_text_from_pdf(filepath, max_pages=1)
        citation_json = get_citation(text, filename, metadata)
        
        try:
            citation_metadata = json.loads(citation_json)
            print(f"Extracted metadata: {citation_metadata}")
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            citation_metadata = {
                'title': metadata.get('title', 'Unknown Title'),
                'author': metadata.get('author', 'Unknown Author'),
                'year': metadata.get('year', ''),
                'journal': metadata.get('journal', '')
            }

        print("About to build filename...")  # New debug print
        new_filename = build_filename(
            author=citation_metadata.get("author", "Unknown Author"),
            year=str(citation_metadata.get("year", "")),  # Convert year to string
            title=citation_metadata.get("title", "Unknown Title")
        )
        print(f"Built new filename: {new_filename}")  # New debug print

        print("About to sanitize filename...")  # New debug print
        sanitized_filename = sanitize_filename(new_filename)
        print(f"Sanitized filename: {sanitized_filename}")  # New debug print
        
        new_filepath = os.path.join(directory, sanitized_filename)
        print(f"Attempting rename from: {filepath}")
        print(f"Attempting rename to: {new_filepath}")
        
        try:
            if filepath != new_filepath:  # Only rename if the name is actually different
                os.rename(filepath, new_filepath)
                print("File renamed successfully")
            else:
                print("Filenames are identical, no rename needed")
        except Exception as e:
            print(f"Error during rename: {str(e)}")

if __name__ == "__main__":
    try:
        directory = pyperclip.paste().strip()
        process_pdf_files(directory)
    except Exception:
        pass
