/**
 * MyVoiceTranslator Chrome Extension - Background Service Worker
 * Coordinates tab capture, offscreen audio processing, and WebSocket streaming.
 */

const WS_URL = 'ws://localhost:8000/transcribe';
let isCapturing = false;
let currentTabId = null;
let offscreenDocumentCreated = false;

// Initialize offscreen document
async function ensureOffscreenDocument() {
  if (offscreenDocumentCreated) return;
  
  const existing = await chrome.offscreen.hasDocument();
  if (existing) {
    offscreenDocumentCreated = true;
    return;
  }
  
  await chrome.offscreen.createDocument({
    url: 'offscreen.html',
    reasons: ['AUDIO_PLAYBACK'],
    justification: 'Real-time audio resampling for WebSocket streaming'
  });
  offscreenDocumentCreated = true;
}

// Start capturing audio from a tab
async function startCapture(tabId) {
  if (isCapturing) {
    console.log('[MyVoiceTranslator] Already capturing');
    return { success: false, error: 'Already capturing' };
  }
  
  try {
    // Ensure offscreen document exists
    await ensureOffscreenDocument();
    
    // Capture tab audio
    const streamId = await chrome.tabCapture.getMediaStreamId({
      targetTabId: tabId
    });
    
    if (!streamId) {
      throw new Error('Failed to get media stream ID - user may have denied permission');
    }
    
    currentTabId = tabId;
    isCapturing = true;
    
    // Send stream ID to offscreen document for processing
    chrome.runtime.sendMessage({
      type: 'init_audio',
      streamId: streamId
    });
    
    // Connect WebSocket from offscreen document
    chrome.runtime.sendMessage({
      type: 'connect_websocket',
      url: WS_URL
    });
    
    console.log('[MyVoiceTranslator] Capture started for tab:', tabId);
    
    // Notify side panel
    chrome.runtime.sendMessage({ type: 'capture_started' });
    
    return { success: true };
    
  } catch (error) {
    console.error('[MyVoiceTranslator] Capture failed:', error);
    isCapturing = false;
    currentTabId = null;
    return { success: false, error: error.message };
  }
}

// Stop audio capture
async function stopCapture() {
  if (!isCapturing) return { success: true };
  
  isCapturing = false;
  currentTabId = null;
  
  // Tell offscreen document to stop
  chrome.runtime.sendMessage({ type: 'stop_audio' });
  
  // Close offscreen document
  await chrome.offscreen.closeDocument();
  offscreenDocumentCreated = false;
  
  console.log('[MyVoiceTranslator] Capture stopped');
  
  // Notify side panel
  chrome.runtime.sendMessage({ type: 'capture_stopped' });
  
  return { success: true };
}

// Handle messages from side panel / popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message.type) {
    case 'start_capture':
      startCapture(message.tabId)
        .then(result => sendResponse(result))
        .catch(error => sendResponse({ success: false, error: error.message }));
      return true;
      
    case 'stop_capture':
      stopCapture()
        .then(result => sendResponse(result))
        .catch(error => sendResponse({ success: false, error: error.message }));
      return true;
      
    case 'get_status':
      sendResponse({ 
        isCapturing, 
        currentTabId 
      });
      return true;
      
    case 'switch_to_tui':
      fetch('http://localhost:8000/api/switch-to-tui', { method: 'POST' })
        .then(r => r.json())
        .then(data => sendResponse({ success: true, data }))
        .catch(err => sendResponse({ success: false, error: err.message }));
      return true;
      
    // Forward transcript/status messages from offscreen to side panel
    case 'transcript':
    case 'status':
    case 'audio_state':
      chrome.runtime.sendMessage({ type: message.type, data: message.data });
      break;
  }
});

// Handle tab closure/navigation
chrome.tabs.onRemoved.addListener((tabId) => {
  if (isCapturing && tabId === currentTabId) {
    console.log('[MyVoiceTranslator] Captured tab closed, stopping capture');
    stopCapture();
  }
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (isCapturing && tabId === currentTabId && changeInfo.status === 'loading') {
    console.log('[MyVoiceTranslator] Captured tab navigating, stopping capture');
    stopCapture();
  }
});

console.log('[MyVoiceTranslator] Background service worker loaded');