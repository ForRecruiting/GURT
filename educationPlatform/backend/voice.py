"""
Text-to-Speech (TTS) Backend API for Educational Platform
Supports Azure Speech Services with browser Web Speech API fallback
Handles math/CS content with accessibility optimizations
"""

import os
import re
import json
import logging
import time
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from functools import wraps
import tempfile

import requests
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from azure.cognitiveservices.speech import (
    SpeechConfig, 
    SpeechSynthesizer, 
    AudioConfig,
    SpeechSynthesisOutputFormat
)
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import AzureError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, origins=["*"])  # Configure for your domain in production

# Configuration from environment variables
class Config:
    AZURE_SPEECH_KEY = os.getenv('AZURE_SPEECH_KEY')
    AZURE_SPEECH_REGION = os.getenv('AZURE_SPEECH_REGION', 'eastus')
    AZURE_SPEECH_ENDPOINT = os.getenv('AZURE_SPEECH_ENDPOINT')
    
    # Rate limiting for demo
    RATE_LIMIT_REQUESTS = int(os.getenv('RATE_LIMIT_REQUESTS', '10'))
    RATE_LIMIT_WINDOW = int(os.getenv('RATE_LIMIT_WINDOW', '60'))  # seconds
    
    # TTS settings
    DEFAULT_VOICE = os.getenv('DEFAULT_VOICE', 'en-US-AriaNeural')
    AUDIO_FORMAT = os.getenv('AUDIO_FORMAT', 'audio-16khz-32kbitrate-mono-mp3')
    MAX_TEXT_LENGTH = int(os.getenv('MAX_TEXT_LENGTH', '5000'))
    
    # Fallback settings
    ENABLE_AZURE_TTS = os.getenv('ENABLE_AZURE_TTS', 'true').lower() == 'true'

# Rate limiting store (use Redis in production)
rate_limit_store = {}

# User preferences store (use database in production)
user_preferences = {}

def clean_rate_limit_store():
    """Clean expired rate limit entries"""
    current_time = time.time()
    expired_keys = [
        key for key, data in rate_limit_store.items()
        if current_time - data['window_start'] > Config.RATE_LIMIT_WINDOW
    ]
    for key in expired_keys:
        del rate_limit_store[key]

def rate_limit(f):
    """Rate limiting decorator"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.remote_addr
        current_time = time.time()
        
        # Clean old entries
        clean_rate_limit_store()
        
        if client_ip not in rate_limit_store:
            rate_limit_store[client_ip] = {
                'count': 0,
                'window_start': current_time
            }
        
        client_data = rate_limit_store[client_ip]
        
        # Reset window if expired
        if current_time - client_data['window_start'] > Config.RATE_LIMIT_WINDOW:
            client_data['count'] = 0
            client_data['window_start'] = current_time
        
        # Check rate limit
        if client_data['count'] >= Config.RATE_LIMIT_REQUESTS:
            return jsonify({
                'error': 'Rate limit exceeded',
                'retry_after': Config.RATE_LIMIT_WINDOW - (current_time - client_data['window_start'])
            }), 429
        
        client_data['count'] += 1
        return f(*args, **kwargs)
    
    return decorated_function

def preprocess_math_content(text: str) -> str:
    """
    Preprocess mathematical and CS content for better TTS pronunciation
    """
    # Math symbols and expressions
    math_replacements = {
        # Basic operators
        r'\+': ' plus ',
        r'\-': ' minus ',
        r'\*': ' times ',
        r'\/': ' divided by ',
        r'\=': ' equals ',
        r'\<': ' less than ',
        r'\>': ' greater than ',
        r'\<=': ' less than or equal to ',
        r'\>=': ' greater than or equal to ',
        r'\!=': ' not equal to ',
        
        # Mathematical notation
        r'\^(\d+)': r' to the power of \1 ',
        r'sqrt\(([^)]+)\)': r' square root of \1 ',
        r'log\(([^)]+)\)': r' logarithm of \1 ',
        r'sin\(([^)]+)\)': r' sine of \1 ',
        r'cos\(([^)]+)\)': r' cosine of \1 ',
        r'tan\(([^)]+)\)': r' tangent of \1 ',
        
        # Programming concepts
        r'def\s+(\w+)': r'define function \1',
        r'class\s+(\w+)': r'class \1',
        r'for\s+(\w+)\s+in': r'for each \1 in',
        r'while\s+': 'while ',
        r'if\s+': 'if ',
        r'else:': 'else',
        r'elif\s+': 'else if ',
        r'return\s+': 'return ',
        
        # Common CS terms
        r'\bAPI\b': 'A P I',
        r'\bHTML\b': 'H T M L',
        r'\bCSS\b': 'C S S',
        r'\bJSON\b': 'Jason',
        r'\bSQL\b': 'sequel',
        r'\bHTTP\b': 'H T T P',
        r'\bURL\b': 'U R L',
        r'\bGUI\b': 'G U I',
        r'\bCPU\b': 'C P U',
        r'\bGPU\b': 'G P U',
        r'\bRAM\b': 'R A M',
        
        # Code symbols
        r'\{': ' open brace ',
        r'\}': ' close brace ',
        r'\[': ' open bracket ',
        r'\]': ' close bracket ',
        r'\(': ' open parenthesis ',
        r'\)': ' close parenthesis ',
        r';': ' semicolon ',
        r':': ' colon ',
        r'\.': ' dot ',
        r',': ' comma ',
    }
    
    processed_text = text
    for pattern, replacement in math_replacements.items():
        processed_text = re.sub(pattern, replacement, processed_text)
    
    # Clean up extra spaces
    processed_text = re.sub(r'\s+', ' ', processed_text).strip()
    
    return processed_text

def get_azure_speech_config() -> Optional[SpeechConfig]:
    """Get Azure Speech configuration with error handling"""
    try:
        if not Config.AZURE_SPEECH_KEY or not Config.AZURE_SPEECH_REGION:
            logger.warning("Azure Speech credentials not configured")
            return None
        
        speech_config = SpeechConfig(
            subscription=Config.AZURE_SPEECH_KEY,
            region=Config.AZURE_SPEECH_REGION
        )
        
        # Set output format for web compatibility
        speech_config.set_speech_synthesis_output_format(
            SpeechSynthesisOutputFormat.Audio16Khz32KBitRateMonoMp3
        )
        
        return speech_config
    except Exception as e:
        logger.error(f"Failed to create Azure Speech config: {e}")
        return None

def synthesize_with_azure(text: str, voice: str = None) -> Optional[bytes]:
    """Synthesize speech using Azure Speech Services"""
    try:
        speech_config = get_azure_speech_config()
        if not speech_config:
            return None
        
        # Set voice
        speech_config.speech_synthesis_voice_name = voice or Config.DEFAULT_VOICE
        
        # Use in-memory audio output
        synthesizer = SpeechSynthesizer(speech_config=speech_config, audio_config=None)
        
        # Synthesize speech
        result = synthesizer.speak_text_async(text).get()
        
        if result.reason.name == 'SynthesizingAudioCompleted':
            return result.audio_data
        else:
            logger.error(f"Azure TTS failed: {result.reason}")
            return None
            
    except AzureError as e:
        logger.error(f"Azure Speech error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in Azure TTS: {e}")
        return None

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'azure_speech_available': Config.ENABLE_AZURE_TTS and bool(Config.AZURE_SPEECH_KEY),
        'version': '1.0.0'
    }
    
    # Test Azure Speech if configured
    if status['azure_speech_available']:
        try:
            speech_config = get_azure_speech_config()
            status['azure_speech_status'] = 'configured' if speech_config else 'error'
        except Exception:
            status['azure_speech_status'] = 'error'
    
    return jsonify(status)

@app.route('/api/voices', methods=['GET'])
@rate_limit
def get_voices():
    """Get available voices for TTS"""
    try:
        voices = []
        
        # Azure voices (if available)
        if Config.ENABLE_AZURE_TTS and Config.AZURE_SPEECH_KEY:
            azure_voices = [
                {
                    'id': 'en-US-AriaNeural',
                    'name': 'Aria (US English)',
                    'language': 'en-US',
                    'gender': 'female',
                    'provider': 'azure',
                    'recommended': True
                },
                {
                    'id': 'en-US-DavisNeural',
                    'name': 'Davis (US English)',
                    'language': 'en-US',
                    'gender': 'male',
                    'provider': 'azure',
                    'recommended': True
                },
                {
                    'id': 'en-GB-SoniaNeural',
                    'name': 'Sonia (UK English)',
                    'language': 'en-GB',
                    'gender': 'female',
                    'provider': 'azure'
                },
                {
                    'id': 'en-AU-NatashaNeural',
                    'name': 'Natasha (Australian English)',
                    'language': 'en-AU',
                    'gender': 'female',
                    'provider': 'azure'
                }
            ]
            voices.extend(azure_voices)
        
        # Browser fallback voices
        browser_voices = [
            {
                'id': 'browser-default',
                'name': 'Browser Default',
                'language': 'en-US',
                'gender': 'system',
                'provider': 'browser',
                'fallback': True
            }
        ]
        voices.extend(browser_voices)
        
        return jsonify({
            'voices': voices,
            'default_voice': Config.DEFAULT_VOICE,
            'azure_available': Config.ENABLE_AZURE_TTS and bool(Config.AZURE_SPEECH_KEY)
        })
        
    except Exception as e:
        logger.error(f"Error getting voices: {e}")
        return jsonify({'error': 'Failed to get voices'}), 500

@app.route('/api/tts', methods=['POST'])
@rate_limit
def text_to_speech():
    """Convert text to speech"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'Text is required'}), 400
        
        text = data['text'].strip()
        if not text:
            return jsonify({'error': 'Text cannot be empty'}), 400
        
        if len(text) > Config.MAX_TEXT_LENGTH:
            return jsonify({'error': f'Text too long. Maximum {Config.MAX_TEXT_LENGTH} characters'}), 400
        
        voice = data.get('voice', Config.DEFAULT_VOICE)
        preprocess = data.get('preprocess', True)
        
        # Preprocess math/CS content if requested
        if preprocess:
            processed_text = preprocess_math_content(text)
        else:
            processed_text = text
        
        logger.info(f"TTS request: {len(text)} chars, voice: {voice}")
        
        # Try Azure TTS first
        if Config.ENABLE_AZURE_TTS and voice != 'browser-default':
            audio_data = synthesize_with_azure(processed_text, voice)
            if audio_data:
                # Create temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                    tmp_file.write(audio_data)
                    tmp_file_path = tmp_file.name
                
                def remove_file(response):
                    try:
                        os.unlink(tmp_file_path)
                    except OSError:
                        pass
                    return response
                
                response = send_file(
                    tmp_file_path,
                    as_attachment=False,
                    mimetype='audio/mpeg',
                    download_name='speech.mp3'
                )
                response.call_on_close(remove_file)
                
                return response
        
        # Fallback to browser TTS instructions
        return jsonify({
            'fallback': True,
            'text': processed_text,
            'voice': voice,
            'message': 'Use browser Web Speech API for TTS',
            'instructions': {
                'api': 'speechSynthesis',
                'method': 'speak',
                'voice_selection': 'getVoices()'
            }
        })
        
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return jsonify({'error': 'TTS service temporarily unavailable'}), 500

@app.route('/api/preferences', methods=['POST'])
@rate_limit
def save_preferences():
    """Save user TTS preferences"""
    try:
        data = request.get_json()
        if not data or 'user_id' not in data:
            return jsonify({'error': 'User ID is required'}), 400
        
        user_id = data['user_id']
        preferences = {
            'voice': data.get('voice', Config.DEFAULT_VOICE),
            'speed': float(data.get('speed', 1.0)),
            'pitch': float(data.get('pitch', 1.0)),
            'preprocess_math': data.get('preprocess_math', True),
            'auto_play': data.get('auto_play', False),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        # Validate preferences
        if not (0.1 <= preferences['speed'] <= 3.0):
            return jsonify({'error': 'Speed must be between 0.1 and 3.0'}), 400
        
        if not (0.5 <= preferences['pitch'] <= 2.0):
            return jsonify({'error': 'Pitch must be between 0.5 and 2.0'}), 400
        
        # Store preferences (use database in production)
        user_preferences[user_id] = preferences
        
        logger.info(f"Saved preferences for user: {user_id}")
        
        return jsonify({
            'success': True,
            'preferences': preferences
        })
        
    except ValueError as e:
        return jsonify({'error': 'Invalid numeric value'}), 400
    except Exception as e:
        logger.error(f"Error saving preferences: {e}")
        return jsonify({'error': 'Failed to save preferences'}), 500

@app.route('/api/preferences/<user_id>', methods=['GET'])
@rate_limit
def get_preferences(user_id):
    """Get user TTS preferences"""
    try:
        if user_id in user_preferences:
            return jsonify({
                'preferences': user_preferences[user_id],
                'found': True
            })
        else:
            # Return defaults
            default_preferences = {
                'voice': Config.DEFAULT_VOICE,
                'speed': 1.0,
                'pitch': 1.0,
                'preprocess_math': True,
                'auto_play': False
            }
            return jsonify({
                'preferences': default_preferences,
                'found': False
            })
            
    except Exception as e:
        logger.error(f"Error getting preferences: {e}")
        return jsonify({'error': 'Failed to get preferences'}), 500

@app.route('/api/test', methods=['GET'])
def test_endpoint():
    """Test endpoint for debugging"""
    return jsonify({
        'message': 'TTS API is running',
        'azure_configured': bool(Config.AZURE_SPEECH_KEY),
        'endpoints': [
            '/health',
            '/api/voices',
            '/api/tts',
            '/api/preferences',
            '/api/preferences/<user_id>'
        ]
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Ensure required environment variables are set
    if not Config.AZURE_SPEECH_KEY:
        logger.warning("AZURE_SPEECH_KEY not set. TTS will use browser fallback only.")
    
    logger.info("Starting TTS API server...")
    logger.info(f"Azure TTS enabled: {Config.ENABLE_AZURE_TTS}")
    logger.info(f"Default voice: {Config.DEFAULT_VOICE}")
    
    # Run Flask app
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5001)),
        debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    )
