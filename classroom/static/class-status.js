const classroom = document.querySelector('[data-class-status]');
const comparisons = classroom.querySelector('[data-comparison-feed]');
const statusUrl = comparisons ? comparisons.dataset.comparisonFeed : classroom.dataset.classStatus;

async function checkClass() {
  try {
    const response = await fetch(statusUrl, { cache: 'no-store' });
    if (response.status === 403 || response.status === 410) {
      classroom.replaceChildren();
      const page = new URL(response.status === 403 ? '/' : window.location.href, window.location.origin);
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
    if (comparisons && response.ok) {
      const choices = document.createElement('template');
      choices.innerHTML = await response.text();
      // Shares only append during a class. Keep existing links in place so focus stays put.
      comparisons.append(...Array.from(choices.content.children).slice(comparisons.childElementCount));
    }
  } catch {
    // Retry after a temporary network interruption.
  }
  window.setTimeout(checkClass, 2000);
}

checkClass();
