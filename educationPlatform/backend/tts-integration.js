/**
 * TTS Integration for Existing HTML Frontends
 * Add this script to your existing HTML pages to enable TTS functionality
 * 
 * Usage:
 * 1. Include this script in your HTML: <script src="tts-integration.js"></script>
 * 2. Add TTS buttons to your content areas with class "tts-button"
 * 3. Use data-text attribute to specify text to speak, or it will use the element's text content
 * 
 * Example:
 * <button class="tts-button" data-text="Hello world">🔊 Speak</button>
 * <div id="ai-output">Your AI response here <button class="tts-button">🔊</button></div>
 */

// Configuration
const TTS_CONFIG = {
    API_BASE_URL: 'http://localhost:5001',
    DEFAULT_VOICE: 'en-US-AriaNeural',
    PREPROCESS_MATH: true,
    AUTO_RETRY: true
};

// Global TTS manager
window.TTSManager = {
    isInitialized: false,
    isPlaying: false,
    currentAudio: null,
    voices: [],
    userPreferences: null,
    
    // Initialize TTS system
    async init() {
        if (this.isInitialized) return;
        
        try {
            await this.loadVoices();
            this.setupTTSButtons();
            this.setupKeyboardShortcuts();
            await this.loadUserPreferences();
            this.isInitialized = true;
            console.log('TTS Manager initialized successfully');
        } catch (error) {
            console.error('TTS Manager initialization failed:', error);
        }
    },
    
    // Load available voices from API
    async loadVoices() {
        try {
            const response = await fetch(`${TTS_CONFIG.API_BASE_URL}/api/voices`);
            const data = await response.json();
            this.voices = data.voices || [];
        } catch (error) {
            console.warn('Failed to load voices from API, using browser fallback:', error);
            this.voices = [{ id: 'browser-default', name: 'Browser Default', provider: 'browser' }];
        }
    },
    
    // Setup TTS buttons for existing elements
    setupTTSButtons() {
        // Find all elements with class 'tts-button' or add buttons to content areas
        document.querySelectorAll('.tts-button').forEach(button => {
            this.setupTTSButton(button);
        });
        
        // Auto-add TTS buttons to common content areas
        this.autoAddTTSButtons();
    },
    
    // Setup individual TTS button
    setupTTSButton(button) {
        if (button.dataset.ttsSetup) return; // Already setup
        
        button.dataset.ttsSetup = 'true';
        button.style.cursor = 'pointer';
        
        // Add accessibility attributes
        button.setAttribute('aria-label', 'Read text aloud');
        button.setAttribute('title', 'Click to read text aloud');
        
        button.addEventListener('click', async (event) => {
            event.preventDefault();
            event.stopPropagation();
            
            const text = this.getTextToSpeak(button);
            if (text) {
                await this.speak(text);
            }
        });
    },
    
    // Auto-add TTS buttons to content areas
    autoAddTTSButtons() {
        // Common selectors for AI output areas
        const selectors = [
            '#ai-output',
            '.ai-response',
            '.chat-message',
            '.response-content',
            '.generated-content',
            '.explanation',
            '.answer'
        ];
        
        selectors.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(element => {
                if (!element.querySelector('.tts-button')) {
                    this.addTTSButtonToElement(element);
                }
            });
        });
    },
    
    // Add TTS button to a specific element
    addTTSButtonToElement(element) {
        const button = document.createElement('button');
        button.className = 'tts-button';
        button.innerHTML = '🔊';
        button.style.cssText = `
            background: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 12px;
            margin-left: 10px;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.3s ease;
            vertical-align: middle;
        `;
        
        button.addEventListener('mouseenter', () => {
            button.style.background = '#2980b9';
        });
        
        button.addEventListener('mouseleave', () => {
            button.style.background = '#3498db';
        });
        
        element.style.position = 'relative';
        element.appendChild(button);
        this.setupTTSButton(button);
    },
    
    // Get text to speak from button or its context
    getTextToSpeak(button) {
        // Priority order:
        // 1. data-text attribute
        // 2. Parent element's text content
        // 3. Button's text content
        
        if (button.dataset.text) {
            return button.dataset.text;
        }
        
        const parent = button.parentElement;
        if (parent) {
            // Get text content excluding the button itself
            const clone = parent.cloneNode(true);
            const buttons = clone.querySelectorAll('.tts-button');
            buttons.forEach(btn => btn.remove());
            
            const text = clone.textContent.trim();
            if (text && text.length > 10) { // Minimum meaningful text length
                return text;
            }
        }
        
        return button.textContent.replace('🔊', '').trim();
    },
    
    // Main speak function
    async speak(text, options = {}) {
        if (!text || text.trim().length === 0) {
            this.showNotification('No text to speak', 'warning');
            return;
        }
        
        // Stop any ongoing speech
        this.stop();
        
        const voice = options.voice || this.userPreferences?.voice || TTS_CONFIG.DEFAULT_VOICE;
        const preprocess = options.preprocess !== undefined ? options.preprocess : TTS_CONFIG.PREPROCESS_MATH;
        
        try {
            this.setPlayingState(true);
            
            if (voice === 'browser-default') {
                await this.speakWithBrowser(text, options);
            } else {
                await this.speakWithAzure(text, voice, preprocess);
            }
            
        } catch (error) {
            console.error('TTS error:', error);
            this.showNotification('Speech synthesis failed', 'error');
            
            // Fallback to browser TTS
            if (TTS_CONFIG.AUTO_RETRY && voice !== 'browser-default') {
                console.log('Retrying with browser TTS...');
                await this.speakWithBrowser(text, options);
            }
        }
    },
    
    // Speak using Azure TTS API
    async speakWithAzure(text, voice, preprocess) {
        try {
            const response = await fetch(`${TTS_CONFIG.API_BASE_URL}/api/tts`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: text,
                    voice: voice,
                    preprocess: preprocess
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const contentType = response.headers.get('content-type');
            
            if (contentType && contentType.includes('audio')) {
                // Azure returned audio
                const audioBlob = await response.blob();
                const audioUrl = URL.createObjectURL(audioBlob);
                
                const audio = new Audio(audioUrl);
                this.currentAudio = { type: 'azure', audio };
                
                audio.onended = () => this.setPlayingState(false);
                audio.onerror = () => {
                    this.setPlayingState(false);
                    throw new Error('Audio playback failed');
                };
                
                await audio.play();
                
            } else {
                // Fallback response
                const data = await response.json();
                if (data.fallback) {
                    await this.speakWithBrowser(data.text);
                } else {
                    throw new Error(data.error || 'Unknown error');
                }
            }
            
        } catch (error) {
            throw new Error(`Azure TTS failed: ${error.message}`);
        }
    },
    
    // Speak using browser Web Speech API
    async speakWithBrowser(text, options = {}) {
        return new Promise((resolve, reject) => {
            if (!('speechSynthesis' in window)) {
                reject(new Error('Browser TTS not supported'));
                return;
            }
            
            window.speechSynthesis.cancel();
            
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = options.speed || this.userPreferences?.speed || 1.0;
            utterance.pitch = options.pitch || this.userPreferences?.pitch || 1.0;
            
            // Try to find a good voice
            const voices = window.speechSynthesis.getVoices();
            const englishVoice = voices.find(v => v.lang.startsWith('en'));
            if (englishVoice) {
                utterance.voice = englishVoice;
            }
            
            utterance.onend = () => {
                this.setPlayingState(false);
                resolve();
            };
            
            utterance.onerror = (event) => {
                this.setPlayingState(false);
                reject(new Error(`Browser TTS failed: ${event.error}`));
            };
            
            window.speechSynthesis.speak(utterance);
            this.currentAudio = { type: 'browser', utterance };
        });
    },
    
    // Stop current speech
    stop() {
        if (this.currentAudio) {
            if (this.currentAudio.type === 'browser') {
                window.speechSynthesis.cancel();
            } else if (this.currentAudio.audio) {
                this.currentAudio.audio.pause();
                this.currentAudio.audio.currentTime = 0;
            }
        }
        
        this.setPlayingState(false);
    },
    
    // Set playing state and update UI
    setPlayingState(playing) {
        this.isPlaying = playing;
        
        // Update all TTS buttons
        document.querySelectorAll('.tts-button').forEach(button => {
            if (playing) {
                button.disabled = true;
                button.style.opacity = '0.6';
                if (button.innerHTML === '🔊') {
                    button.innerHTML = '⏸️';
                }
            } else {
                button.disabled = false;
                button.style.opacity = '1';
                if (button.innerHTML === '⏸️') {
                    button.innerHTML = '🔊';
                }
            }
        });
    },
    
    // Setup keyboard shortcuts
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (event) => {
            // Ctrl+Shift+S: Speak selected text or current page content
            if (event.ctrlKey && event.shiftKey && event.key === 'S') {
                event.preventDefault();
                
                const selectedText = window.getSelection().toString().trim();
                if (selectedText) {
                    this.speak(selectedText);
                } else {
                    // Speak main content
                    const mainContent = this.getMainContent();
                    if (mainContent) {
                        this.speak(mainContent);
                    }
                }
            }
            
            // Escape: Stop speaking
            if (event.key === 'Escape' && this.isPlaying) {
                this.stop();
            }
        });
    },
    
    // Get main content from page
    getMainContent() {
        const selectors = [
            'main',
            '.content',
            '.main-content',
            '#content',
            'article',
            '.article-content'
        ];
        
        for (const selector of selectors) {
            const element = document.querySelector(selector);
            if (element) {
                const text = element.textContent.trim();
                if (text.length > 50) {
                    return text;
                }
            }
        }
        
        // Fallback to body content
        return document.body.textContent.trim();
    },
    
    // Load user preferences
    async loadUserPreferences() {
        try {
            const userId = this.getUserId();
            if (!userId) return;
            
            const response = await fetch(`${TTS_CONFIG.API_BASE_URL}/api/preferences/${userId}`);
            const data = await response.json();
            
            if (data.preferences) {
                this.userPreferences = data.preferences;
            }
            
        } catch (error) {
            console.warn('Failed to load user preferences:', error);
        }
    },
    
    // Get user ID (implement based on your authentication system)
    getUserId() {
        // Try to get from localStorage, sessionStorage, or other sources
        return localStorage.getItem('userId') || 
               sessionStorage.getItem('userId') || 
               'anonymous-user';
    },
    
    // Show notification to user
    showNotification(message, type = 'info') {
        // Create simple notification
        const notification = document.createElement('div');
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${type === 'error' ? '#e74c3c' : type === 'warning' ? '#f39c12' : '#3498db'};
            color: white;
            padding: 12px 20px;
            border-radius: 4px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            z-index: 10000;
            font-family: Arial, sans-serif;
            font-size: 14px;
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 3000);
    },
    
    // Public API for manual integration
    addTTSToElement(element, text = null) {
        if (text) {
            element.dataset.text = text;
        }
        element.classList.add('tts-button');
        this.setupTTSButton(element);
    },
    
    // Check if TTS is available
    isAvailable() {
        return 'speechSynthesis' in window || this.voices.length > 0;
    }
};

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.TTSManager.init();
    });
} else {
    window.TTSManager.init();
}

// Watch for dynamically added content
const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        if (mutation.type === 'childList') {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === Node.ELEMENT_NODE) {
                    // Check if new content areas need TTS buttons
                    const contentAreas = node.querySelectorAll('#ai-output, .ai-response, .chat-message');
                    contentAreas.forEach((area) => {
                        if (!area.querySelector('.tts-button')) {
                            window.TTSManager.addTTSButtonToElement(area);
                        }
                    });
                    
                    // Setup any new TTS buttons
                    const newButtons = node.querySelectorAll('.tts-button:not([data-tts-setup])');
                    newButtons.forEach((button) => {
                        window.TTSManager.setupTTSButton(button);
                    });
                }
            });
        }
    });
});

// Start observing
observer.observe(document.body, {
    childList: true,
    subtree: true
});

// Export for use in modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = window.TTSManager;
}
