const form = document.querySelector('.signin-form');
const credential = form.elements.namedItem('credential');
const error = document.getElementById('cred-error');
const submit = form.querySelector('button[type="submit"]');
const languageSwitch = document.querySelector('.panel-top .lang');
const languages = languageSwitch.querySelectorAll('a[lang]');
const translations = JSON.parse(form.dataset.copy);

credential.addEventListener('input', () => {
  form.dataset.error = '';
  credential.setAttribute('aria-invalid', 'false');
  error.textContent = '';
});

for (const link of languages) {
  link.addEventListener('click', event => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();

    // Translate the current form in place so the draft stays in the password field.
    const copy = translations[link.lang];
    document.documentElement.lang = link.lang;
    document.title = `${copy.sign_in} · SiMetropolis Edu`;
    languageSwitch.setAttribute('aria-label', copy.language);
    for (const option of languages) {
      option.setAttribute('aria-current', String(option === link));
    }
    credential.labels[0].textContent = copy.credential;
    submit.textContent = copy.sign_in;
    error.textContent = copy[form.dataset.error] || '';

    const action = new URL(form.action);
    action.searchParams.set('lang', link.lang);
    form.action = action.href;
    history.replaceState(null, '', link.href);
    credential.focus();
  });
}
