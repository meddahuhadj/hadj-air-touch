/**
 * HADJ AIR TOUCH PWA - Main Application Controller
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const video = document.getElementById('webcam-video');
  const canvas = document.getElementById('output-canvas');
  const btnStart = document.getElementById('btn-start');
  const btnCalibrate = document.getElementById('btn-calibrate');
  const btnEmergency = document.getElementById('btn-emergency');
  const virtualCursor = document.getElementById('virtual-cursor');
  const toast = document.getElementById('toast-notification');
  const statusDot = document.getElementById('status-dot');
  const statusText = document.getElementById('status-text');
  const fpsCounter = document.getElementById('fps-counter');
  const trackingQuality = document.getElementById('tracking-quality');
  const activeGestureText = document.getElementById('active-gesture');
  const pinchDistText = document.getElementById('pinch-dist');

  // Calibration Modal Elements
  const calibrationModal = document.getElementById('calibration-modal');
  const calibInstruction = document.getElementById('calib-instruction');
  const calibPoints = [
    document.getElementById('calib-tl'),
    document.getElementById('calib-tr'),
    document.getElementById('calib-br'),
    document.getElementById('calib-bl')
  ];

  // Settings Controls
  const sensitivitySlider = document.getElementById('sensitivity-slider');
  const sensitivityVal = document.getElementById('sensitivity-val');

  // Instances
  const tracker = new HandTracker(video, canvas);
  const calibrator = new ScreenCalibrator();
  const gestureEngine = new GestureEngine();

  // App State
  let isRunning = false;
  let isCalibrating = false;
  let currentCalibStep = 0;
  let isPaused = false;

  // Cursor jitter control (mirrors the desktop dead-zone + smoothing)
  let cursorX = null;
  let cursorY = null;
  const CURSOR_SMOOTH_ALPHA = 0.35;
  const CURSOR_DEAD_ZONE_PX = 4;

  // Initialize
  tracker.init((landmarks, fps) => onHandResults(landmarks, fps));

  // Audio Beep Feedback (synthesized Web Audio API)
  const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  function playClickSound(freq = 800, type = 'sine') {
    if (audioCtx.state === 'suspended') audioCtx.resume();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
    gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.1);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.1);
  }

  function showToast(message) {
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2500);
  }

  // Toggle Tracking Start/Stop
  btnStart.addEventListener('click', async () => {
    if (!isRunning) {
      try {
        await tracker.start();
        isRunning = true;
        btnStart.textContent = '⏹ STOP TRACKING';
        btnStart.classList.replace('btn-primary', 'btn-secondary');
        statusDot.className = 'status-dot active';
        statusText.textContent = 'Tracking Active';
        virtualCursor.style.display = 'block';
        showToast('Camera Hand Tracking Started 🖐️');
      } catch (err) {
        console.error("Camera access error:", err);
        let errorMsg = 'Erreur : Impossible d\'accéder à la caméra ⚠️';
        if (err.name === 'NotReadableError' || (err.message && err.message.includes('NotReadableError'))) {
          errorMsg = '📷 Caméra occupée ! Fermez la version Desktop (main.py) ou toute autre appli utilisant la webcam.';
          alert('📷 La webcam est actuellement utilisée par une autre application (ex: HADJ AIR TOUCH version desktop main.py).\n\nVeuillez fermer l\'application desktop puis réessayez.');
        } else if (err.name === 'NotAllowedError') {
          errorMsg = '⚠️ Accès caméra refusé par le navigateur.';
        }
        showToast(errorMsg);
      }
    } else {
      stopTracking();
    }
  });

  function stopTracking() {
    tracker.stop();
    isRunning = false;
    cursorX = null;
    cursorY = null;
    btnStart.textContent = '▶ START TRACKING';
    btnStart.classList.replace('btn-secondary', 'btn-primary');
    statusDot.className = 'status-dot';
    statusText.textContent = 'Ready';
    virtualCursor.style.display = 'none';
    fpsCounter.textContent = '0 FPS';
    trackingQuality.textContent = 'Inactive';
    activeGestureText.textContent = 'None';
    showToast('Tracking Paused ⏸️');
  }

  // Emergency Stop Shortcut (Ctrl+Alt+H)
  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.altKey && e.key.toLowerCase() === 'h') {
      stopTracking();
      showToast('EMERGENCY STOP TRIGGERED (Ctrl+Alt+H) 🚨');
    }
  });

  if (btnEmergency) {
    btnEmergency.addEventListener('click', () => {
      stopTracking();
      showToast('EMERGENCY STOP 🚨');
    });
  }

  // Sensitivity Adjustment
  sensitivitySlider.addEventListener('input', (e) => {
    const val = e.target.value;
    sensitivityVal.textContent = val;
    gestureEngine.setSensitivity(parseFloat(val));
  });

  // Calibration Trigger
  btnCalibrate.addEventListener('click', () => {
    if (!isRunning) {
      showToast('Please start tracking first before calibrating!');
      return;
    }
    startCalibrationWorkflow();
  });

  function startCalibrationWorkflow() {
    isCalibrating = true;
    currentCalibStep = 0;
    calibrator.clear();
    calibrator.setTargetPoints(window.innerWidth, window.innerHeight);

    calibrationModal.classList.add('active');
    updateCalibUI();
    showToast('4-Point Screen Calibration Started 🎯');
  }

  function updateCalibUI() {
    calibPoints.forEach((pt, idx) => {
      pt.classList.remove('active', 'done');
      if (idx < currentCalibStep) pt.classList.add('done');
      if (idx === currentCalibStep) pt.classList.add('active');
    });

    const labels = ['Top-Left Corner ↖️', 'Top-Right Corner ↗️', 'Bottom-Right Corner ↘️', 'Bottom-Left Corner ↙️'];
    if (currentCalibStep < 4) {
      calibInstruction.textContent = `Point finger at the ${labels[currentCalibStep]} and PINCH 🤏 to register.`;
    } else {
      calibInstruction.textContent = 'Calculating Screen Homography Matrix...';
    }
  }

  // Handle Hand Results Callback
  function onHandResults(landmarks, fps) {
    fpsCounter.textContent = `${fps} FPS`;

    if (!landmarks) {
      trackingQuality.textContent = 'Searching Hand...';
      activeGestureText.textContent = 'None';
      return;
    }

    trackingQuality.textContent = 'High Confidence 🟢';

    // Process Gestures first so a wave can resume a paused session
    const gesture = gestureEngine.processLandmarks(landmarks);
    activeGestureText.textContent = gesture.gesture;
    pinchDistText.textContent = gesture.pinchDist;

    if (isPaused) {
      if (gesture.action === 'WAVE') {
        isPaused = false;
        statusDot.className = 'status-dot active';
        statusText.textContent = 'Tracking Active';
        showToast('Resumed ▶️');
      }
      return;
    }

    // Index Tip position (Landmark 8) for virtual air mouse
    const indexTip = landmarks[8];
    // Invert X because camera is mirrored
    const camX = 1.0 - indexTip.x;
    const camY = indexTip.y;

    // Transform using 4-point calibrator or direct viewport mapping
    const mapped = calibrator.transformPoint(camX, camY, window.innerWidth, window.innerHeight);

    // Jitter control: ignore sub-threshold drift, then ease toward the target.
    // The raw `mapped` point stays available for calibration/click logic.
    if (cursorX === null) {
      cursorX = mapped.x;
      cursorY = mapped.y;
    } else {
      const dx = mapped.x - cursorX;
      const dy = mapped.y - cursorY;
      if (Math.hypot(dx, dy) > CURSOR_DEAD_ZONE_PX) {
        cursorX += dx * CURSOR_SMOOTH_ALPHA;
        cursorY += dy * CURSOR_SMOOTH_ALPHA;
      }
    }

    // Update Virtual Cursor Position
    virtualCursor.style.left = `${cursorX}px`;
    virtualCursor.style.top = `${cursorY}px`;

    // Visual Cursor State
    if (gesture.pinched) {
      virtualCursor.className = 'pinched';
    } else if (gesture.grabbed) {
      virtualCursor.className = 'grabbed';
    } else {
      virtualCursor.className = '';
    }

    // Process Actions
    if (gesture.action === 'WAVE') {
      isPaused = true;
      statusDot.className = 'status-dot';
      statusText.textContent = 'Paused ⏸️ (wave to resume)';
      showToast('Paused ⏸️ (wave to resume)');
    } else if (gesture.action === 'THUMBS_UP') {
      playClickSound(600);
      showToast('Thumbs Up 👍');
    } else if (gesture.action === 'CLICK') {
      playClickSound(800);
      showToast('Pinch Click 🤏');
      simulateVirtualClick(mapped.x, mapped.y);

      if (isCalibrating && currentCalibStep < 4) {
        calibrator.addCameraPoint(camX, camY);
        currentCalibStep++;
        playClickSound(1200, 'triangle');
        if (currentCalibStep === 4) {
          const success = calibrator.computeHomography();
          isCalibrating = false;
          calibrationModal.classList.remove('active');
          showToast(success ? 'Calibration Successful! 🎉' : 'Calibration Failed. Using default mapping.');
        } else {
          updateCalibUI();
        }
      }
    } else if (gesture.action === 'DOUBLE_CLICK') {
      playClickSound(1000);
      showToast('Double Pinch Click 🤏🤏');
    }
  }

  // Simulate element click at coordinates (Web PWA Interaction)
  function simulateVirtualClick(x, y) {
    const el = document.elementFromPoint(x, y);
    if (el) {
      el.dispatchEvent(new MouseEvent('click', {
        bubbles: true,
        cancelable: true,
        clientX: x,
        clientY: y
      }));
    }
  }
});
