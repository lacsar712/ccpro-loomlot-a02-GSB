<script>
  import { onMount } from 'svelte';
  import { api, VAT_STATUS, toLocalInput, fromLocalInput } from '../lib/api.js';
  import { user } from '../lib/auth.js';

  let vats = [];
  let rows = [];
  let stats = null;
  let error = '';
  let form = {
    vatId: '',
    chemicalName: '',
    doseL: 5,
    dosedAt: toLocalInput(new Date().toISOString()),
    operatorName: '',
  };

  $: isAdmin = $user?.role === 'admin';

  async function load() {
    error = '';
    try {
      [vats, rows, stats] = await Promise.all([
        api('/vats'),
        api('/chemical-doses'),
        api('/dashboard/stats'),
      ]);
      if (!form.operatorName) form.operatorName = $user?.displayName || $user?.username || '';
      const usable = vats.filter((v) => v.status === 'ready' || v.status === 'dyeing');
      if (!form.vatId && usable.length) form.vatId = String(usable[0].id);
    } catch (e) {
      error = e.message;
    }
  }

  onMount(load);

  function vatLabel(id) {
    const v = vats.find((x) => x.id === id);
    if (!v) return id;
    return `${v.vatCode}（${VAT_STATUS[v.status] || v.status}）`;
  }

  // 与看板同一“本周”口径（本周一 UTC 00:00，来自 /dashboard/stats 的 weekStart）。
  $: weekRows = stats
    ? rows.filter(
        (r) =>
          !r.voided && new Date(r.dosedAt).getTime() >= new Date(stats.weekStart).getTime()
      )
    : [];
  $: weekTotalL = weekRows.reduce((s, r) => s + Number(r.doseL || 0), 0);

  function selectedVat() {
    return vats.find((v) => v.id === Number(form.vatId)) || null;
  }

  async function save() {
    error = '';
    const vat = selectedVat();
    if (vat && vat.status === 'drain') {
      error = '排液缸不可加注';
      return;
    }
    try {
      const body = {
        vatId: Number(form.vatId),
        chemicalName: form.chemicalName.trim(),
        doseL: Number(form.doseL),
        dosedAt: fromLocalInput(form.dosedAt),
        operatorName: form.operatorName.trim(),
      };
      await api('/chemical-doses', { method: 'POST', body: JSON.stringify(body) });
      form = {
        ...form,
        chemicalName: '',
        doseL: 5,
        dosedAt: toLocalInput(new Date().toISOString()),
      };
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  async function voidDose(row) {
    if (!confirm(`确认作废 #${row.id} 这笔 ${row.doseL}L 加注？作废后不可恢复。`)) return;
    error = '';
    try {
      await api(`/chemical-doses/${row.id}/void`, { method: 'POST' });
      await load();
    } catch (e) {
      error = e.message;
    }
  }
</script>

<h1 class="page-title">助剂加注</h1>
<p class="page-sub">
  仅就绪 / 染色中染缸可加注；未排液期间累计加注不超过缸容 30%；染色中单笔不超过最新染程布重一半（1kg 布重折 1 升）。
</p>

<div class="panel" style="margin-bottom:1rem;">
  <div class="form-grid">
    <label
      >染缸
      <select bind:value={form.vatId}>
        {#each vats as v}
          <option value={String(v.id)}
            >{v.vatCode} · {VAT_STATUS[v.status] || v.status} · 缸容 {v.capacityL}L</option
          >
        {/each}
      </select>
    </label>
    <label>助剂名 <input placeholder="如 纯碱缓冲剂" bind:value={form.chemicalName} /></label>
    <label>加注升数 L <input type="number" step="0.1" min="0.1" bind:value={form.doseL} /></label>
    <label>加注时刻 <input type="datetime-local" bind:value={form.dosedAt} /></label>
    <label>操作人 <input bind:value={form.operatorName} /></label>
  </div>
  <div class="toolbar">
    <button class="btn" type="button" on:click={save}>新建加注</button>
  </div>
  {#if error}<p class="err">{error}</p>{/if}
</div>

<div class="panel">
  <div class="week-bar">
    <span>本周（自 {stats ? new Date(stats.weekStart).toLocaleDateString() : '周一'} 起）</span>
    <strong>{weekTotalL.toFixed(1)} L</strong>
    <span class="muted">· {weekRows.length} 笔有效加注，与看板合计一致</span>
  </div>
  <table>
    <thead>
      <tr>
        <th>ID</th>
        <th>染缸</th>
        <th>助剂名</th>
        <th>升数</th>
        <th>加注时刻</th>
        <th>操作人</th>
        <th>状态</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row}
        <tr class:voided={row.voided}>
          <td>{row.id}</td>
          <td>{vatLabel(row.vatId)}</td>
          <td>{row.chemicalName}</td>
          <td>{row.doseL} L</td>
          <td>{new Date(row.dosedAt).toLocaleString()}</td>
          <td>{row.operatorName}</td>
          <td>
            {#if row.voided}
              <span class="badge void">已作废{row.voidedByName ? ` · ${row.voidedByName}` : ''}</span>
            {:else}
              <span class="badge ok">有效</span>
            {/if}
          </td>
          <td class="row-actions">
            {#if !row.voided && isAdmin}
              <button class="btn danger small" type="button" on:click={() => voidDose(row)}>作废</button>
            {:else if !row.voided && !isAdmin}
              <span class="muted">仅主管可作废</span>
            {/if}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  .week-bar {
    display: flex;
    align-items: baseline;
    gap: 0.6rem;
    padding: 0.6rem 0.1rem 0.9rem;
    font-size: 0.92rem;
  }

  .week-bar strong {
    font-size: 1.15rem;
    color: var(--indigo-bright, #8b7cf0);
  }

  .muted {
    color: var(--indigo-mist, #9a90c8);
    opacity: 0.8;
    font-size: 0.82rem;
  }

  .badge {
    display: inline-block;
    padding: 0.1rem 0.5rem;
    border-radius: 3px;
    font-size: 0.78rem;
  }

  .badge.ok {
    background: rgba(76, 175, 130, 0.18);
    color: var(--ok, #4caf82);
  }

  .badge.void {
    background: rgba(220, 90, 90, 0.16);
    color: #d06a6a;
  }

  tr.voided td {
    opacity: 0.55;
    text-decoration: line-through;
  }

  tr.voided td:last-child,
  tr.voided .badge {
    text-decoration: none;
  }
</style>
