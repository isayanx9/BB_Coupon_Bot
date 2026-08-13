/* Optional Mini App enhancements.  This file intentionally adds pages without
   changing checkout, payment confirmation, delivery, or existing customer data. */
(function () {
  const q = (selector) => document.querySelector(selector);
  const safe = (value) => { const node = document.createElement('i'); node.textContent = value || ''; return node.innerHTML; };
  const moneyText = (value) => 'Rs ' + Number(value || 0).toLocaleString('en-IN');
  const call = (path, options = {}) => window.api(path, options);
  const open = (title, body) => window.openPage(title, body);

  function countdown(value) {
    if (!value) return 'Limited time';
    const seconds = Math.max(0, Math.floor((new Date(value).getTime() - Date.now()) / 1000));
    return seconds ? `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}` : 'Ended';
  }

  function renderExtras() {
    if (!window.state?.data) return;
    const sales = window.state.data.flash_sales || [];
    const holder = q('#flash-sales');
    if (holder) holder.innerHTML = sales.map(s => `<article class="flash-sale"><b>FLASH: ${safe(s.title || s.coupon_name)}</b><small>${safe(s.discount_text || 'Special live price')}</small><time data-sale-expiry="${safe(s.expires_at || '')}">${countdown(s.expires_at)}</time></article>`).join('');
    document.querySelectorAll('.coupon').forEach((card, index) => {
      if (card.querySelector('.coupon-watch')) return;
      const coupon = window.state.data.coupons[index];
      if (!coupon) return;
      card.insertAdjacentHTML('beforeend', `<button class="coupon-watch" data-watch="${safe(coupon.coupon_name)}">Notify me when this is stocked</button>`);
    });
  }

  async function stockWatch(name) {
    try { await call('/api/mini/stock-watch', { method: 'POST', body: JSON.stringify({ coupon_name: name }) }); window.toast('Stock alert saved. We will message you on Telegram.'); }
    catch (error) { window.toast(error.message); }
  }

  function receipt(id) {
    call('/api/mini/receipts/' + encodeURIComponent(id)).then(result => {
      const o = result.receipt;
      open('Order receipt', `<section class="receipt-card"><small>BB Coupon Shop receipt</small><h3>${safe(o.coupon_name)}</h3><p>Order: <code>${safe(o.id)}</code></p><p>Status: <b>${safe(o.delivery_status)}</b></p><p>Paid: <b>${moneyText(o.amount)}</b></p><p>Quantity: <b>${o.quantity}</b></p><p>Created: ${safe(window.formatDate(o.created_at))}</p>${o.coupon_code ? `<code>${safe(o.coupon_code)}</code><button class="primary" data-copy="${safe(o.coupon_code)}">Copy coupon code</button>` : '<p class="meta">The coupon code appears here only after successful delivery.</p>'}</section>`);
    }).catch(error => window.toast(error.message));
  }

  function validator() {
    open('Validate coupon', `<p class="meta">Validate a coupon that was delivered to this Telegram account.</p><input id="validate-code" placeholder="Enter coupon code"><button class="primary" id="validate-submit">Validate coupon</button><div id="validate-result"></div>`);
    q('#validate-submit').onclick = async () => {
      try { const r = await call('/api/mini/coupon-validate', { method: 'POST', body: JSON.stringify({ code: q('#validate-code').value }) }); q('#validate-result').innerHTML = r.valid ? `<p class="service-status">Valid delivered coupon for ${safe(r.coupon_name)}. Order ${safe(r.order_id)}.</p>` : '<p class="pending-note">This code was not found in your delivered orders.</p>'; } catch (error) { window.toast(error.message); }
    };
  }

  async function preferences() {
    try {
      const value = await call('/api/mini/preferences');
      open('Notifications', `<p class="meta">Choose whether this account receives stock-restock alerts in Telegram.</p><label class="switch-row"><span><b>Stock alerts</b><small>Coupon availability updates</small></span><input id="stock-alert-toggle" type="checkbox" ${value.stock_alerts ? 'checked' : ''}></label><button class="primary" id="save-preferences">Save preferences</button>`);
      q('#save-preferences').onclick = async () => { const result = await call('/api/mini/preferences', { method: 'POST', body: JSON.stringify({ stock_alerts: q('#stock-alert-toggle').checked }) }); window.toast(result.stock_alerts ? 'Stock alerts enabled' : 'Stock alerts disabled'); };
    } catch (error) { window.toast(error.message); }
  }

  async function adminOrders() {
    open('Admin order search', `<p class="meta">Search by order ID, Telegram user ID, or delivered coupon code.</p><input id="admin-query" placeholder="Order ID, user ID, or coupon code"><button class="primary" id="admin-search">Search orders</button><div id="admin-results"></div>`);
    q('#admin-search').onclick = async () => { try { const r = await call('/api/mini/admin/orders/search?query=' + encodeURIComponent(q('#admin-query').value)); q('#admin-results').innerHTML = r.orders.map(o => `<article class="order-card"><b>${safe(o.id)}</b><small>User ${o.user_id} · ${safe(o.coupon_name)}</small><p class="pending-note">${safe(o.payment_status)} / ${safe(o.delivery_status)} · ${moneyText(o.amount)}</p></article>`).join('') || '<p class="meta">No matching orders.</p>'; } catch (error) { window.toast(error.message); } };
  }

  async function adminTickets() {
    try { const d = await call('/api/mini/admin/overview'); open('Admin tickets', `<p class="meta">Replies are stored and sent to the customer in Telegram.</p>${d.tickets.map(t => `<button class="admin-action" data-ticket-id="${t.id}" data-ticket-subject="${safe(t.subject)}"><b>#${t.id} ${safe(t.subject)}</b><small>${safe(t.status)} - tap to reply</small></button>`).join('') || '<p class="meta">No open support tickets.</p>'}`); }
    catch (error) { window.toast(error.message); }
  }

  function replyTicket(id, subject) {
    open('Reply to ticket #' + id, `<p class="meta">${safe(subject)}</p><textarea id="admin-reply" placeholder="Write a helpful reply"></textarea><button class="primary" id="send-admin-reply">Send reply and close ticket</button>`);
    q('#send-admin-reply').onclick = async () => { try { await call('/api/mini/admin/tickets/' + id + '/reply', { method: 'POST', body: JSON.stringify({ message: q('#admin-reply').value }) }); window.toast('Reply sent and ticket closed'); adminTickets(); } catch (error) { window.toast(error.message); } };
  }

  async function backupStatus() {
    try { const d = await call('/api/mini/admin/overview'); open('Database protection', `<section class="receipt-card"><b>${safe(d.backup.provider)}</b><p>${safe(d.backup.status)}</p><p class="meta">Customer, order, coupon and payment data are never editable from this Mini App. Configure managed backups in Railway for recovery snapshots.</p></section>`); } catch (error) { window.toast(error.message); }
  }

  const originalAdmin = window.admin;
  window.admin = async function () {
    try { const d = await call('/api/mini/admin/overview'); const a = d.analytics; open('Admin dashboard', `<p class="meta">Protected operations center. Customer data is read-only here.</p><div class="quick-grid"><div class="quick violet"><b>${moneyText(a.revenue)}</b><small>Revenue</small></div><div class="quick gold"><b>${a.total_orders}</b><small>Orders</small></div><div class="quick cyan"><b>${a.total_users}</b><small>Users</small></div></div><button class="primary" id="maintenance-toggle">${d.maintenance_mode === 'on' ? 'Turn maintenance OFF' : 'Turn maintenance ON'}</button><div class="feature-grid"><button id="admin-orders">Order search</button><button id="admin-tickets">Support tickets</button><button id="admin-backups">Database protection</button><button id="admin-inventory">Inventory overview</button></div>`); q('#maintenance-toggle').onclick = async () => { try { const r = await call('/api/mini/admin/maintenance', { method: 'POST', body: JSON.stringify({ enabled: d.maintenance_mode !== 'on' }) }); window.toast('Maintenance is ' + r.maintenance_mode); window.admin(); } catch (error) { window.toast(error.message); } }; q('#admin-orders').onclick = adminOrders; q('#admin-tickets').onclick = adminTickets; q('#admin-backups').onclick = backupStatus; q('#admin-inventory').onclick = () => open('Inventory overview', d.coupons.map(c => `<div class="order"><b>${safe(c.name)}</b><small>${c.available} available · ${moneyText(c.price)}</small></div>`).join('') || '<p class="meta">No coupon data.</p>'); }
    catch (error) { window.toast(error.message); if (originalAdmin) originalAdmin(); }
  };

  document.addEventListener('click', event => {
    const watch = event.target.closest('[data-watch]'); if (watch) stockWatch(watch.dataset.watch);
    const ticket = event.target.closest('[data-ticket-id]'); if (ticket) replyTicket(ticket.dataset.ticketId, ticket.dataset.ticketSubject);
    const viewReceipt = event.target.closest('[data-receipt]'); if (viewReceipt) receipt(viewReceipt.dataset.receipt);
    if (event.target.closest('[data-nav="orders"],[data-view="orders"]')) setTimeout(() => {
      document.querySelectorAll('.order-card').forEach((card, index) => {
        const order = window.state?.data?.orders?.[index];
        if (order && !card.querySelector('[data-receipt]')) card.insertAdjacentHTML('beforeend', `<button class="coupon-watch" data-receipt="${safe(order.id)}">View receipt</button>`);
      });
    }, 500);
  });

  const timer = setInterval(() => { renderExtras(); document.querySelectorAll('[data-sale-expiry]').forEach(el => { el.textContent = countdown(el.dataset.saleExpiry); }); if (window.state?.data) clearInterval(timer); }, 250);
  document.addEventListener('click', event => { if (event.target.closest('#profile-btn')) setTimeout(() => { const host = q('.account-actions'); if (host && !q('#account-extras')) host.insertAdjacentHTML('beforeend', `<button id="account-extras">&#10003; <span>Validate coupon / alerts</span> &#8594;</button>`); q('#account-extras')?.addEventListener('click', () => { open('Tools', `<div class="feature-grid"><button id="open-validator">Validate coupon</button><button id="open-preferences">Notifications</button></div>`); q('#open-validator').onclick = validator; q('#open-preferences').onclick = preferences; }); }, 0); });
})();
