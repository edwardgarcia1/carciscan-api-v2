import os
from pydantic_settings import BaseSettings

# Construct the absolute path to the project root directory.
# This makes the .env file location independent of where the script is run from.
# __file__ is the path to the current file (config.py)
# We go up three directories: core/ -> app/ -> project_root/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class Settings(BaseSettings):
    """
    Application settings. This class will load variables from the .env file.
    """
    # The database connection URL
    DATABASE_URL: str
    LLM_API_URL: str
    LLM_API_KEY: str
    MODEL_ID: str

    # API settings
    API_V2_STR: str = "/api/v2"
    PROJECT_NAME: str = "Carciscan API"

    class Config:
        # Construct the full, absolute path to the .env file
        env_file = os.path.join(BASE_DIR, ".env")
        env_file_encoding = 'utf-8'

# Create a single settings instance to be used throughout the application
settings = Settings()