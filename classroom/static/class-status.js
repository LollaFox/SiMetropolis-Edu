const classroom = document.querySelector('[data-class-status]');
const comparisons = classroom.querySelector('[data-comparison-feed]');
const statusUrl = comparisons ? comparisons.dataset.comparisonFeed : classroom.dataset.classStatus;
const countdown = classroom.querySelector('[data-remaining-ms]');
const countdownDeadline = countdown ? watchCountdown(countdown) : 0;

function watchCountdown(timer) {
  const navigation = performance.getEntriesByType('navigation')[0];
  const deadline = (navigation?.responseStart || performance.now()) + Number(timer.dataset.remainingMs);

  function update() {
    const remaining = Math.max(0, deadline - performance.now());
    const seconds = Math.ceil(remaining / 1000);
    const minutesText = String(Math.floor(seconds / 60)).padStart(2, '0');
    const secondsText = String(seconds % 60).padStart(2, '0');
    timer.textContent = minutesText + ':' + secondsText;
    if (remaining > 0) window.setTimeout(update, remaining % 1000 || 1000);
  }

  update();
  return deadline;
}

function leaveClass(status) {
  const page = new URL(status === 403 ? '/' : window.location.href, window.location.origin);
  page.searchParams.set('lang', document.documentElement.lang);
  // A fragment destination can keep the browser on the open-class document.
  page.hash = '';
  window.location.replace(page);
}

async function checkClass() {
  try {
    const response = await fetch(statusUrl, { cache: 'no-store' });
    if (response.status === 403 || response.status === 410) {
      classroom.replaceChildren();
      leaveClass(response.status);
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
  const untilDeadline = countdownDeadline - performance.now();
  window.setTimeout(checkClass, untilDeadline > 0 ? Math.min(untilDeadline, 2000) : 2000);
}

const ASSIGNMENT_TIMEOUT_MS = 10000;
const FORM_NAVIGATION_GRACE_MS = 10000;

function watchAssignment(notice) {
  const site = classroom.querySelector('[data-group-site]');
  const form = site.querySelector('#crossing-design');
  const controls = [...form.querySelectorAll('select')];
  const swapWait = Number(site.dataset.swapWait) * 1000;
  let active;
  let retry;
  let handoff;
  let firstReveal = true;
  let navigating = false;
  let submitting = false;

  function showNotice(message) {
    site.hidden = true;
    notice.textContent = message;
    notice.hidden = false;
  }

  function pause() {
    active?.abort();
    window.clearTimeout(retry);
    showNotice(notice.dataset.siteCheck);
  }

  function navigateToPartnerSite() {
    window.clearTimeout(handoff);
    handoff = undefined;
    const page = new URL(window.location.href);
    page.searchParams.set('lang', document.documentElement.lang);
    page.searchParams.set('notice', 'swapped');
    page.hash = 'current-site';
    if (page.search === window.location.search) window.location.reload();
    else window.location.replace(page);
  }

  function openPartnerSite() {
    navigating = true;
    showNotice(notice.dataset.siteOpening);
    // Let a pending Share send its original snapshot. Bound the wait if cancellation goes unreported.
    if (submitting) handoff = window.setTimeout(navigateToPartnerSite, FORM_NAVIGATION_GRACE_MS);
    else navigateToPartnerSite();
  }

  async function checkSite(waitForSwap) {
    const controller = new AbortController();
    active = controller;
    // Give the long poll the full server wait plus time for the response to arrive.
    const deadline = window.setTimeout(() => {
      if (!controller.signal.aborted) connect();
    }, ASSIGNMENT_TIMEOUT_MS + (waitForSwap ? swapWait : 0));
    try {
      const response = await fetch(waitForSwap ? statusUrl + '?wait=swap' : statusUrl, {
        cache: 'no-store', signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (response.status === 403 || response.status === 410) {
        navigating = true;
        showNotice(notice.dataset.siteCheck);
        leaveClass(response.status);
        return;
      }
      const assignedSite = response.headers.get('X-Current-Site');
      if (response.status === 204 && (assignedSite === 'A' || assignedSite === 'B')) {
        if (assignedSite === site.dataset.groupSite) {
          if (site.hidden) restoreDraft();
          site.hidden = false;
          notice.hidden = true;
          if (firstReveal) {
            firstReveal = false;
            // Form redirects can point to an anchor that was hidden during page load.
            document.getElementById(window.location.hash.slice(1))?.scrollIntoView();
          }
          if (swapWait) checkSite(true);
          else retry = window.setTimeout(() => checkSite(false), 2000);
        } else {
          openPartnerSite();
        }
        return;
      }
    } catch {
      if (controller.signal.aborted) return;
    } finally {
      window.clearTimeout(deadline);
    }
    pause();
    retry = window.setTimeout(connect, 2000);
  }

  function connect() {
    if (navigating) return;
    pause();
    if (!document.hidden && navigator.onLine) checkSite(false);
  }

  function restoreDraft() {
    // A history entry can load a fresh document for the other site after a swap.
    const draft = history.state?.crossingDraft;
    if (draft?.classStatus !== statusUrl || draft.site !== site.dataset.groupSite) return;
    for (const control of controls) {
      const value = draft.choices?.[control.name];
      if ([...control.options].some(option => option.value === value)) control.value = value;
    }
  }

  form.addEventListener('change', () => {
    history.replaceState({
      ...history.state,
      crossingDraft: {
        classStatus: statusUrl,
        site: site.dataset.groupSite,
        choices: Object.fromEntries(controls.map(control => [control.name, control.value])),
      },
    }, '');
  });

  form.addEventListener('submit', () => { submitting = true; });
  window.navigation?.addEventListener('navigate', event => {
    if (!event.formData) return;
    event.signal.addEventListener('abort', () => {
      submitting = false;
      if (handoff !== undefined) navigateToPartnerSite();
    }, { once: true });
  });
  document.addEventListener('visibilitychange', connect);
  window.addEventListener('offline', connect);
  window.addEventListener('online', connect);
  window.addEventListener('pagehide', () => {
    window.clearTimeout(handoff);
    handoff = undefined;
    pause();
  });
  window.addEventListener('pageshow', event => {
    if (!event.persisted) return;
    navigating = false;
    submitting = false;
    connect();
  });
  connect();
}

const siteNotice = classroom.querySelector('[data-site-check]');
if (siteNotice) watchAssignment(siteNotice);
else checkClass();
