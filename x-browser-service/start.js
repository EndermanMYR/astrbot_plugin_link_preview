const button = document.querySelector('#start');
button.addEventListener('click', async () => {
  button.disabled = true;
  try {
    const ticket = location.pathname.split('/').pop();
    const response = await fetch('/redeem/' + encodeURIComponent(ticket), { method: 'POST' });
    if (response.ok) location.replace('/');
    else document.querySelector('#status').textContent = await response.text();
  } catch {
    document.querySelector('#status').textContent = '连接失败，请稍后重试。';
  }
  button.disabled = false;
});
