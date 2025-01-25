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
    """
    Extract text and metadata from a PDF file.
    
    Args:
        pdf_path (str): Path to the PDF file
        max_pages (int): Maximum number of pages to process
        
    Returns:
        tuple: (extracted_text, metadata_dict)
        
    Raises:
        ValueError: If max_pages is invalid or file is not accessible
        RuntimeError: If PDF processing fails
    """
    if not os.path.exists(pdf_path):
        raise ValueError(f"PDF file not found: {pdf_path}")
        
    if not isinstance(max_pages, int) or max_pages < 1:
        raise ValueError("max_pages must be a positive integer")
    
    text = ""
    relevant_metadata = {}
    
    try:
        document = fitz.open(pdf_path)
    except Exception as e:
        raise RuntimeError(f"Failed to open PDF: {str(e)}")
        
    try:
        # Extract and filter relevant metadata
        full_metadata = document.metadata
        relevant_fields = ['title', 'author', 'subject', 'keywords', 'producer', 'creator']
        
        for field in relevant_fields:
            if field in full_metadata and full_metadata[field]:
                # Clean the metadata value
                value = full_metadata[field].strip()
                if value:  # Only add non-empty values
                    relevant_metadata[field] = value
        
        # Extract text from pages
        num_pages = min(len(document), max_pages)
        for page_num in range(num_pages):
            try:
                page = document.load_page(page_num)
                page_text = page.get_text()
                if page_text:  # Only add non-empty pages
                    text += page_text + "\n"
            except Exception as e:
                print(f"Warning: Failed to extract text from page {page_num}: {str(e)}")
                continue
                
    except Exception as e:
        raise RuntimeError(f"Failed to process PDF: {str(e)}")
        
    finally:
        try:
            document.close()
        except:
            pass  # Ignore errors during closing
            
    return text.strip(), relevant_metadata

def get_citation(text, filename, metadata):
    """
    Extract citation information from PDF text using OpenAI API and Crossref.
    
    Args:
        text (str): Extracted text from PDF
        filename (str): Original filename
        metadata (dict): PDF metadata
        
    Returns:
        dict: Dictionary containing citation information
    """
    cr = Crossref()

    # Step 1: Extract citation data using OpenAI
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

    Text from first page: {text[:1500]}
    """
    
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at extracting bibliographic information. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ]
        )
        
        # Parse the OpenAI response once
        pdf_data = json.loads(response.choices[0].message.content)
        
    except (openai.error.OpenAIError, json.JSONDecodeError) as e:
        print(f"OpenAI API or JSON parsing error: {str(e)}")
        pdf_data = {
            'title': metadata.get('title', '').strip('[]'),
            'author': metadata.get('author', ''),
            'year': '',
            'publisher': '',
            'journal': ''
        }

    # Clean and validate metadata
    metadata_title = metadata.get('title', '').strip('[]').strip()
    metadata_author = metadata.get('author', '').strip()
    
    if not pdf_data.get('title') and metadata_title:
        pdf_data['title'] = metadata_title
    if not pdf_data.get('author') and metadata_author:
        pdf_data['author'] = metadata_author

    # Use Crossref as fallback
    if not all([pdf_data.get('title'), pdf_data.get('author'), pdf_data.get('year')]):
        try:
            search_query = f"{pdf_data.get('title', '')} {pdf_data.get('author', '')}"
            results = cr.works(query=search_query, limit=1)
            
            if results.get('message', {}).get('total-results', 0) > 0:
                item = results['message']['items'][0]
                crossref_data = {
                    'title': item.get('title', [pdf_data.get('title', '')])[0],
                    'author': ', '.join([f"{author.get('given', '')} {author.get('family', '')}"
                                       for author in item.get('author', [])]) or pdf_data.get('author', ''),
                    'year': str(item.get('published-print', {}).get('date-parts', [['']])[0][0] or
                              item.get('published-online', {}).get('date-parts', [['']])[0][0] or
                              pdf_data.get('year', '')),
                    'publisher': item.get('publisher', '') or pdf_data.get('publisher', ''),
                    'journal': item.get('container-title', [''])[0]
                }
                # Update only if we have better data
                pdf_data.update({k: v for k, v in crossref_data.items() if v})
                
        except Exception as e:
            print(f"Crossref API error: {str(e)}")

    # Ensure all values are strings
    return {k: str(v) if v is not None else '' for k, v in pdf_data.items()}

def build_filename(author, year, title, journal=None, max_length=225):
    """
    Constructs a filename using author, year, and title.
    
    Args:
        author (str): Author name(s)
        year (str): Publication year
        title (str): Publication title
        journal (str, optional): Journal name (unused, kept for backward compatibility)
        max_length (int, optional): Maximum filename length minus extension. Defaults to 225.
    
    Returns:
        str: Constructed filename with .pdf extension
    """
    components = []
    
    # Process author
    if author:
        # Handle et al. cases
        author_parts = author.split(",")
        first_author = author_parts[0].strip()
        author_part = first_author + (" et al" if len(author_parts) > 1 else "")
        components.append(author_part)
    
    # Process year
    if year:
        # Clean and validate year
        year_clean = ''.join(filter(str.isdigit, str(year)))[:4]
        if year_clean:
            components.append(year_clean)
    
    # Process title
    if title:
        # Clean title: remove extra spaces and periods
        title_clean = ' '.join(title.strip().split())
        components.append(title_clean)
    
    # Join components with periods
    base_name = ".".join(components)
    
    # Truncate at word boundary
    if len(base_name) > (max_length - 4):  # -4 for .pdf
        truncated = base_name[:max_length - 4].rsplit(' ', 1)[0].strip()
    else:
        truncated = base_name
    
    final_name = truncated + ".pdf"
    print(f"Debug - build_filename output: {final_name}")
    return final_name

def sanitize_filename(filename):
    """
    Sanitize filename for cross-platform compatibility.
    
    Args:
        filename (str): Original filename
        
    Returns:
        str: Sanitized filename with .pdf extension
    """
    # Remove any existing file extension
    base = os.path.splitext(filename)[0]
    
    # Define invalid characters including Windows reserved characters
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4',
        'LPT1', 'LPT2', 'LPT3', 'LPT4'
    }
    
    # Replace invalid characters
    sanitized = re.sub(invalid_chars, '', base)
    
    # Replace colons with dashes (no space after)
    sanitized = re.sub(r'\s*:\s*', '-', sanitized)
    
    # Replace other separators with hyphens
    sanitized = re.sub(r'[\t\n\r\v\f]', '-', sanitized)
    
    # Remove multiple hyphens and ensure no spaces around them
    sanitized = re.sub(r'\s*-\s*', '-', sanitized)
    sanitized = re.sub(r'-+', '-', sanitized)
    
    # Remove leading/trailing periods and spaces
    sanitized = sanitized.strip('. ')
    
    # Check for Windows reserved names
    if sanitized.upper() in reserved_names:
        sanitized = f"_{sanitized}"
    
    # Ensure we have a valid filename
    if not sanitized:
        sanitized = "unnamed_document"
    
    # Always add .pdf extension
    sanitized = sanitized + ".pdf"
    
    print(f"Debug - sanitize_filename output: {sanitized}")
    return sanitized

def add_metadata_to_pdf(pdf_path, title, author, subject, keywords):
    """
    Add or update metadata in a PDF file.
    
    Args:
        pdf_path (str): Path to the PDF file
        title (str): Document title
        author (str): Document author
        subject (str): Document subject
        keywords (str or list): Keywords for the document
    
    Raises:
        ValueError: If pdf_path is invalid or file doesn't exist
        RuntimeError: If metadata update fails
    """
    if not os.path.exists(pdf_path):
        raise ValueError(f"PDF file not found: {pdf_path}")
        
    # Convert keywords to string if necessary
    if isinstance(keywords, list):
        keywords = ', '.join(str(k).strip() for k in keywords if k)
    elif not isinstance(keywords, str):
        keywords = ""

    # Clean and prepare metadata
    metadata = {
        "title": str(title).strip() if title else "",
        "author": str(author).strip() if author else "",
        "subject": str(subject).strip() if subject else "",
        "keywords": str(keywords).strip() if keywords else ""
    }

    # Remove empty fields
    metadata = {k: v for k, v in metadata.items() if v}
    
    # Create temporary directory
    temp_dir = None
    document = None
    
    try:
        # Open PDF
        document = fitz.open(pdf_path)
        
        # Set metadata
        document.set_metadata(metadata)
        
        # Create temp directory for safe saving
        temp_dir = tempfile.mkdtemp()
        temp_pdf = os.path.join(temp_dir, os.path.basename(pdf_path))
        
        # Save with optimization
        document.save(
            temp_pdf,
            garbage=4,  # Maximum garbage collection
            deflate=True,  # Compress streams
            clean=True,  # Clean unused elements
            pretty=False  # No pretty printing (smaller file)
        )
        
        # Close before moving
        document.close()
        document = None
        
        # Safely replace original file
        shutil.move(temp_pdf, pdf_path)
        
    except fitz.FileDataError as e:
        raise RuntimeError(f"Invalid or corrupted PDF file: {str(e)}")
    except fitz.FileNotFoundError as e:
        raise RuntimeError(f"PDF file not accessible: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Failed to update PDF metadata: {str(e)}")
        
    finally:
        # Clean up resources
        if document:
            try:
                document.close()
            except:
                pass
                
        # Remove temp directory if it exists
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except:
                pass  # Best effort cleanup

def process_pdf_files(directory):
    """
    Process all PDF files in a directory, extracting citations and renaming files.
    
    Args:
        directory (str): Path to directory containing PDF files
    
    Returns:
        dict: Summary of processing results
        {
            'total': number of files processed,
            'successful': number of successful processes,
            'failed': number of failures,
            'errors': list of error messages
        }
    """
    results = {
        'total': 0,
        'successful': 0,
        'failed': 0,
        'errors': []
    }

    print(f"Starting to process directory: {directory}")
    
    # Validate directory
    if not os.path.exists(directory):
        error_msg = f"Directory not found: {directory}"
        results['errors'].append(error_msg)
        print(f"Error: {error_msg}")
        return results
        
    if not os.path.isdir(directory):
        error_msg = f"Path is not a directory: {directory}"
        results['errors'].append(error_msg)
        print(f"Error: {error_msg}")
        return results

    # Get list of PDF files
    try:
        pdf_files = [f for f in os.listdir(directory) if f.lower().endswith(".pdf")]
    except PermissionError:
        error_msg = f"Permission denied accessing directory: {directory}"
        results['errors'].append(error_msg)
        print(f"Error: {error_msg}")
        return results
    except Exception as e:
        error_msg = f"Error accessing directory: {str(e)}"
        results['errors'].append(error_msg)
        print(f"Error: {error_msg}")
        return results

    print(f"Found {len(pdf_files)} PDF files")
    results['total'] = len(pdf_files)

    # Process each PDF
    for filename in pdf_files:
        print(f"\nProcessing file: {filename}")
        filepath = os.path.join(directory, filename)
        
        try:
            # Check file access
            if not os.access(filepath, os.R_OK | os.W_OK):
                raise PermissionError(f"Insufficient permissions for file: {filename}")

            # Extract text and metadata
            text, metadata = extract_text_from_pdf(filepath, max_pages=1)
            if not text and not metadata:
                print("Warning: No text or metadata extracted")

            # Get citation information
            citation_metadata = get_citation(text, filename, metadata)
            print(f"Extracted metadata: {citation_metadata}")

            # Build new filename
            new_filename = build_filename(
                author=citation_metadata.get("author", "Unknown Author"),
                year=str(citation_metadata.get("year", "")),
                title=citation_metadata.get("title", "Unknown Title")
            )
            print(f"Built new filename: {new_filename}")

            # Sanitize filename
            sanitized_filename = sanitize_filename(new_filename)
            print(f"Sanitized filename: {sanitized_filename}")
            
            new_filepath = os.path.join(directory, sanitized_filename)

            # Rename file if needed
            if filepath.lower() != new_filepath.lower():
                # Check if target file already exists
                if os.path.exists(new_filepath):
                    base, ext = os.path.splitext(new_filepath)
                    counter = 1
                    while os.path.exists(f"{base}_{counter}{ext}"):
                        counter += 1
                    new_filepath = f"{base}_{counter}{ext}"
                    print(f"File already exists, using: {os.path.basename(new_filepath)}")

                os.rename(filepath, new_filepath)
                print("File renamed successfully")
                filepath = new_filepath  # Update filepath for metadata step

            # Add metadata to PDF
            add_metadata_to_pdf(
                filepath,
                title=citation_metadata.get("title", ""),
                author=citation_metadata.get("author", ""),
                subject=f"Journal: {citation_metadata.get('journal', '')} | Publisher: {citation_metadata.get('publisher', '')}",
                keywords=citation_metadata.get("other_info", "")
            )
            print("Metadata added successfully")
            
            results['successful'] += 1

        except PermissionError as e:
            error_msg = f"Permission error processing {filename}: {str(e)}"
            results['errors'].append(error_msg)
            print(f"Error: {error_msg}")
            results['failed'] += 1
            continue
            
        except Exception as e:
            error_msg = f"Error processing {filename}: {str(e)}"
            results['errors'].append(error_msg)
            print(f"Error: {error_msg}")
            results['failed'] += 1
            continue

    # Print summary
    print("\nProcessing Summary:")
    print(f"Total files processed: {results['total']}")
    print(f"Successful: {results['successful']}")
    print(f"Failed: {results['failed']}")
    if results['errors']:
        print("\nErrors encountered:")
        for error in results['errors']:
            print(f"- {error}")

    return results

if __name__ == "__main__":
    try:
        directory = pyperclip.paste().strip()
        if directory:
            process_pdf_files(directory)
        else:
            print("No directory path found in clipboard")
    except Exception as e:
        print(f"Error: {str(e)}")