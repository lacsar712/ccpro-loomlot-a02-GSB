<script>
  import { onMount } from 'svelte';
  import { api, VAT_STATUS, toLocalInput, fromLocalInput } from '../lib/api.js';
  import { user } from '../lib/auth.js';

  let vats = [];
  let lots = [];
  let rows = [];
  let error = '';
  let form = {
    vatId: '',
    auxName: '',
    liters: 5,
    dosedAt: toLocalInput(new Date().toISOString()),
    operatorName: '',
  };

  const isAdmin = () => $user?.role === 'admin';

  // 与看板一致的「本周」口径：本周一 00:00（UTC）
  function startOfWeekUTC(d = new Date()) {
    const x = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
    const mondayOffset = (x.getUTCDay() + 6) % 7;
    x.setUTCDate(x.getUTCDate() - mondayOffset);
    x.setUTCHours(0, 0, 0, 0);
    return x;
  }

  async function load() {
    error = '';
    try {
      [vats, lots, rows] = await Promise.all([
        api('/vats'),
        api('/dye-lots'),
        api('/aux-doses'),
      ]);
      if (!form.operatorName) form.operatorName = $user?.displayName || $user?.username || '';
      if (!form.vatId) {
        const usable = vats.filter((v) => v.status === 'ready' || v.status === 'dyeing');
        if (usable.length) form.vatId = String(usable[0].id);
        else if (vats.length) form.vatId = String(vats[0].id);
      }
    } catch (e) {
      error = e.message;
    }
  }

  onMount(load);

  function vatById(id) {
    return vats.find((v) => v.id === id);
  }

  function vatLabel(id) {
    const v = vatById(id);
    return v ? `${v.vatCode}（${VAT_STATUS[v.status] || v.status}）` : id;
  }

  // 本周（未作废）加注升数合计，须与看板 auxDoseLitersThisWeek 一致
  $: weekStart = startOfWeekUTC();
  $: weekRows = rows.filter(
    (r) => !r.voidedAt && new Date(r.dosedAt).getTime() >= weekStart.getTime()
  );
  $: weekLiters = weekRows.reduce((s, r) => s + Number(r.liters || 0), 0);

  // 同缸未排液期间累计（未作废；排液时刻之后）
  function accumulatedOf(vatId) {
    const v = vatById(vatId);
    if (!v) return 0;
    const drained = v.drainedAt ? new Date(v.drainedAt).getTime() : null;
    return rows
      .filter((r) => {
        if (r.vatId !== vatId || r.voidedAt) return false;
        if (drained !== null && new Date(r.dosedAt).getTime() <= drained) return false;
        return true;
      })
      .reduce((s, r) => s + Number(r.liters || 0), 0);
  }

  $: selectedVat = form.vatId ? vatById(Number(form.vatId)) : null;
  $: selectedAccum = selectedVat ? accumulatedOf(selectedVat.id) : 0;
  $: selectedCapLimit = selectedVat ? selectedVat.capacityL * 0.3 : 0;
  // 染程中：取该缸最新染程（按开始时刻倒序），单次上限 = 布重 kg ÷ 2
  $: latestLotForSelected = selectedVat
    ? lots
        .filter((l) => l.vatId === selectedVat.id)
        .slice()
        .sort((a, b) => new Date(b.startedAt) - new Date(a.startedAt))[0] || null
    : null;
  $: selectedFabricLimit = latestLotForSelected
    ? Number(latestLotForSelected.fabricKg) / 2
    : null;

  async function save() {
    error = '';
    try {
      const body = {
        vatId: Number(form.vatId),
        auxName: form.auxName.trim(),
        liters: Number(form.liters),
        dosedAt: fromLocalInput(form.dosedAt),
        operatorName: form.operatorName.trim(),
      };
      await api('/aux-doses', { method: 'POST', body: JSON.stringify(body) });
      form = {
        ...form,
        auxName: '',
        liters: 5,
        dosedAt: toLocalInput(new Date().toISOString()),
      };
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  async function voidDose(id) {
    if (!confirm('确认作废该加注单？作废后不再计入缸容与本周合计。')) return;
    error = '';
    try {
      await api(`/aux-doses/${id}/void`, { method: 'POST' });
      await load();
    } catch (e) {
      error = e.message;
    }
  }
</script>

<h1 class="page-title">助剂加注</h1>
<p class="page-sub">
  仅就绪 / 染程中染缸可加注；同缸未排液累计 ≤ 缸容 30%；染程中单次 ≤ 最新染程布重 kg ÷ 2（即每 1kg 布 0.5L）。
</p>

<div class="panel" style="margin-bottom:1rem;">
  <div class="form-grid">
    <label
      >所属染缸
      <select bind:value={form.vatId}>
        {#each vats as v}
          <option value={String(v.id)}
            >{v.vatCode} · {VAT_STATUS[v.status] || v.status} · 缸容 {v.capacityL}L</option
          >
        {/each}
      </select>
    </label>
    <label>助剂名 <input placeholder="如 冰醋酸 / 匀染剂" bind:value={form.auxName} /></label>
    <label>加注升数 (L) <input type="number" step="0.1" min="0.1" bind:value={form.liters} /></label>
    <label>加注时刻 <input type="datetime-local" bind:value={form.dosedAt} /></label>
    <label>操作人 <input bind:value={form.operatorName} /></label>
  </div>

  {#if selectedVat}
    <p class="hint-line">
      当前缸未排液累计 <strong>{selectedAccum}</strong> / 上限 {selectedCapLimit} L（缸容
      {selectedVat.capacityL}L 的 30%）
      {#if selectedVat.status === 'dyeing' && selectedFabricLimit !== null}
        · 染程中单次上限 {selectedFabricLimit} L（最新染程布重 {latestLotForSelected.fabricKg}kg ÷ 2）
      {/if}
      {#if selectedVat.status === 'drain'}<span class="warn">· 排液缸不可加注（409）</span>{/if}
    </p>
  {/if}

  <div class="toolbar">
    <button class="btn" type="button" on:click={save}>提交加注</button>
  </div>
  {#if error}<p class="err">{error}</p>{/if}
</div>

<div class="panel">
  <div class="list-head">
    <h2 class="list-title">加注记录</h2>
    <div class="week-sum">本周加注合计（未作废）：<strong>{weekLiters}</strong> L · 共 {weekRows.length} 单</div>
  </div>
  <table>
    <thead>
      <tr>
        <th>ID</th>
        <th>染缸</th>
        <th>助剂</th>
        <th>升数 L</th>
        <th>加注时刻</th>
        <th>操作人</th>
        <th>状态</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row}
        <tr class:voided={!!row.voidedAt}>
          <td>{row.id}</td>
          <td>{vatLabel(row.vatId)}</td>
          <td>{row.auxName}</td>
          <td>{row.liters}</td>
          <td>{new Date(row.dosedAt).toLocaleString()}</td>
          <td>{row.operatorName}</td>
          <td>
            {#if row.voidedAt}
              <span class="badge void">已作废</span>
            {:else}
              <span class="badge ready">有效</span>
            {/if}
          </td>
          <td class="row-actions">
            {#if !row.voidedAt && isAdmin()}
              <button class="btn danger small" type="button" on:click={() => voidDose(row.id)}>作废</button>
            {:else if !row.voidedAt}
              <span class="only-admin">作废仅主管</span>
            {/if}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  .hint-line {
    margin: 0.2rem 0 0.6rem;
    font-size: 0.85rem;
    color: var(--indigo-mist);
  }

  .warn {
    color: #ff8a8a;
  }

  .list-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    margin-bottom: 0.6rem;
    flex-wrap: wrap;
  }

  .list-title {
    font-size: 1.05rem;
    margin: 0;
  }

  .week-sum {
    font-size: 0.9rem;
    color: var(--indigo-mist);
  }

  tr.voided td {
    opacity: 0.55;
    text-decoration: line-through;
  }

  tr.voided td:last-child,
  tr.voided td:nth-child(7) {
    text-decoration: none;
  }

  .badge.void {
    background: rgba(255, 138, 138, 0.15);
    color: #ff9a9a;
    border: 1px solid rgba(255, 138, 138, 0.4);
  }

  .only-admin {
    font-size: 0.72rem;
    color: var(--indigo-mist);
    opacity: 0.7;
  }
</style>
