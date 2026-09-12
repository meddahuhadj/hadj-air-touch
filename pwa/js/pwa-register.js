// Service Worker and PWA Install Prompt Manager
let deferredInstallPrompt = null;

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredInstallPrompt = e;
  const installBtn = document.getElementById('btn-pwa-install');
  if (installBtn) {
    installBtn.style.display = 'inline-flex';
  }
});

function initPWA() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('./sw.js')
      .then((registration) => {
        console.log('[PWA] Service Worker registered with scope:', registration.scope);
      })
      .catch((error) => {
        console.warn('[PWA] Service Worker registration failed:', error);
      });
  }

  const installBtn = document.getElementById('btn-pwa-install');
  if (installBtn) {
    installBtn.addEventListener('click', async () => {
      if (!deferredInstallPrompt) return;
      deferredInstallPrompt.prompt();
      const { outcome } = await deferredInstallPrompt.userChoice;
      console.log('[PWA] User response to install prompt:', outcome);
      deferredInstallPrompt = null;
      installBtn.style.display = 'none';
    });
  }
}

document.addEventListener('DOMContentLoaded', initPWA);
