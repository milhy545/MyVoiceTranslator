/**
 * MyVoiceTranslator Offscreen Document - Audio Processing
 * Uses AudioWorklet for efficient real-time resampling
 */

// AudioWorklet processor for resampling
const resampleProcessorCode = `
class ResampleProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.targetSampleRate = options.processorOptions.targetSampleRate || 16000;
    this.sourceSampleRate = sampleRate;
    this.ratio = this.sourceSampleRate / this.targetSampleRate;
    this.buffer = new Float32Array(4096);
    this.bufferIndex = 0;
    this.outputIndex = 0;
    
    this.port.onmessage = (event) => {
      if (event.data === 'flush') {
        this.flush();
      }
    };
  }
  
  process(inputs, outputs) {
    const input = inputs[0];
    const output = outputs[0];
    
    if (!input || input.length === 0) return true;
    
    // Mix all channels to mono
    const channelCount = input[0].length;
    const inputData = input[0];
    
    for (let channel = 1; channel < channelCount; channel++) {
      const chData = input[channel];
      for (let i = 0; i < inputData.length; i++) {
        inputData[i] += chData[i];
      }
    }
    
    // Normalize
    for (let i = 0; i < inputData.length; i++) {
      inputData[i] /= channelCount;
    }
    
    // Resample and send to main thread
    this.resampleAndSend(inputData);
    
    return true;
  }
  
  resampleAndSend(inputData) {
    const outputLength = Math.ceil(inputData.length / this.ratio);
    const resampled = new Float32Array(outputLength);
    
    for (let i = 0; i < outputLength; i++) {
      const srcIndex = i * this.ratio;
      const srcIndexFloor = Math.floor(srcIndex);
      const srcIndexCeil = Math.min(srcIndexFloor + 1, inputData.length - 1);
      const frac = srcIndex - srcIndexFloor;
      resampled[i] = inputData[srcIndexFloor] * (1 - frac) + inputData[srcIndexCeil] * frac;
    }
    
    // Send to main thread via port
    this.port.postMessage({
      type: 'audio_chunk',
      data: resampled.buffer
    }, [resampled.buffer]);
  }
  
  flush() {
    // Send any remaining buffered data
    this.port.postMessage({ type: 'flush_complete' });
  }
}

registerProcessor('resample-processor', ResampleProcessor);
`;

// Create blob URL for AudioWorklet
const processorBlob = new Blob([resampleProcessorCode], { type: 'application/javascript' });
const processorUrl = URL.createObjectURL(processorBlob);

// Initialize audio context and worklet
let audioContext = null;
let mediaStreamSource = null;
let workletNode = null;
let websocket = null;

// Message handler from background script
chrome.runtime.onMessage.addListener(async (message, sender, sendResponse) => {
  switch (message.type) {
    case 'init_audio':
      try {
        // Receive media stream from background
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            mandatory: {
              chromeMediaSource: 'tab',
              chromeMediaSourceId: message.streamId
            }
          }
        });
        
        audioContext = new AudioContext({ sampleRate: 48000 });
        await audioContext.audioWorklet.addModule(processorUrl);
        
        mediaStreamSource = audioContext.createMediaStreamSource(stream);
        workletNode = new AudioWorkletNode(audioContext, 'resample-processor', {
          processorOptions: { targetSampleRate: 16000 }
        });
        
        workletNode.port.onmessage = (event) => {
          if (event.data.type === 'audio_chunk' && websocket && websocket.readyState === WebSocket.OPEN) {
            websocket.send(event.data.data);
          }
        };
        
        mediaStreamSource.connect(workletNode);
        workletNode.connect(audioContext.destination);
        
        sendResponse({ success: true });
      } catch (error) {
        sendResponse({ success: false, error: error.message });
      }
      return true;
      
    case 'connect_websocket':
      connectWebSocket(message.url);
      sendResponse({ success: true });
      return true;
      
    case 'stop_audio':
      if (workletNode) {
        workletNode.disconnect();
        workletNode = null;
      }
      if (mediaStreamSource) {
        mediaStreamSource.disconnect();
        mediaStreamSource = null;
      }
      if (audioContext) {
        await audioContext.close();
        audioContext = null;
      }
      sendResponse({ success: true });
      return true;
  }
});

async function connectWebSocket(url) {
  websocket = new WebSocket(url);
  websocket.binaryType = 'arraybuffer';
  
  websocket.onopen = () => {
    console.log('[Offscreen] WebSocket connected');
  };
  
  websocket.onclose = () => {
    console.log('[Offscreen] WebSocket closed');
  };
  
  websocket.onerror = (error) => {
    console.error('[Offscreen] WebSocket error:', error);
  };
}

// Keep alive
setInterval(() => {
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    websocket.send(JSON.stringify({ type: 'ping' }));
  }
}, 30000);

console.log('[MyVoiceTranslator] Offscreen document loaded');