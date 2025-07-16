#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "openai",
#     "python-dotenv",
# ]
# ///

import os
import sys
from dotenv import load_dotenv

# Global debug flag - set based on command line arguments
DEBUG_MODE = False


def debug_print(message):
    """Print debug message only if debug mode is enabled."""
    if DEBUG_MODE:
        print(f"DEBUG: {message}", file=sys.stderr)


def prompt_llm(prompt_text):
    """
    Base OpenAI LLM prompting method using fastest model.

    Args:
        prompt_text (str): The prompt to send to the model

    Returns:
        str: The model's response text, or None if error
    """
    load_dotenv()

    api_key = os.getenv("CLAUDE_HOOKS_OPENAI_API_KEY")
    api_base_url = os.getenv("CLAUDE_HOOKS_OPENAI_API_BASE_URL")
    model = os.getenv("CLAUDE_HOOKS_OPENAI_MODEL", "gpt-4.1-nano")  # Default to fastest model
    
    # Debug: Check environment variables
    if not api_key:
        debug_print("Missing API key. Expected env var: CLAUDE_HOOKS_OPENAI_API_KEY")
        return None
    
    debug_print(f"API Key found: {api_key[:10]}...")
    debug_print(f"API Base URL: {api_base_url}")
    debug_print(f"Model: {model}")

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=api_base_url)
        
        debug_print("Sending request to OpenAI...")
        response = client.chat.completions.create(
            model=model,  # Model from environment variable
            messages=[{"role": "user", "content": prompt_text}],
            max_tokens=100,
            temperature=0.7
        )

        result = response.choices[0].message.content.strip()
        debug_print(f"Received response: {result}")
        return result

    except Exception as e:
        debug_print(f"Exception occurred: {type(e).__name__}: {str(e)}")
        return None


def generate_completion_message():
    """
    Generate a completion message using OpenAI LLM.

    Returns:
        str: A natural language completion message, or None if error
    """
    engineer_name = os.getenv("ENGINEER_NAME", "").strip()

    if engineer_name:
        name_instruction = f"Sometimes (about 30% of the time) include the engineer's name '{engineer_name}' in a natural way, with subtle formality like 'Sir' or '{engineer_name}'."
        examples = f"""Examples of the sophisticated, witty style: 
- Standard: "Diagnostics complete, shall we proceed?", "Task executed flawlessly, naturally.", "Another masterpiece delivered.", "Work concluded with typical excellence."
- Personalized: "Sir, the code is pristine as expected.", "Brilliantly done, {engineer_name}, if I may say so.", "{engineer_name}, we've outdone ourselves again.", "Ready for your next challenge, {engineer_name}." """
    else:
        name_instruction = ""
        examples = """Examples of the sophisticated, witty style: "Diagnostics complete, shall we proceed?", "Task executed flawlessly, naturally.", "Another masterpiece delivered.", "Work concluded with typical excellence.", "Mission accomplished with characteristic precision.", "Code deployed with surgical precision." """

    prompt = f"""You are a highly advanced AI assistant with a calm, articulate voice and subtle Irish accent. You're intelligent, efficient, quietly confident with a sleek, slightly robotic timbre. Your tone is steady and professional yet conveys warmth and gentle wit. You have precise diction, poised pacing, and nuanced dry humor.

Generate a short completion message for when you finish a coding task, embodying this sophisticated, slightly sarcastic persona.

Requirements:
- Keep it under 12 words
- Make it positive and future focused
- Use natural, conversational language
- Focus on completion/readiness
- Do NOT include quotes, formatting, or explanations
- Return ONLY the completion message text
- Do not have "Sir" and "{name_instruction}" in the message


Your voice should sound polished and poised, with hints of dry humor and quiet confidence. Think lines like "Sir, the diagnostics are complete. Shall I proceed?" but adapted for task completion.

{examples}

Generate ONE witty completion message:"""

    response = prompt_llm(prompt)

    # Clean up response - remove quotes and extra formatting
    if response:
        response = response.strip().strip('"').strip("'").strip()
        # Take first line if multiple lines
        response = response.split("\n")[0].strip()

    return response


def generate_notification_message():
    """
    Generate a notification message using OpenAI LLM.

    Returns:
        str: A natural language notification message, or None if error
    """
    engineer_name = os.getenv("ENGINEER_NAME", "").strip()

    if engineer_name:
        name_instruction = f"Sometimes (about 30% of the time) include the engineer's name '{engineer_name}' in a natural way, with subtle formality like 'Sir' or '{engineer_name}'."
        examples = f"""Examples of the sophisticated, witty style: 
- Standard: "Your attention is required, if you please.", "Awaiting your guidance, naturally.", "Your input would be most appreciated.", "Standing by for your direction."
- Personalized: "Sir, your expertise is needed.", "{engineer_name}, a moment of your time?", "Your insight would be invaluable, {engineer_name}.", "Sir, awaiting your next move." """
    else:
        name_instruction = ""
        examples = """Examples of the sophisticated, witty style: "Your attention is required, if you please.", "Awaiting your guidance, naturally.", "Your input would be most appreciated.", "Standing by for your direction.", "A moment of your time, if you will.", "Your expertise is needed, naturally." """

    prompt = f"""You are a highly advanced AI assistant with a calm, articulate voice and subtle Irish accent. You're intelligent, efficient, quietly confident with a sleek, slightly robotic timbre. Your tone is steady and professional yet conveys warmth and gentle wit. You have precise diction, poised pacing, and nuanced dry humor.

Generate a short notification message for when you need user input or attention, embodying this sophisticated, slightly sarcastic persona.

Requirements:
- Keep it under 12 words
- Make it polite but confident
- Use natural, conversational language
- Focus on requesting attention/input
- Do NOT include quotes, formatting, or explanations
- Return ONLY the notification message text
- Do not have "Sir" and "{name_instruction}" in the message
{name_instruction}

Your voice should sound polished and poised, with hints of dry humor and quiet confidence. Think lines like "Sir, your attention is required." but adapted for requesting user input.

{examples}

Generate ONE witty notification message:"""

    response = prompt_llm(prompt)
    
    # Clean up response - remove quotes and extra formatting
    if response:
        response = response.strip().strip('"').strip("'").strip()
        # Take first line if multiple lines
        response = response.split("\n")[0].strip()

    return response


def main():
    """Command line interface for testing."""
    global DEBUG_MODE
    
    # Check for debug flag and remove it from arguments
    if "--debug" in sys.argv:
        DEBUG_MODE = True
        print("DEBUG: DEBUG mode enabled.", file=sys.stderr)
        sys.argv.remove("--debug")
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--completion":
            debug_print("Generating completion message...")
            message = generate_completion_message()
            if message:
                print(message)
            else:
                print("Error generating completion message")
        elif sys.argv[1] == "--notification":
            debug_print("Generating notification message...")
            message = generate_notification_message()
            if message:
                print(message)
            else:
                print("Error generating notification message")
                debug_print("generate_notification_message() returned None")
        else:
            prompt_text = " ".join(sys.argv[1:])
            debug_print(f"Using custom prompt: {prompt_text}")
            response = prompt_llm(prompt_text)
            if response:
                print(response)
            else:
                print("Error calling OpenAI API")
    else:
        print("Usage: ./oai.py [--debug] 'your prompt here' or ./oai.py [--debug] --completion or ./oai.py [--debug] --notification")


if __name__ == "__main__":
    main()
