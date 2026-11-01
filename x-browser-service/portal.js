import RFB from '/novnc/core/rfb.js';

history.replaceState(null, '', '/');
const status = document.querySelector('#status');
const finish = document.querySelector('#finish');
const address = new URL('/ws', location.href);
address.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
const remote = new RFB(document.querySelector('#screen'), address.href);
remote.scaleViewport = true;
remote.addEventListener('connect', () => { status.textContent = '请在 X 页面完成登录'; });
remote.addEventListener('disconnect', () => { if (!done) status.textContent = '画面连接已断开，正在检查登录状态…'; });
let done = false;
function saved() {
  done = true;
  remote.disconnect();
  finish.disabled = true;
  status.className = 'success';
  status.textContent = '登录完成！Cookie 已保存在服务器，现在可以抓取 X 内容了。';
}
finish.addEventListener('click', async () => {
  finish.disabled = true;
  try {
    const response = await fetch('/finish', { method: 'POST' });
    if (response.ok) saved();
    else status.textContent = await response.text();
  } catch { status.textContent = '连接失败，请稍后重试。'; }
  if (!done) finish.disabled = false;
});
async function poll() {
  if (done) return;
  try {
    const response = await fetch('/status');
    if (!response.ok) {
      done = true;
      remote.disconnect();
      finish.disabled = true;
      status.textContent = '登录会话已过期，请重新发送 /xlogin。';
      return;
    }
    const result = await response.json();
    document.querySelector('#timer').textContent = '剩余 ' + Math.ceil(result.remaining_seconds / 60) + ' 分钟';
    if (result.status === 'saved') saved();
    else if (result.status !== 'pending') {
      done = true;
      remote.disconnect();
      finish.disabled = true;
      status.textContent = '登录窗口已结束，请重新发送 /xlogin。';
    }
  } catch { status.textContent = '正在重新连接服务器…'; }
  if (!done) setTimeout(poll, 2000);
}
poll();
