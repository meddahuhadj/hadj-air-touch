/**
 * MediaPipe Camera & Hand Tracker Wrapper
 */
class HandTracker {
  constructor(videoElement, canvasElement) {
    this.videoElement = videoElement;
    this.canvasElement = canvasElement;
    this.ctx = canvasElement.getContext('2d');
    this.hands = null;
    this.camera = null;
    this.isTracking = false;
    this.onResultsCallback = null;
    this.fps = 0;
    this.lastFrameTime = performance.now();
    this.frameCount = 0;
  }

  async init(onResults) {
    this.onResultsCallback = onResults;

    // Resize canvas to match video stream dimensions
    this.videoElement.addEventListener('loadedmetadata', () => {
      this.canvasElement.width = this.videoElement.videoWidth;
      this.canvasElement.height = this.videoElement.videoHeight;
    });

    if (window.Hands) {
      this.hands = new window.Hands({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`
      });

      this.hands.setOptions({
        maxNumHands: 1,
        modelComplexity: 1,
        minDetectionConfidence: 0.7,
        minTrackingConfidence: 0.6
      });

      this.hands.onResults((results) => this.handleResults(results));

      if (window.Camera) {
        this.camera = new window.Camera(this.videoElement, {
          onFrame: async () => {
            if (this.isTracking && this.hands) {
              await this.hands.send({ image: this.videoElement });
            }
          },
          width: 1280,
          height: 720
        });
      }
    } else {
      console.warn("MediaPipe Hands library not loaded from CDN.");
    }
  }

  async start() {
    this.isTracking = true;
    try {
      if (this.camera) {
        await this.camera.start();
      } else {
        await this.startNativeWebRTC();
      }
    } catch (err) {
      console.warn("MediaPipe camera helper failed, trying native getUserMedia...", err);
      try {
        await this.startNativeWebRTC();
      } catch (nativeErr) {
        this.isTracking = false;
        throw nativeErr;
      }
    }
  }

  async startNativeWebRTC() {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' }
    });
    this.videoElement.srcObject = stream;
    await this.videoElement.play();
    this.requestFrameLoop();
  }

  stop() {
    this.isTracking = false;
    if (this.videoElement && this.videoElement.srcObject) {
      const tracks = this.videoElement.srcObject.getTracks();
      tracks.forEach(track => track.stop());
      this.videoElement.srcObject = null;
    }
  }

  requestFrameLoop() {
    if (!this.isTracking) return;
    if (this.hands && this.videoElement.readyState >= 2) {
      this.hands.send({ image: this.videoElement }).catch(console.error);
    }
    requestAnimationFrame(() => this.requestFrameLoop());
  }

  handleResults(results) {
    // Compute FPS
    const now = performance.now();
    this.frameCount++;
    if (now - this.lastFrameTime >= 1000) {
      this.fps = this.frameCount;
      this.frameCount = 0;
      this.lastFrameTime = now;
    }

    // Clear previous overlay
    this.ctx.clearRect(0, 0, this.canvasElement.width, this.canvasElement.height);

    let landmarks = null;
    if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
      landmarks = results.multiHandLandmarks[0];
      this.drawHandMesh(landmarks);
    }

    if (this.onResultsCallback) {
      this.onResultsCallback(landmarks, this.fps);
    }
  }

  drawHandMesh(landmarks) {
    const w = this.canvasElement.width;
    const h = this.canvasElement.height;
    const ctx = this.ctx;

    // Connections between 21 MediaPipe hand landmarks
    const connections = [
      [0, 1], [1, 2], [2, 3], [3, 4],       // Thumb
      [0, 5], [5, 6], [6, 7], [7, 8],       // Index
      [5, 9], [9, 10], [10, 11], [11, 12],  // Middle
      [9, 13], [13, 14], [14, 15], [15, 16],// Ring
      [13, 17], [17, 18], [18, 19], [19, 20],// Pinky
      [0, 17]                               // Palm base
    ];

    // Draw skeletal connection lines
    ctx.strokeStyle = '#00e5ff';
    ctx.lineWidth = 3;
    ctx.shadowColor = '#00e5ff';
    ctx.shadowBlur = 10;

    for (const [start, end] of connections) {
      const p1 = landmarks[start];
      const p2 = landmarks[end];
      ctx.beginPath();
      ctx.moveTo(p1.x * w, p1.y * h);
      ctx.lineTo(p2.x * w, p2.y * h);
      ctx.stroke();
    }
    ctx.shadowBlur = 0;

    // Draw landmark joint points
    for (let i = 0; i < landmarks.length; i++) {
      const lm = landmarks[i];
      ctx.fillStyle = (i === 8 || i === 4) ? '#00e676' : '#ffffff';
      ctx.beginPath();
      ctx.arc(lm.x * w, lm.y * h, (i === 8 || i === 4) ? 7 : 4, 0, 2 * Math.PI);
      ctx.fill();
    }
  }
}
