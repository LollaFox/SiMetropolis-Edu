const seasonInput = document.querySelector('#crossing-design [name="season"]');
const seasonButtons = [...document.querySelectorAll('#season-buttons button')];
const scene = document.querySelector('#season-scene');
const scenes = new Map([[seasonInput.value, scene.firstElementChild]]);
for (const template of document.querySelectorAll('#crossing-comparison template[data-season]')) {
  scenes.set(template.dataset.season, template.content.firstElementChild);
}

const player = document.querySelector('#play-seasons');
const playLabel = player.textContent;
const announcement = document.querySelector('#season-announcement');
let timer = null;

function showSeason(season) {
  seasonInput.value = season;
  for (const button of seasonButtons) {
    button.setAttribute('aria-pressed', String(button.value === season));
    if (button.value === season) announcement.textContent = button.textContent;
  }
  scene.replaceChildren(scenes.get(season));
  document.querySelector('.experiment-status')?.remove();

  const url = new URL(window.location.href);
  url.searchParams.set('season', season);
  url.searchParams.delete('notice');
  url.hash = 'crossing-comparison';
  window.history.replaceState(null, '', url);
}

function pause() {
  window.clearInterval(timer);
  timer = null;
  player.textContent = playLabel;
}

function advance() {
  const index = seasonButtons.findIndex(button => button.value === seasonInput.value);
  showSeason(seasonButtons[(index + 1) % seasonButtons.length].value);
}

for (const button of seasonButtons) {
  button.addEventListener('click', event => {
    event.preventDefault();
    pause();
    if (button.value !== seasonInput.value) showSeason(button.value);
  });
}
player.addEventListener('click', () => {
  if (timer !== null) {
    pause();
    return;
  }
  player.textContent = player.dataset.pause;
  timer = window.setInterval(advance, 2500);
});

scene.addEventListener('focusin', pause);
scene.addEventListener('pointerdown', pause);
window.addEventListener('pagehide', pause);
player.hidden = false;
