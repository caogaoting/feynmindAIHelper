# Feynmind AI Helper (Open Source Version)

This is an open-source Feynmind AI Helper.

## Setup

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Set up your environment variables:**

    Create a `.env` file in the root directory and add your OpenAI API key:
    ```
    OPENAI_API_KEY="your-api-key"
    OPENAI_BASE_URL="your-base-url" # Optional
    ```

3.  **Initialize the database:**
    ```bash
    python init_db.py
    ```

4.  **Run the application:**
    ```bash
    python app/main.py
    ```
