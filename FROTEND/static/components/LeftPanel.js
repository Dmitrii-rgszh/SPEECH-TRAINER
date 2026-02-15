export function LeftPanel() {
  const panel = document.createElement('aside');
  panel.className = 'left-panel';

  const logo = document.createElement('img');
  logo.className = 'left-logo';
  logo.src = '/static/assets/logo/logo.svg';
  logo.alt = 'RGSL';

  const text = document.createElement('p');
  text.className = 'left-copy';
  text.textContent = 'Добро пожаловать в Речевой тренажер страховой компании "Росгосстрах Жизнь"!';

  const menu = document.createElement('nav');
  menu.className = 'left-menu hidden';
  const menuItems = ['Дэшборд', 'Сценарии', 'Персоны', 'Аналитика'];
  menuItems.forEach((label) => {
    const btn = document.createElement('button');
    btn.className = 'left-menu-btn';
    btn.type = 'button';
    btn.textContent = label;
    btn.addEventListener('click', () => {
      window.dispatchEvent(
        new CustomEvent('app:navigate', {
          detail: { title: label },
        })
      );
    });
    menu.append(btn);
  });

  const footer = document.createElement('div');
  footer.className = 'left-footer hidden';

  const accountRow = document.createElement('div');
  accountRow.className = 'left-footer-row';
  const accountIcon = document.createElement('span');
  accountIcon.className = 'left-footer-icon';
  accountIcon.innerHTML = `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm0 2c-4.4 0-8 2.6-8 5.8 0 .7.6 1.2 1.2 1.2h13.6c.7 0 1.2-.5 1.2-1.2C20 16.6 16.4 14 12 14Z"/>
    </svg>
  `;
  const accountText = document.createElement('span');
  accountRow.append(accountIcon, accountText);

  const logoutButton = document.createElement('button');
  logoutButton.className = 'left-footer-row left-logout-btn';
  logoutButton.type = 'button';
  logoutButton.innerHTML = '<span class="left-footer-icon">↪</span><span>Выйти</span>';
  logoutButton.addEventListener('click', async () => {
    try {
      await fetch('/auth/logout', {
        method: 'POST',
        credentials: 'same-origin',
      });
    } catch (_) {
      // ignore
    }
    window.location.href = '/';
  });

  footer.append(accountRow, logoutButton);

  const applyTopMode = (event) => {
    panel.classList.add('left-panel--top');
    text.textContent = 'Речевой тренажер "Росгосстрах Жизнь"';
    menu.classList.remove('hidden');
    const login = event?.detail?.login || '';
    if (login) {
      accountText.textContent = `Учетная запись: ${login}`;
      footer.classList.remove('hidden');
    } else {
      footer.classList.add('hidden');
    }
  };

  window.addEventListener('registration:completed', applyTopMode);

  panel.append(logo, text, menu, footer);
  return panel;
}
