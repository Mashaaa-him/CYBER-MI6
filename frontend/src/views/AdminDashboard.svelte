<script lang="ts">
  import { onMount } from 'svelte';
  import { apiFetch } from '../services/api';
  import type { UserProfile } from '../types/auth';

  let users = $state<UserProfile[]>([]);
  let loading = $state(true);
  let error = $state('');

  // Form states for creating/editing users
  let showModal = $state(false);
  let editMode = $state(false);
  let currentUser = $state<Partial<UserProfile>>({
    username: '',
    role: 'analyst',
    permissions: [],
    status: 'active'
  });
  let newPassword = $state('');

  onMount(async () => {
    await loadUsers();
  });

  async function loadUsers() {
    loading = true;
    try {
      // Expecting backend route: GET /api/users
      users = await apiFetch<UserProfile[]>('/users');
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to load users';
    } finally {
      loading = false;
    }
  }

  function openCreateModal() {
    editMode = false;
    currentUser = { username: '', role: 'analyst', permissions: [], status: 'active' };
    newPassword = '';
    showModal = true;
  }

  function openEditModal(user: UserProfile) {
    editMode = true;
    currentUser = { ...user };
    newPassword = ''; // Only fill if changing
    showModal = true;
  }

  async function saveUser(e: Event) {
    e.preventDefault();
    try {
      const payload = {
        ...currentUser,
        ...(newPassword ? { password: newPassword } : {})
      };

      if (editMode) {
        await apiFetch(`/users/${currentUser.id}`, { method: 'PATCH', body: JSON.stringify(payload) });
      } else {
        await apiFetch('/users', { method: 'POST', body: JSON.stringify(payload) });
      }
      
      showModal = false;
      await loadUsers();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to save user';
    }
  }

  async function toggleStatus(user: UserProfile) {
    try {
      const newStatus = user.status === 'active' ? 'disabled' : 'active';
      await apiFetch(`/users/${user.id}/status`, { 
        method: 'PATCH', 
        body: JSON.stringify({ status: newStatus }) 
      });
      await loadUsers();
    } catch (err) {
      error = err instanceof Error ? err.message : 'Failed to update status';
    }
  }
</script>

<div class="admin-container">
  <div class="header-actions">
    <h2>User Administration</h2>
    <button class="btn-primary" onclick={openCreateModal}>+ Provision Account</button>
  </div>

  {#if error}
    <div class="error-banner">{error}</div>
  {/if}

  <div class="table-container">
    <table class="data-table">
      <thead>
        <tr>
          <th>Operator ID</th>
          <th>Role</th>
          <th>Status</th>
          <th>Last Login</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {#if loading}
          <tr><td colspan="5" class="center-text">Loading directory...</td></tr>
        {:else if users.length === 0}
          <tr><td colspan="5" class="center-text">No users found.</td></tr>
        {:else}
          {#each users as user}
            <tr class={user.status === 'disabled' ? 'disabled-row' : ''}>
              <td class="mono">{user.username}</td>
              <td><span class={`badge role-${user.role}`}>{user.role.toUpperCase()}</span></td>
              <td>
                <span class={`status-dot ${user.status}`}></span>
                {user.status}
              </td>
              <td class="mono muted">{user.lastLogin || 'Never'}</td>
              <td class="actions">
                <button class="btn-text" onclick={() => openEditModal(user)}>Edit</button>
                <button class="btn-text danger" onclick={() => toggleStatus(user)}>
                  {user.status === 'active' ? 'Disable' : 'Reactivate'}
                </button>
              </td>
            </tr>
          {/each}
        {/if}
      </tbody>
    </table>
  </div>
</div>

{#if showModal}
  <div class="modal-backdrop">
    <div class="modal-card">
      <h3>{editMode ? 'Modify Account' : 'Provision New Account'}</h3>
      <form onsubmit={saveUser}>
        <div class="form-group">
          <label for="username">Operator ID</label>
          <input type="text" id="username" bind:value={currentUser.username} required disabled={editMode} />
        </div>
        
        <div class="form-group">
          <label for="password">{editMode ? 'Reset Passphrase (leave blank to keep)' : 'Initial Passphrase'}</label>
          <input type="password" id="password" bind:value={newPassword} required={!editMode} />
        </div>

        <div class="form-group row">
          <div class="col">
            <label for="role">Clearance Level</label>
            <select id="role" bind:value={currentUser.role}>
              <option value="analyst">Analyst</option>
              <option value="admin">Administrator</option>
            </select>
          </div>
          <div class="col">
            <label for="status">Account Status</label>
            <select id="status" bind:value={currentUser.status}>
              <option value="active">Active</option>
              <option value="disabled">Disabled</option>
            </select>
          </div>
        </div>

        <div class="modal-actions">
          <button type="button" class="btn-secondary" onclick={() => showModal = false}>Cancel</button>
          <button type="submit" class="btn-primary">{editMode ? 'Save Changes' : 'Create Account'}</button>
        </div>
      </form>
    </div>
  </div>
{/if}

<style>
  .admin-container {
    padding: 1rem;
    color: var(--color-text, #cdd6f4);
  }
  .header-actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2rem;
  }
  h2 {
    font-family: 'JetBrains Mono Variable', monospace;
    color: var(--color-primary, #89b4fa);
    margin: 0;
  }
  .table-container {
    background: var(--color-surface, #1e1e2e);
    border: 1px solid var(--color-border, #313244);
    border-radius: 8px;
    overflow-x: auto;
  }
  .data-table {
    width: 100%;
    border-collapse: collapse;
    text-align: left;
  }
  .data-table th, .data-table td {
    padding: 1rem;
    border-bottom: 1px solid var(--color-border, #313244);
  }
  .data-table th {
    font-weight: 600;
    font-size: 0.85rem;
    text-transform: uppercase;
    color: var(--color-text-muted, #a6adc8);
    background: rgba(17, 17, 27, 0.5);
  }
  .mono { font-family: 'JetBrains Mono Variable', monospace; font-size: 0.9rem; }
  .muted { color: var(--color-text-muted, #a6adc8); }
  .disabled-row { opacity: 0.5; }
  
  .badge {
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: bold;
  }
  .role-admin { background: rgba(243, 139, 168, 0.2); color: #f38ba8; }
  .role-analyst { background: rgba(137, 180, 250, 0.2); color: #89b4fa; }
  
  .status-dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    margin-right: 6px;
  }
  .status-dot.active { background: #a6e3a1; box-shadow: 0 0 5px #a6e3a1; }
  .status-dot.disabled { background: #f38ba8; }

  .actions { display: flex; gap: 1rem; }
  .btn-text {
    background: none; border: none;
    color: var(--color-primary, #89b4fa);
    cursor: pointer; font-size: 0.85rem; padding: 0;
  }
  .btn-text.danger { color: #f38ba8; }
  .btn-text:hover { text-decoration: underline; }

  .btn-primary {
    background: var(--color-primary, #89b4fa);
    color: #11111b; border: none; padding: 0.5rem 1rem;
    border-radius: 4px; font-weight: 600; cursor: pointer;
  }
  .btn-secondary {
    background: transparent; color: var(--color-text, #cdd6f4);
    border: 1px solid var(--color-border, #313244);
    padding: 0.5rem 1rem; border-radius: 4px; cursor: pointer;
  }

  .modal-backdrop {
    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
    background: rgba(0,0,0,0.7); display: flex;
    align-items: center; justify-content: center; z-index: 100;
  }
  .modal-card {
    background: var(--color-surface, #1e1e2e);
    border: 1px solid var(--color-border, #313244);
    padding: 2rem; border-radius: 8px; width: 100%; max-width: 400px;
  }
  .modal-card h3 { margin-top: 0; color: var(--color-primary, #89b4fa); }
  .form-group { margin-bottom: 1rem; }
  .row { display: flex; gap: 1rem; }
  .col { flex: 1; }
  label { display: block; margin-bottom: 0.5rem; font-size: 0.85rem; color: var(--color-text-muted, #a6adc8); }
  input, select {
    width: 100%; padding: 0.6rem; border-radius: 4px;
    background: var(--color-background-dark, #11111b);
    border: 1px solid var(--color-border, #313244);
    color: var(--color-text, #cdd6f4); box-sizing: border-box;
  }
  .modal-actions { display: flex; justify-content: flex-end; gap: 1rem; margin-top: 2rem; }
  .error-banner { background: rgba(243, 139, 168, 0.1); color: #f38ba8; padding: 1rem; margin-bottom: 1rem; border-radius: 4px; }
</style>