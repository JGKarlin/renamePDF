# renamePDF

An automated PDF citation and metadata management tool that intelligently renames academic PDF files and enriches their metadata using machine learning and academic databases.

## Overview

renamePDF automatically processes PDF files by extracting content, generating standardized citations using OpenAI's GPT-4o-mini, cross-referencing with Crossref, and updating both filenames and metadata accordingly. It uses Chicago bibliography style for citations and ensures cross-platform filename compatibility.

## Features

- Smart text extraction from PDF files with configurable page limits
- Multi-source citation generation combining:
  - OpenAI GPT-4o-mini for content analysis
  - Crossref API for academic verification
  - PDF metadata extraction
- Cross-platform compatible filename generation
- Comprehensive metadata enrichment
- Automated batch processing of multiple PDFs
- Built-in error handling and recovery
- Progress tracking with detailed processing summaries

## Requirements

- Python 3.6+
- OpenAI API key
- Required Python packages:
  - openai: For GPT-4o-mini integration
  - PyMuPDF (fitz): For PDF processing
  - habanero: For Crossref API access
  - python-dotenv: For environment management
  - pyperclip: For clipboard operations

## Installation

1. **Clone the repository:**
```bash
git clone https://github.com/jgkarlin/renamePDF.git
cd renamePDF
```

2. **Set up Python environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Configure API key:**
Create a `.env` file in the project root:
```plaintext
OPENAI_API_KEY=your_openai_api_key_here
```

## Usage

Important: The script reads the target directory path from your clipboard.

1. **Copy the target directory path** to your clipboard using Cmd+C (MacOS) or Ctrl+C (Windows)
2. **Run the script:**
```bash
python renamepdf.py
```

The script will:
- Process all PDF files in the specified directory
- Generate standardized filenames based on citations
- Update PDF metadata with bibliographic information
- Provide a detailed processing summary

### Generated Filenames

Files are renamed using the format:
```
AuthorLastName[et al].YYYY.Title.pdf
```

For example:
```
Smith et al.2023.Machine Learning Applications in Historical Research.pdf
```

### Metadata Fields

The script updates the following PDF metadata:
- Title: Full paper title
- Author: Complete author list
- Subject: Journal and publisher information
- Keywords: Additional bibliographic data

## Error Handling

The script includes comprehensive error handling for:
- Invalid file paths
- Corrupted PDF files
- API failures
- Permission issues
- Duplicate filenames

Failed operations are logged with detailed error messages in the processing summary.

## MacOS Automator Integration

You can set up the script as a Quick Action service in MacOS:

1. Open Automator and create a new "Quick Action" workflow
2. Set workflow to receive "folders" in "Finder.app"
3. Add "Run Shell Script" action
4. Configure the shell script:
```bash
# Use your Python interpreter path
PYTHON_PATH="/usr/local/bin/python3"  # Default system Python
# Alternative: PYTHON_PATH="$(which python3)"  # Active Python in PATH

# Path to the script (adjust to your installation directory)
SCRIPT_PATH="path/to/renamepdf.py"

$PYTHON_PATH $SCRIPT_PATH
```

The workflow will appear in Finder's right-click menu. When invoked, it automatically copies the selected folder's path to clipboard and runs the script.
