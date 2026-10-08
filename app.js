const messages = document.querySelector('#messages');
const form = document.querySelector('#chatForm');
const input = document.querySelector('#chatInput');
const quickReplies = document.querySelector('#quickReplies');
const toast = document.querySelector('#toast');
function addMessage(text, type = 'user') {
  const item = document.createElement('div');
  item.className = `message ${type}`;
  item.innerHTML = type === 'bot' ? `<span class="message-time">hozir</span>${text}` : text;
  messages.appendChild(item);
  messages.scrollTop = messages.scrollHeight;
}
async function answer(text) {
  addMessage(text);
  input.value = '';
  try {
    const response = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: text }) });
    const data = await response.json();
    addMessage(data.reply, 'bot');
  } catch (error) { addMessage('Server bilan aloqa uzildi. Backend ishlayotganini tekshiring.', 'bot'); }
}
form.addEventListener('submit', (event) => { event.preventDefault(); if (input.value.trim()) answer(input.value.trim()); });
quickReplies.addEventListener('click', (event) => { if (event.target.matches('button')) answer(event.target.dataset.prompt); });
async function addToCart(itemId, label) {
  try {
    const response = await fetch('/api/cart', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ item_id: itemId }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    showToast(`${label} savatga qo‘shildi`);
    renderCart(data);
  } catch (error) { showToast('Savatga qo‘shib bo‘lmadi'); }
}
document.querySelector('#addBtn').addEventListener('click', () => addToCart('ramen', 'Truffle Ramen'));
document.querySelectorAll('.mini-add').forEach(button => button.addEventListener('click', () => {
  const itemId = { 'Gyoza Mix': 'gyoza', 'Butter Chicken': 'chicken', 'Matcha Latte': 'matcha' }[button.dataset.food];
  addToCart(itemId, button.dataset.food);
}));
async function loadCart() {
  try {
    const response = await fetch('/api/cart');
    renderCart(await response.json());
  } catch (error) { showToast('Savatni yuklab bo‘lmadi'); }
}
function renderCart(data) {
  const items = data.items || [];
  document.querySelector('#cartCount').textContent = `${items.reduce((sum, item) => sum + item.quantity, 0)} taom`;
  document.querySelector('#cartTotal').textContent = `${data.total.toLocaleString('uz-UZ')} so‘m`;
  document.querySelector('#orderBtn').disabled = items.length === 0;
  document.querySelector('#cartItems').innerHTML = items.length ? items.map(item => `<div class="cart-row"><span class="food-emoji">${item.emoji}</span><div><strong>${item.name}</strong><small>${item.quantity} dona × ${item.price.toLocaleString('uz-UZ')} so‘m</small></div><span class="cart-row-total">${(item.quantity * item.price).toLocaleString('uz-UZ')} so‘m</span></div>`).join('') : '<div class="cart-empty">Savat hozircha bo‘sh. Yoqtirgan taomingizni qo‘shing.</div>';
}
document.querySelector('#orderBtn').addEventListener('click', async () => {
  const response = await fetch('/api/orders', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ customer: { name: 'Mehmon' } }) });
  const order = await response.json();
  if (response.ok) { showToast(`${order.id} buyurtma qabul qilindi`); loadCart(); }
});
document.querySelector('#refreshBtn').addEventListener('click', (event) => { event.target.textContent = '✓ Yangilandi'; setTimeout(() => event.target.textContent = '↻ Yangilash', 1300); showToast('Tavsiyalar yangilandi'); });
document.querySelectorAll('[data-scroll]').forEach(button => button.addEventListener('click', () => document.querySelector(`#${button.dataset.scroll}`).scrollIntoView({ behavior: 'smooth' })));
function showToast(text) { toast.textContent = text; toast.classList.add('show'); setTimeout(() => toast.classList.remove('show'), 2200); }
loadCart();
