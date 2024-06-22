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
    
    print(f"Extracted metadata: {relevant_metadata}")
    return text, relevant_metadata

def get_citation(text, filename, metadata):
    cr = Crossref()

    # Step 1: Extract citation data from PDF text
    prompt = f"""
    Extract the following information from the provided text:
    1. Title of the work
    2. Author(s) name(s)
    3. Publication year
    4. Publisher
    5. Any other relevant bibliographic information

    Text from first page: {text}

    Provide the extracted information in a JSON format.
    """
    
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an expert at extracting bibliographic information from academic texts."},
            {"role": "user", "content": prompt}
        ]
    )

    try:
        pdf_data = json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        print("Failed to parse JSON from AI response. Using fallback method.")
        # Fallback: use a simple dictionary with metadata
        pdf_data = {
            'title': metadata.get('title', '').strip('[]'),
            'author': metadata.get('author', ''),
            'year': '',
            'publisher': ''
        }

    # Step 2: Compare and supplement with metadata
    metadata_title = metadata.get('title', '').strip('[]')
    metadata_author = metadata.get('author', '')
    
    if not pdf_data.get('title') and metadata_title:
        pdf_data['title'] = metadata_title
    if not pdf_data.get('author') and metadata_author:
        pdf_data['author'] = metadata_author

    # Check for disagreements
    use_crossref = False
    if pdf_data.get('title') != metadata_title and metadata_title:
        pdf_data['notes'] = f"Title disagreement. PDF: {pdf_data.get('title')}, Metadata: {metadata_title}"
        use_crossref = True
    if pdf_data.get('author') != metadata_author and metadata_author:
        pdf_data['notes'] = pdf_data.get('notes', '') + f"\nAuthor disagreement. PDF: {pdf_data.get('author')}, Metadata: {metadata_author}"
        use_crossref = True

    # Step 3: Use Crossref if data is missing or there are disagreements
    if use_crossref or not all([pdf_data.get('title'), pdf_data.get('author'), pdf_data.get('year'), pdf_data.get('publisher')]):
        search_query = f"{pdf_data.get('title', '')} {pdf_data.get('author', '')}"
        try:
            results = cr.works(query=search_query, limit=1)
            if results['message']['total-results'] > 0:
                item = results['message']['items'][0]
                
                crossref_data = {
                    'title': item.get('title', [pdf_data.get('title', '')])[0],
                    'author': ', '.join([f"{author.get('given', '')} {author.get('family', '')}" for author in item.get('author', [])]) or pdf_data.get('author', ''),
                    'year': item.get('published-print', {}).get('date-parts', [['']])[0][0] or item.get('published-online', {}).get('date-parts', [['']])[0][0] or pdf_data.get('year', ''),
                    'publisher': item.get('publisher', '') or pdf_data.get('publisher', ''),
                    'journal': item.get('container-title', [''])[0],
                    'volume': item.get('volume', ''),
                    'issue': item.get('issue', ''),
                    'page': item.get('page', '')
                }
                
                pdf_data.update(crossref_data)
                pdf_data['notes'] = pdf_data.get('notes', '') + "\nCitation information supplemented using CrossRef."
            else:
                pdf_data['notes'] = pdf_data.get('notes', '') + "\nNo matching results found in CrossRef. Citation may be incomplete."
        except Exception as e:
            pdf_data['notes'] = pdf_data.get('notes', '') + f"\nAttempt to verify citation with CrossRef failed: {str(e)}"

    # Generate Chicago style citation
    citation_prompt = f"""
    Generate a complete Chicago style citation for the following work:
    Title: {pdf_data.get('title', '')}
    Author(s): {pdf_data.get('author', '')}
    Year: {pdf_data.get('year', '')}
    Publisher: {pdf_data.get('publisher', '')}
    Journal: {pdf_data.get('journal', '')}
    Volume: {pdf_data.get('volume', '')}
    Issue: {pdf_data.get('issue', '')}
    Page: {pdf_data.get('page', '')}

    Provide only the citation, no additional text.
    """

    citation_response = openai.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are an expert bibliographer. Generate a complete and accurate Chicago style citation based on the provided information."},
            {"role": "user", "content": citation_prompt}
        ]
    )
    
    pdf_data['citation'] = citation_response.choices[0].message.content.strip()

    return json.dumps(pdf_data)

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
    
    # Create a new metadata dictionary
    metadata = {
        "title": title,
        "author": author,
        "subject": subject,
        "keywords": keywords
    }

    # Removing any None values to avoid invalid keys in the metadata
    metadata = {k: v for k, v in metadata.items() if v}

    try:
        # Set the new metadata, overwriting any existing metadata
        document.set_metadata(metadata)
        
        # Get the base name of the file
        base_name = os.path.basename(pdf_path)
        
        # Create a temporary directory
        temp_dir = tempfile.mkdtemp()
        
        # Save the modified PDF file to the temporary directory
        new_pdf_path = os.path.join(temp_dir, f"{base_name}_with_metadata.pdf")
        document.save(new_pdf_path, garbage=4, deflate=True, clean=True)
        document.close()
        
        # Move the modified PDF file to the original directory
        shutil.move(new_pdf_path, pdf_path)
    except Exception as e:
        print(f"Error setting metadata for {pdf_path}: {str(e)}")
        document.close()

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
            text, metadata = extract_text_from_pdf(filepath, max_pages)
            citation_json = get_citation(text, filename, metadata)
            
            try:
                citation_metadata = json.loads(citation_json)
            except json.JSONDecodeError:
                print(f"Failed to parse citation JSON for {filename}. Using fallback method.")
                citation_metadata = {
                    'citation': f"{metadata.get('author', 'Unknown Author')}. {metadata.get('title', 'Unknown Title')}.",
                    'title': metadata.get('title', 'Unknown Title'),
                    'author': metadata.get('author', 'Unknown Author')
                }

            title = citation_metadata.get("title", "")
            author = citation_metadata.get("author", "")
            subject = citation_metadata.get("subject", "")
            keywords = citation_metadata.get("keywords", "")
            citation = citation_metadata.get("citation", "")

            citation_str = citation[:225].replace("/", "-")

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
    max_pages = 1
    max_filename_length = 225

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