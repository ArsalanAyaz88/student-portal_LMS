import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the database URL from environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL or not DATABASE_URL.startswith("sqlite:///"):
    print("Error: DATABASE_URL is not set or is not a SQLite database in the .env file.")
    exit(1)

# The project root is the current working directory
project_root = os.getcwd()

# Extract the relative path from the URL
db_relative_path = DATABASE_URL.split('///')[1]

# Construct the absolute path
db_file_path = os.path.join(project_root, db_relative_path)

# Check if the database file exists
if os.path.exists(db_file_path):
    try:
        # Delete the file
        os.remove(db_file_path)
        print(f"Successfully deleted database file: {db_file_path}")
    except OSError as e:
        print(f"Error deleting file {db_file_path}: {e}")
        exit(1)
else:
    print(f"Database file not found at {db_file_path}. Nothing to delete.")

print("Database has been successfully reset.")
