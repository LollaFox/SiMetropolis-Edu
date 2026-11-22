(() => {
  let retry;
  let loading = false;

  function loadStatus() {
    if (loading || !navigator.onLine) return;
    window.clearTimeout(retry);
    loading = true;
    const script = document.createElement('script');
    script.src = '/class-status.js';
    script.onload = () => window.removeEventListener('online', loadStatus);
    script.onerror = () => {
      script.remove();
      loading = false;
      retry = window.setTimeout(loadStatus, 2000);
    };
    document.head.append(script);
  }

  window.addEventListener('online', loadStatus);
  loadStatus();
})();
