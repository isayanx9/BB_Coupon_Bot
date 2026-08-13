/* Cashfree hosted checkout launcher.
 * It intentionally replaces the older embedded QR flow. Telegram opens this
 * URL externally, so users can choose any payment option provided by Cashfree.
 */
startPayment = async function () {
  try {
    const phone = ($('#checkout-phone')?.value || '').replace(/\D/g, '');
    if (!/^[6-9]\d{9}$/.test(phone)) {
      throw Error('Enter your own valid 10-digit mobile number.');
    }

    const result = await api('/api/mini/checkout', {
      method: 'POST',
      body: JSON.stringify({
        coupon_id: state.selected.coupon_id,
        quantity: state.quantity,
        customer_phone: phone,
      }),
    });

    if (result.delivered) {
      successSound();
      state.data = await api('/api/mini/bootstrap');
      renderHome();
      sheet(`<h2>Coupon delivered</h2><p class="meta">Your wallet paid this order in full.</p><div class="order"><b>${escape(result.order.coupon_name)}</b><small>Code: ${escape(result.order.coupon_code || 'Delivered')}</small></div>`);
      setTimeout(() => tg?.close(), 2200);
      return;
    }

    const expiry = new Date(result.order.expires_at);
    sheet(`<h2>Opening secure payment...</h2><p class="meta">Order ${escape(result.order.id)}</p><h1 id="timer">--:--</h1><p class="meta">Cashfree is opening in your browser. Choose any available UPI app or payment method and pay before the timer ends.</p>`);
    const tick = () => {
      const seconds = Math.max(0, Math.floor((expiry - Date.now()) / 1000));
      $('#timer').textContent = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
      if (!seconds) {
        toast('Payment expired');
        return;
      }
      setTimeout(tick, 1000);
    };
    tick();

    if (!result.checkout_url) throw Error('Secure checkout is unavailable.');
    // Telegram's supported external-link API opens the hosted Cashfree page
    // in the system browser instead of navigating the Mini App to a UPI URI.
    setTimeout(() => {
      if (tg?.openLink) tg.openLink(result.checkout_url);
      else window.location.assign(result.checkout_url);
    }, 150);
  } catch (error) {
    toast(error.message);
  }
};
