import { LeftPanel } from '/static/components/LeftPanel.js';
import { RightPanel } from '/static/components/RightPanel.js';

async function setupBackgroundRotator() {
  if (document.querySelector('.app-bg-rotator')) return;

  const imageCandidates = [
    '/static/assets/backgrounds/background.jpg',
    '/static/assets/backgrounds/background2.jpg',
    '/static/assets/backgrounds/background3.jpg',
    '/static/assets/backgrounds/background4.jpg',
  ];

  const preloadImage = (src) =>
    new Promise((resolve) => {
      const img = new Image();
      img.onload = () => resolve(src);
      img.onerror = () => resolve(null);
      img.src = src;
    });

  const images = (await Promise.all(imageCandidates.map(preloadImage))).filter(Boolean);
  if (images.length === 0) return;

  const rotator = document.createElement('div');
  rotator.className = 'app-bg-rotator';

  const layerA = document.createElement('div');
  layerA.className = 'app-bg-layer is-visible';

  const layerB = document.createElement('div');
  layerB.className = 'app-bg-layer';

  layerA.style.backgroundImage = `url("${images[0]}")`;
  layerB.style.backgroundImage = `url("${images[1] || images[0]}")`;

  rotator.append(layerA, layerB);
  document.body.prepend(rotator);

  let activeLayer = layerA;
  let hiddenLayer = layerB;
  let nextIndex = images.length > 1 ? 1 : 0;
  const TRANSITION_MS = 1400;

  if (images.length < 2) return;

  window.setInterval(() => {
    rotator.classList.add('is-transitioning');
    hiddenLayer.style.backgroundImage = `url("${images[nextIndex]}")`;
    hiddenLayer.classList.add('is-visible');
    activeLayer.classList.remove('is-visible');

    const previousActive = activeLayer;
    activeLayer = hiddenLayer;
    hiddenLayer = previousActive;
    nextIndex = (nextIndex + 1) % images.length;

    window.setTimeout(() => {
      rotator.classList.remove('is-transitioning');
    }, TRANSITION_MS + 60);
  }, 20000);
}

function renderApp() {
  const root = document.getElementById('app');
  if (!root) return;

  const layout = document.createElement('main');
  layout.className = 'main-layout';
  layout.append(LeftPanel(), RightPanel());

  root.innerHTML = '';
  root.append(layout);
}

setupBackgroundRotator();
renderApp();
