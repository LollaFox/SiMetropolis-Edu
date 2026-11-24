async function openTeacherView() {
  const ticket = window.location.hash.slice(1);
  const language = document.documentElement.lang;
  const teacherView = language === 'en' ? '/teacher' : `/teacher?lang=${language}`;
  if (!ticket) {
    window.location.replace(teacherView);
    return;
  }

  window.history.replaceState(null, '', window.location.pathname);
  const response = await fetch('/teacher/launch', {
    method: 'POST',
    body: new URLSearchParams({ ticket }),
  });
  if (response.status === 202) {
    document.getElementById('launch-status').hidden = true;
    document.getElementById('launch-renewed').hidden = false;
    return;
  }
  if (!response.ok) throw new Error('Teacher launch failed');
  window.location.replace(teacherView);
}

openTeacherView().catch(() => {
  document.getElementById('launch-status').hidden = true;
  document.getElementById('launch-error').hidden = false;
});
