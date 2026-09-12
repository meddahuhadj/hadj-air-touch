/**
 * Real-time Hand Gesture Recognition Engine
 */
class GestureEngine {
  constructor() {
    this.pinchThreshold = 0.06;
    this.isPinched = false;
    this.lastPinchTime = 0;
    this.pinchCount = 0;
    this.isGrabbed = false;
    this.historyX = [];
    this.historyY = [];
    this.waveHistory = [];
  }

  setSensitivity(sensitivityVal) {
    // Convert 1..10 scale to distance threshold
    this.pinchThreshold = 0.03 + (sensitivityVal / 10) * 0.05;
  }

  processLandmarks(landmarks) {
    if (!landmarks || landmarks.length < 21) {
      return { action: 'NONE', gesture: 'None', pinched: false, grabbed: false };
    }

    const thumbTip = landmarks[4];
    const indexTip = landmarks[8];
    const middleTip = landmarks[12];
    const ringTip = landmarks[16];
    const pinkyTip = landmarks[20];
    const wrist = landmarks[0];

    // 1. Calculate Euclidean distance between Thumb Tip and Index Tip
    const pinchDist = Math.hypot(thumbTip.x - indexTip.x, thumbTip.y - indexTip.y);

    const now = performance.now();
    let action = 'NONE';
    let gestureName = 'Pointer Mode';

    // 2. Check Pinch state
    let currentPinch = pinchDist < this.pinchThreshold;

    if (currentPinch && !this.isPinched) {
      // Pinch started
      this.isPinched = true;
      if (now - this.lastPinchTime < 350) {
        action = 'DOUBLE_CLICK';
        gestureName = 'Double Pinch 🤏🤏';
      } else {
        action = 'CLICK';
        gestureName = 'Pinch Click 🤏';
      }
      this.lastPinchTime = now;
    } else if (!currentPinch && this.isPinched) {
      // Pinch released
      this.isPinched = false;
      action = 'RELEASE';
    } else if (currentPinch && this.isPinched) {
      action = 'HOLD';
      gestureName = 'Pinch Hold 🤏';
    }

    // 3. Check Grab (Fist) / Thumbs-Up state
    const dMiddle = Math.hypot(middleTip.x - wrist.x, middleTip.y - wrist.y);
    const dRing = Math.hypot(ringTip.x - wrist.x, ringTip.y - wrist.y);
    const dPinky = Math.hypot(pinkyTip.x - wrist.x, pinkyTip.y - wrist.y);
    const avgDist = (dMiddle + dRing + dPinky) / 3;

    if (avgDist < 0.22 && !currentPinch) {
      const dThumb = Math.hypot(thumbTip.x - wrist.x, thumbTip.y - wrist.y);
      if (dThumb > 0.35) {
        // Thumb clearly stuck out past folded fingers -> Thumbs Up
        this.isGrabbed = false;
        if (action === 'NONE') {
          action = 'THUMBS_UP';
          gestureName = 'Thumbs Up 👍';
        }
      } else {
        this.isGrabbed = true;
        gestureName = 'Fist / Grab ✊';
        if (action === 'NONE') action = 'GRAB';
      }
    } else {
      this.isGrabbed = false;
    }

    // 4. Swipe detection via wrist position history
    this.historyX.push(wrist.x);
    this.historyY.push(wrist.y);
    if (this.historyX.length > 8) {
      this.historyX.shift();
      this.historyY.shift();
      const dx = this.historyX[this.historyX.length - 1] - this.historyX[0];
      const dy = this.historyY[this.historyY.length - 1] - this.historyY[0];
      if (Math.abs(dx) > 0.35 && action === 'NONE') {
        action = dx > 0 ? 'SWIPE_RIGHT' : 'SWIPE_LEFT';
        gestureName = dx > 0 ? 'Swipe Right ➡️' : 'Swipe Left ⬅️';
      }
    }

    // 5. Wave detection (rapid horizontal oscillation of the wrist)
    if (action === 'NONE') {
      const nowT = performance.now();
      this.waveHistory.push({ t: nowT, x: wrist.x });
      this.waveHistory = this.waveHistory.filter((p) => nowT - p.t < 700);
      if (this.waveHistory.length >= 6) {
        let reversals = 0;
        for (let i = 1; i < this.waveHistory.length - 1; i++) {
          const d1 = this.waveHistory[i].x - this.waveHistory[i - 1].x;
          const d2 = this.waveHistory[i + 1].x - this.waveHistory[i].x;
          if (d1 > 0.02 && d2 < -0.02) reversals++;
          else if (d1 < -0.02 && d2 > 0.02) reversals++;
        }
        const xs = this.waveHistory.map((p) => p.x);
        const span = Math.max(...xs) - Math.min(...xs);
        if (reversals >= 2 && span > 0.15) {
          action = 'WAVE';
          gestureName = 'Wave 👋';
          this.waveHistory = [];
        }
      }
    }

    return {
      action: action,
      gesture: gestureName,
      pinched: this.isPinched,
      grabbed: this.isGrabbed,
      pinchDist: pinchDist.toFixed(3)
    };
  }
}
