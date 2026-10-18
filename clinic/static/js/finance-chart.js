(() => {
  const canvas = document.getElementById('finance-chart');
  const dataNode = document.getElementById('finance-chart-data');
  if (!canvas || !dataNode) return;

  let points;
  try { points = JSON.parse(dataNode.textContent); } catch (_) { points = []; }
  const context = canvas.getContext('2d');
  const empty = canvas.parentElement.querySelector('.chart-empty');
  const hasTransactions = points.some(point => Number(point.income) || Number(point.expense));
  if (!hasTransactions) {
    canvas.hidden = true;
    empty.hidden = false;
    return;
  }

  const compactRupiah = value => {
    if (value >= 1e9) return `Rp${(value / 1e9).toLocaleString('id-ID', { maximumFractionDigits: 1 })} M`;
    if (value >= 1e6) return `Rp${(value / 1e6).toLocaleString('id-ID', { maximumFractionDigits: 1 })} jt`;
    if (value >= 1e3) return `Rp${(value / 1e3).toLocaleString('id-ID', { maximumFractionDigits: 0 })} rb`;
    return `Rp${Math.round(value).toLocaleString('id-ID')}`;
  };

  function draw() {
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    if (!width || !height) return;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);

    const pad = { top: 8, right: 12, bottom: 30, left: 60 };
    const plotWidth = width - pad.left - pad.right;
    const plotHeight = height - pad.top - pad.bottom;
    const maximum = Math.max(1, ...points.map(point => Math.max(Number(point.income) || 0, Number(point.expense) || 0)));
    const magnitude = 10 ** Math.floor(Math.log10(maximum));
    const fraction = maximum / magnitude;
    const ceiling = (fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10) * magnitude;

    context.font = '10px system-ui, sans-serif';
    context.textBaseline = 'middle';
    for (let tick = 0; tick <= 4; tick++) {
      const y = pad.top + plotHeight * (1 - tick / 4);
      const value = ceiling * tick / 4;
      context.strokeStyle = '#edf1f3';
      context.lineWidth = 1;
      context.beginPath(); context.moveTo(pad.left, y); context.lineTo(width - pad.right, y); context.stroke();
      context.fillStyle = '#87939a';
      context.textAlign = 'right';
      context.fillText(compactRupiah(value), pad.left - 8, y);
    }

    const slot = plotWidth / points.length;
    const barWidth = Math.max(2, Math.min(14, slot * 0.29));
    const labelEvery = Math.max(1, Math.ceil(points.length / 9));
    points.forEach((point, index) => {
      const center = pad.left + slot * (index + 0.5);
      const incomeHeight = (Number(point.income) || 0) / ceiling * plotHeight;
      const expenseHeight = (Number(point.expense) || 0) / ceiling * plotHeight;
      context.fillStyle = '#22af46';
      context.fillRect(center - barWidth - 1, pad.top + plotHeight - incomeHeight, barWidth, incomeHeight);
      context.fillStyle = '#de4848';
      context.fillRect(center + 1, pad.top + plotHeight - expenseHeight, barWidth, expenseHeight);
      if (index % labelEvery === 0 || index === points.length - 1) {
        context.fillStyle = '#7f8b92';
        context.textAlign = 'center';
        context.textBaseline = 'top';
        context.fillText(point.label, center, pad.top + plotHeight + 8);
        context.textBaseline = 'middle';
      }
    });
  }

  draw();
  if ('ResizeObserver' in window) new ResizeObserver(draw).observe(canvas.parentElement);
  else window.addEventListener('resize', draw);
})();
