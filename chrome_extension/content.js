/**
 * MyVoiceTranslator Chrome Extension - Content Script
 * Injects floating subtitles overlay using Shadow DOM for style isolation
 */

(function() {
  'use strict';
  
  // State
  let subtitleContainer = null;
  let enSubtitle = null;
  let czSubtitle = null;
  let isVisible = false;
  let dragOffset = { x: 0, y: 0 };
  let isDragging = false;
  
  // Create Shadow DOM for style isolation
  function createSubtitleOverlay() {
    if (subtitleContainer) return;
    
    // Create container
    const container = document.createElement('div');
    container.id = 'myvoicetranslator-subtitles';
    
    // Attach Shadow DOM
    const shadow = container.attachShadow({ mode: 'open' });
    
    // Styles
    const style = document.createElement('style');
    style.textContent = `
      :host {
        position: fixed;
        bottom: 80px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 2147483647;
        pointer-events: none;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      }
      
      :host(.dragging) {
        pointer-events: auto;
        cursor: grab;
      }
      
      .subtitle-wrapper {
        display: flex;
        flex-direction: column;
        gap: 4px;
        max-width: 90vw;
        pointer-events: auto;
      }
      
      .subtitle-line {
        padding: 8px 16px;
        border-radius: 8px;
        font-size: 16px;
        line-height: 1.4;
        white-space: pre-wrap;
        word-wrap: break-word;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        transition: opacity 0.2s, transform 0.2s;
        opacity: 0;
        transform: translateY(10px);
      }
      
      .subtitle-line.visible {
        opacity: 1;
        transform: translateY(0);
      }
      
      .subtitle-line.en {
        background: rgba(8, 28, 30, 0.95);
        border: 2px solid #2dd4bf;
        color: #e0f2fe;
      }
      
      .subtitle-line.cz {
        background: rgba(38, 30, 6, 0.95);
        border: 2px solid #fccc15;
        color: #fff8c4;
        font-weight: 600;
      }
      
      .drag-handle {
        position: absolute;
        top: -28px;
        left: 50%;
        transform: translateX(-50%);
        width: 32px;
        height: 24px;
        background: rgba(16, 18, 24, 0.9);
        border: 1px solid #47556b;
        border-radius: 6px;
        cursor: grab;
        display: flex;
        align-items: center;
        justify-content: center;
        pointer-events: auto;
      }
      
      .drag-handle:hover {
        background: rgba(16, 18, 24, 1);
        border-color: #2dd4bf;
      }
      
      .drag-handle:active {
        cursor: grabbing;
      }
      
      .drag-handle svg {
        width: 16px;
        height: 16px;
        stroke: #8b9cb3;
      }
      
      @media (prefers-reduced-motion: reduce) {
        .subtitle-line {
          transition: none;
        }
      }
    `;
    
    shadow.appendChild(style);
    
    // Create subtitle wrapper
    const wrapper = document.createElement('div');
    wrapper.className = 'subtitle-wrapper';
    
    // English subtitle line
    const enLine = document.createElement('div');
    enLine.className = 'subtitle-line en';
    enLine.textContent = '';
    enLine.dataset.lang = 'en';
    
    // Czech subtitle line
    const czLine = document.createElement('div');
    czLine.className = 'subtitle-line cz';
    czLine.textContent = '';
    czLine.dataset.lang = 'cz';
    
    wrapper.appendChild(enLine);
    wrapper.appendChild(czLine);
    
    // Drag handle
    const dragHandle = document.createElement('div');
    dragHandle.className = 'drag-handle';
    dragHandle.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="4" y1="12" x2="20" y2="12"></line>
        <line x1="4" y1="6" x2="20" y2="6"></line>
        <line x1="4" y1="18" x2="20" y2="18"></line>
      </svg>
    `;
    
    // Drag events
    dragHandle.addEventListener('mousedown', startDrag);
    dragHandle.addEventListener('touchstart', startDrag, { passive: false });
    
    shadow.appendChild(dragHandle);
    shadow.appendChild(wrapper);
    
    // Store references
    subtitleContainer = container;
    enSubtitle = enLine;
    czSubtitle = czLine;
    
    // Add to document
    document.body.appendChild(container);
    
    // Load saved position
    loadPosition();
  }
  
  // Drag handling
  function startDrag(e) {
    e.preventDefault();
    e.stopPropagation();
    
    isDragging = true;
    subtitleContainer.classList.add('dragging');
    
    const rect = subtitleContainer.getBoundingClientRect();
    
    if (e.type === 'mousedown') {
      dragOffset.x = e.clientX - rect.left;
      dragOffset.y = e.clientY - rect.top;
    } else if (e.type === 'touchstart') {
      dragOffset.x = e.touches[0].clientX - rect.left;
      dragOffset.y = e.touches[0].clientY - rect.top;
    }
    
    document.addEventListener('mousemove', onDrag);
    document.addEventListener('mouseup', stopDrag);
    document.addEventListener('touchmove', onDrag, { passive: false });
    document.addEventListener('touchend', stopDrag);
  }
  
  function onDrag(e) {
    if (!isDragging) return;
    e.preventDefault();
    
    let clientX, clientY;
    if (e.type === 'mousemove') {
      clientX = e.clientX;
      clientY = e.clientY;
    } else if (e.type === 'touchmove') {
      clientX = e.touches[0].clientX;
      clientY = e.touches[0].clientY;
    }
    
    const x = clientX - dragOffset.x;
    const y = clientY - dragOffset.y;
    
    // Constrain to viewport
    const rect = subtitleContainer.getBoundingClientRect();
    const maxX = window.innerWidth - rect.width;
    const maxY = window.innerHeight - rect.height;
    
    const constrainedX = Math.max(0, Math.min(x, maxX));
    const constrainedY = Math.max(0, Math.min(y, maxY));
    
    subtitleContainer.style.left = constrainedX + 'px';
    subtitleContainer.style.transform = 'none';
    subtitleContainer.style.bottom = 'auto';
    subtitleContainer.style.top = constrainedY + 'px';
  }
  
  function stopDrag() {
    if (!isDragging) return;
    isDragging = false;
    subtitleContainer.classList.remove('dragging');
    
    document.removeEventListener('mousemove', onDrag);
    document.removeEventListener('mouseup', stopDrag);
    document.removeEventListener('touchmove', onDrag);
    document.removeEventListener('touchend', stopDrag);
    
    savePosition();
  }
  
  // Save/load position
  function savePosition() {
    const rect = subtitleContainer.getBoundingClientRect();
    const pos = {
      x: rect.left,
      y: rect.top,
      useTransform: false
    };
    chrome.storage.local.set({ 'myvoicetranslator_subtitle_pos': pos });
  }
  
  function loadPosition() {
    chrome.storage.local.get('myvoicetranslator_subtitle_pos', (result) => {
      if (result.myvoicetranslator_subtitle_pos) {
        const pos = result.myvoicetranslator_subtitle_pos;
        subtitleContainer.style.left = pos.x + 'px';
        subtitleContainer.style.top = pos.y + 'px';
        subtitleContainer.style.transform = 'none';
        subtitleContainer.style.bottom = 'auto';
      }
    });
  }
  
  // Update subtitle text
  function updateSubtitle(lang, text) {
    if (!subtitleContainer) createSubtitleOverlay();
    
    const line = lang === 'en' ? enSubtitle : czSubtitle;
    if (!line) return;
    
    // Don't update if same text
    if (line.textContent === text) return;
    
    line.textContent = text || '';
    
    if (text && text.trim()) {
      line.classList.add('visible');
      isVisible = true;
    } else {
      line.classList.remove('visible');
      // Check if both are empty
      if (!enSubtitle.textContent.trim() && !czSubtitle.textContent.trim()) {
        isVisible = false;
      }
    }
  }
  
  // Clear subtitles
  function clearSubtitles() {
    if (enSubtitle) enSubtitle.textContent = '';
    if (czSubtitle) czSubtitle.textContent = '';
    if (enSubtitle) enSubtitle.classList.remove('visible');
    if (czSubtitle) czSubtitle.classList.remove('visible');
    isVisible = false;
  }
  
  // Listen for messages from background
  chrome.runtime.onMessage.addListener((message) => {
    switch (message.type) {
      case 'transcript':
        const data = message.data;
        if (data.type === 'partial_transcript') {
          updateSubtitle('en', data.english);
          updateSubtitle('cz', 'Translating...');
        } else if (data.type === 'transcript') {
          updateSubtitle('en', data.english);
          updateSubtitle('cz', data.czech);
        }
        break;
      case 'capture_stopped':
        clearSubtitles();
        break;
    }
  });
  
  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', createSubtitleOverlay);
  } else {
    createSubtitleOverlay();
  }
  
  // Cleanup on unload
  window.addEventListener('beforeunload', () => {
    if (subtitleContainer) {
      savePosition();
    }
  });
})();