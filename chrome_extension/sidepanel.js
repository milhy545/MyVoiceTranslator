/**
 * MyVoiceTranslator Chrome Extension - Side Panel UI
 * Displays live transcriptions and controls
 */

// State
let isCapturing = false;
let currentTabId = null;
let historyItems = [];

// DOM Elements
const elements = {
  statusDot: document.getElementById('statusDot'),
  statusText: document.getElementById('statusText'),
  enContent: document.getElementById('enContent'),
  czContent: document.getElementById('czContent'),
  historyContent: document.getElementById('historyContent'),
  startBtn: document.getElementById('startBtn'),
  stopBtn: document.getElementById('stopBtn'),
  switchToTuiBtn: document.getElementById('switchToTuiBtn'),
  clearHistoryBtn: document.getElementById('clearHistoryBtn'),
  levelBar: document.getElementById('levelBar'),
  audioLevel: document.getElementById('audioLevel')
};

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  await checkServerConnection();
  setupEventListeners();
  loadHistory();
  updateUI();
});

// Check server connection
async function checkServerConnection() {
  try {
    const response = await fetch('http://localhost:8000/health', { 
      method: 'GET',
      timeout: 2000
    });
    if (response.ok) {
      setConnectionStatus('connected', 'Connected');
      // Get current capture status
      chrome.runtime.sendMessage({ type: 'get_status' }, (response) => {
        if (response) {
          isCapturing = response.isCapturing;
          currentTabId = response.currentTabId;
          updateUI();
        }
      });
    } else {
      setConnectionStatus('disconnected', 'Server Error');
    }
  } catch (error) {
    setConnectionStatus('disconnected', 'Server Offline');
  }
}

// Setup event listeners
function setupEventListeners() {
  // Start capture button
  elements.startBtn.addEventListener('click', async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab) return;
    
    setConnectionStatus('connecting', 'Starting...');
    elements.startBtn.disabled = true;
    
    chrome.runtime.sendMessage(
      { type: 'start_capture', tabId: tab.id },
      (response) => {
        elements.startBtn.disabled = false;
        if (response && response.success) {
          isCapturing = true;
          currentTabId = tab.id;
          setConnectionStatus('connected', 'Capturing');
          elements.audioLevel.style.display = 'block';
          updateUI();
        } else {
          setConnectionStatus('connected', 'Error: ' + (response?.error || 'Unknown'));
        }
      }
    );
  });
  
  // Stop capture button
  elements.stopBtn.addEventListener('click', () => {
    chrome.runtime.sendMessage({ type: 'stop_capture' }, (response) => {
      if (response && response.success) {
        isCapturing = false;
        currentTabId = null;
        setConnectionStatus('connected', 'Connected');
        elements.audioLevel.style.display = 'none';
        elements.levelBar.style.width = '0%';
        updateUI();
      }
    });
  });
  
  // Switch to TUI button
  elements.switchToTuiBtn.addEventListener('click', () => {
    if (confirm('Switch to Terminal mode? This will stop the server and close the extension connection.')) {
      chrome.runtime.sendMessage({ type: 'switch_to_tui' }, (response) => {
        if (response && response.success) {
          setConnectionStatus('disconnected', 'Switched to TUI');
          isCapturing = false;
          elements.audioLevel.style.display = 'none';
          updateUI();
        } else {
          alert('Failed to switch: ' + (response?.error || 'Unknown error'));
        }
      });
    }
  });
  
  // Clear history button
  elements.clearHistoryBtn.addEventListener('click', () => {
    historyItems = [];
    saveHistory();
    renderHistory();
  });
  
  // Listen for messages from background script
  chrome.runtime.onMessage.addListener((message) => {
    switch (message.type) {
      case 'transcript':
        handleTranscript(message.data);
        break;
      case 'status':
        handleStatus(message.data);
        break;
      case 'audio_state':
        handleAudioState(message.data);
        break;
      case 'capture_started':
        isCapturing = true;
        elements.audioLevel.style.display = 'block';
        updateUI();
        break;
      case 'capture_stopped':
        isCapturing = false;
        elements.audioLevel.style.display = 'none';
        elements.levelBar.style.width = '0%';
        updateUI();
        break;
    }
  });
}

// Handle transcript from server
function handleTranscript(data) {
  const { type, english, czech, backend, input_mode } = data;
  
  if (type === 'partial_transcript') {
    // Show partial in EN panel
    elements.enContent.textContent = english || '...';
    elements.czContent.textContent = 'Translating...';
  } else if (type === 'transcript') {
    // Show final transcript
    elements.enContent.textContent = english;
    elements.czContent.textContent = czech;
    
    // Add to history
    addToHistory('en', english);
    addToHistory('cz', czech);
  }
}

// Handle status messages
function handleStatus(data) {
  const { level, message } = data;
  console.log(`[Status:${level}]`, message);
  
  // Update connection status for important messages
  if (level === 'error') {
    setConnectionStatus('connected', 'Error: ' + message);
  }
}

// Handle audio state changes
function handleAudioState(data) {
  const { state } = data;
  
  // Visual feedback for audio state
  switch (state) {
    case 'Speaking':
      elements.levelBar.style.background = 'linear-gradient(90deg, #22c55e, #fccc15)';
      break;
    case 'Transcribing':
      elements.levelBar.style.background = 'linear-gradient(90deg, #f59e0b, #ef4444)';
      break;
    default:
      elements.levelBar.style.background = 'linear-gradient(90deg, #2dd4bf, #fccc15)';
  }
}

// Simulate audio level (since we don't get real levels from server)
function simulateAudioLevel() {
  if (!isCapturing) return;
  
  // Random level for visual feedback
  const level = Math.random() * 60 + 20;
  elements.levelBar.style.width = level + '%';
  
  setTimeout(simulateAudioLevel, 100);
}

// Update UI based on state
function updateUI() {
  elements.startBtn.disabled = isCapturing;
  elements.stopBtn.disabled = !isCapturing;
  
  if (isCapturing) {
    elements.startBtn.querySelector('span').textContent = 'Capturing...';
    simulateAudioLevel();
  } else {
    elements.startBtn.querySelector('span').textContent = 'Start Capture';
  }
}

// Connection status
function setConnectionStatus(status, text) {
  elements.statusDot.className = 'status-dot ' + status;
  elements.statusText.textContent = text;
}

// History management
function addToHistory(lang, text) {
  if (!text || text.trim() === '' || text === 'Waiting for speech...' || text === 'Waiting for translation...') return;
  
  const item = {
    lang,
    text: text.trim(),
    timestamp: Date.now()
  };
  
  historyItems.unshift(item);
  
  // Keep only last 50 items
  if (historyItems.length > 50) {
    historyItems = historyItems.slice(0, 50);
  }
  
  saveHistory();
  renderHistory();
}

function saveHistory() {
  chrome.storage.local.set({ 'myvoicetranslator_history': historyItems });
}

function loadHistory() {
  chrome.storage.local.get('myvoicetranslator_history', (result) => {
    if (result.myvoicetranslator_history) {
      historyItems = result.myvoicetranslator_history;
      renderHistory();
    }
  });
}

function renderHistory() {
  if (historyItems.length === 0) {
    elements.historyContent.innerHTML = '<div class="history-empty">No transcriptions yet</div>';
    return;
  }
  
  elements.historyContent.innerHTML = historyItems.map(item => `
    <div class="history-item ${item.lang}">
      <div class="history-item-header">
        <span>${item.lang === 'en' ? 'ENG' : 'CZE'}</span>
        <span>${new Date(item.timestamp).toLocaleTimeString()}</span>
      </div>
      <div class="history-item-text">${escapeHtml(item.text)}</div>
    </div>
  `).join('');
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}