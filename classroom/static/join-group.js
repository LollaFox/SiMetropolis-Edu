function joinBrowserKey() {
  return new Promise((resolve, reject) => {
    const open = indexedDB.open('long-valley-classroom', 1);
    open.onupgradeneeded = () => open.result.createObjectStore('browser');
    open.onerror = () => reject(open.error);
    open.onsuccess = () => {
      const database = open.result;
      // A write transaction makes two tabs opening together share the same key.
      const transaction = database.transaction('browser', 'readwrite');
      const store = transaction.objectStore('browser');
      const existing = store.get('key');
      let key;
      existing.onsuccess = () => {
        key = existing.result;
        if (key) return;
        const random = crypto.getRandomValues(new Uint8Array(16));
        key = Array.from(random, byte => byte.toString(16).padStart(2, '0')).join('');
        store.add(key, 'key');
      };
      transaction.oncomplete = () => resolve(key);
      transaction.onabort = () => reject(transaction.error);
      database.close();
    };
  });
}

const joinChooser = document.querySelector('[data-join-chooser]');
const joinCheck = document.querySelector('[data-join-check]');

async function openJoinPage() {
  const key = await joinBrowserKey();
  const response = await fetch(joinChooser.dataset.resumePath, {
    method: 'POST', body: new URLSearchParams({ browser_key: key }),
  });
  if (response.status === 204) {
    for (const input of joinChooser.querySelectorAll('input[name="browser_key"]')) input.value = key;
    joinCheck.hidden = true;
    joinChooser.hidden = false;
    if (window.location.hash === '#rejoin-group') document.getElementById('rejoin-group')?.scrollIntoView();
    return;
  }
  if (response.status === 200) {
    // Verify the session cookie was accepted before reloading the join URL.
    const status = await fetch(`${window.location.pathname}/status`);
    if (status.status !== 204 && status.status !== 410) throw new Error('Could not restore the group session');
  } else if (response.status !== 410) {
    throw new Error('Could not check the site assignment');
  }
  window.location.reload();
}

openJoinPage().catch(() => {
  joinCheck.hidden = true;
  document.querySelector('[data-join-check-error]').hidden = false;
});
