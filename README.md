### re-namePDF.py
# PDF Citation Renamer and Metadata Generator

## Overview

This script renames PDF files based on their citation in Chicago bibliography style and adds the citation to the PDF metadata. It utilizes OpenAI's GPT-4 to generate the citation from the text extracted from the PDF files.

## Features

- Extracts text from the first few pages of PDF files.
- Generates a citation in JSON format using OpenAI's GPT-4.
- Renames PDF files to their citation in Chicago bibliography style.
- Adds bibliographic metadata to PDF files.
- Supports user choice for renaming files, adding metadata, or both.

## Requirements

- Python 3.6+
- `openai` library
- `PyMuPDF` (also known as `fitz`)
- `dotenv` library

## Installation

1. **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/pdf-citation-renamer.git
    cd pdf-citation-renamer
    ```

2. **Create a virtual environment and activate it:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. **Install the required packages:**
    ```bash
    pip install -r requirements.txt
    ```

4. **Set up your OpenAI API key:**

    Create a `.env` file in the root directory of the project and add your OpenAI API key:
    ```plaintext
    OPENAI_API_KEY=your_openai_api_key_here
    ```

## Usage

1. **Run the script:**
    ```bash
    python renamepdf2.py
    ```

2. **Follow the prompts:**
    - Enter the directory path containing the PDF files.
    - Choose how to add bibliographic information:
      - `1`: Rename files only
      - `2`: Add metadata only
      - `3`: Both rename files and add metadata
      - `4`: Quit

### Example

```plaintext
Enter the directory path containing the PDF files: /path/to/pdf/files
Found 5 PDF files in the directory.
Do you want to proceed with processing the files? (y/n): y

What bibliographic information would you like to add:
1. File name
2. Metadata
3. Both
4. Quit
Enter your choice (1, 2, 3, 4): 3

