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

    // 3. Check Grab (Fist) state
    const dMiddle = Math.hypot(middleTip.x - wrist.x, middleTip.y - wrist.y);
    const dRing = Math.hypot(ringTip.x - wrist.x, ringTip.y - wrist.y);
    const dPinky = Math.hypot(pinkyTip.x - wrist.x, pinkyTip.y - wrist.y);
    const avgDist = (dMiddle + dRing + dPinky) / 3;

    if (avgDist < 0.22 && !currentPinch) {
      this.isGrabbed = true;
      gestureName = 'Fist / Grab ✊';
      if (action === 'NONE') action = 'GRAB';
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

    return {
      action: action,
      gesture: gestureName,
      pinched: this.isPinched,
      grabbed: this.isGrabbed,
      pinchDist: pinchDist.toFixed(3)
    };
  }
}
