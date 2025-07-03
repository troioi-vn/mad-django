
import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)


def call_gemini_api(prompt: str, api_key: str, parameters: dict = None) -> str:
    """
    Calls the Gemini API to get a response to a prompt.
    """
    logger.info(
        f"Calling Gemini API with prompt (first 100 chars): {prompt[:100]}..."
    )
    logger.info(f"Using API Key: {api_key[:5]}...")

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        generation_config = None
        if parameters:
            generation_config = genai.types.GenerationConfig(**parameters)


        response = model.generate_content(prompt, generation_config=generation_config)

        logger.info("Gemini API call completed.")
        return response.text
    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        raise  # Re-raise the exception to be handled by the caller
