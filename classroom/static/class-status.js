const classroom = document.querySelector('[data-class-status]');

async function checkClass() {
  try {
    const response = await fetch(classroom.dataset.classStatus, { cache: 'no-store' });
    if (response.status === 410) {
      const page = new URL(window.location.href);
      page.searchParams.set('lang', document.documentElement.lang);
      // A fragment destination can keep the browser on the open-class document.
      page.hash = '';
      window.location.replace(page);
      return;
    }
    if (classroom.dataset.sitesSwapped === 'false' && response.headers.get('X-Sites-Swapped') === 'true') {
      const page = new URL(window.location.href);
      page.searchParams.set('notice', 'swapped');
      page.hash = 'current-site';
      window.location.replace(page);
      return;
    }
  } catch {
    // Retry after a temporary network interruption.
  }
  window.setTimeout(checkClass, 2000);
}

checkClass();
