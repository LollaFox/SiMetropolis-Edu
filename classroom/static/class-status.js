const classroom = document.querySelector('[data-class-status]');

async function checkClass() {
  try {
    const response = await fetch(classroom.dataset.classStatus, { cache: 'no-store' });
    if (response.status === 410) {
      const page = new URL(window.location.href);
      page.searchParams.set('lang', document.documentElement.lang);
      window.location.replace(page);
      return;
    }
  } catch {
    // Retry after a temporary network interruption.
  }
  window.setTimeout(checkClass, 2000);
}

checkClass();
