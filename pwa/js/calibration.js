/**
 * 4-Point Homography Matrix Calibration Solver for Web Browser
 */
class ScreenCalibrator {
  constructor() {
    this.isCalibrated = false;
    this.srcPoints = []; // 4 Camera points [(x0,y0), (x1,y1), (x2,y2), (x3,y3)]
    this.dstPoints = []; // 4 Target screen points [(0,0), (1,0), (1,1), (0,1)]
    this.H = null; // 3x3 Homography Transformation Matrix
  }

  setTargetPoints(width, height) {
    this.dstPoints = [
      [0.05 * width, 0.05 * height],   // Top-Left
      [0.95 * width, 0.05 * height],   // Top-Right
      [0.95 * width, 0.95 * height],   // Bottom-Right
      [0.05 * width, 0.95 * height]    // Bottom-Left
    ];
  }

  addCameraPoint(x, y) {
    this.srcPoints.push([x, y]);
  }

  clear() {
    this.srcPoints = [];
    this.isCalibrated = false;
    this.H = null;
  }

  computeHomography() {
    if (this.srcPoints.length < 4 || this.dstPoints.length < 4) {
      console.warn("Insufficient points for Homography computation");
      return false;
    }

    // Solve Direct Linear Transformation (DLT) for 3x3 Homography Matrix
    const matrixA = [];
    for (let i = 0; i < 4; i++) {
      const [x, y] = this.srcPoints[i];
      const [u, v] = this.dstPoints[i];
      matrixA.push([-x, -y, -1, 0, 0, 0, x * u, y * u, u]);
      matrixA.push([0, 0, 0, -x, -y, -1, x * v, y * v, v]);
    }

    // Gaussian Elimination with partial pivoting to solve A*h = 0 (h_9 = 1)
    const h = this.solveGaussian(matrixA);
    if (!h) {
      this.isCalibrated = false;
      return false;
    }

    this.H = [
      [h[0], h[1], h[2]],
      [h[3], h[4], h[5]],
      [h[6], h[7], h[8]]
    ];
    this.isCalibrated = true;
    return true;
  }

  solveGaussian(A) {
    const N = 8;
    const M = [];
    for (let i = 0; i < 8; i++) {
      M[i] = A[i].slice(0, 8);
      M[i].push(-A[i][8]); // RHS
    }

    for (let i = 0; i < N; i++) {
      let maxRow = i;
      for (let k = i + 1; k < N; k++) {
        if (Math.abs(M[k][i]) > Math.abs(M[maxRow][i])) maxRow = k;
      }
      const temp = M[i]; M[i] = M[maxRow]; M[maxRow] = temp;

      if (Math.abs(M[i][i]) < 1e-8) return null;

      for (let k = i + 1; k < N; k++) {
        const factor = M[k][i] / M[i][i];
        for (let j = i; j <= N; j++) {
          M[k][j] -= factor * M[i][j];
        }
      }
    }

    const x = new Array(N);
    for (let i = N - 1; i >= 0; i--) {
      let sum = 0;
      for (let j = i + 1; j < N; j++) {
        sum += M[i][j] * x[j];
      }
      x[i] = (M[i][N] - sum) / M[i][i];
    }

    x.push(1.0); // Normalize h9 = 1
    return x;
  }

  transformPoint(camX, camY, screenWidth, screenHeight) {
    if (!this.isCalibrated || !this.H) {
      // Default linear mapping if uncalibrated
      return {
        x: camX * screenWidth,
        y: camY * screenHeight
      };
    }

    const H = this.H;
    const denom = H[2][0] * camX + H[2][1] * camY + H[2][2];
    if (Math.abs(denom) < 1e-6) return { x: camX * screenWidth, y: camY * screenHeight };

    const targetX = (H[0][0] * camX + H[0][1] * camY + H[0][2]) / denom;
    const targetY = (H[1][0] * camX + H[1][1] * camY + H[1][2]) / denom;

    return {
      x: Math.max(0, Math.min(screenWidth, targetX)),
      y: Math.max(0, Math.min(screenHeight, targetY))
    };
  }
}
