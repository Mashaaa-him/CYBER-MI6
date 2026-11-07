<script lang="ts">
  import { auth } from '../lib/auth';
  import { apiFetch } from '../services/api';
  import type { AuthResponse } from '../types/auth';

  let username = $state('');
  let password = $state('');
  let showPassword = $state(false);
  let error = $state('');
  let loading = $state(false);
  let rememberMe = $state(false);

  async function handleLogin(e: Event) {
    e.preventDefault();
    error = '';
    loading = true;

    try {
      const data = await apiFetch<AuthResponse>('/token', {
        method: 'POST',
        requireAuth: false,
        body: JSON.stringify({ username, password })
      });
      
      auth.login(data.access_token, data.user);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Invalid credentials. Access denied.';
    } finally {
      loading = false;
    }
  }
</script>

<div class="login-container">
  <div class="login-card">
    <div class="header">
      <h1 class="brand-title">CYBER-MI6</h1>
      <p>Restricted Access. Authenticate to continue.</p>
    </div>

    {#if error}
      <div class="error-banner">{error}</div>
    {/if}

    <form onsubmit={handleLogin}>
      <div class="form-group">
        <label for="username">Operator ID</label>
        <input type="text" id="username" bind:value={username} required autocomplete="username" />
      </div>

      <div class="form-group">
        <label for="password">Passphrase</label>
        <div class="password-wrapper">
          <input type={showPassword ? "text" : "password"} id="password" bind:value={password} required autocomplete="current-password" />
          <button type="button" class="toggle-visibility" onclick={() => showPassword = !showPassword}>
            {showPassword ? 'Hide' : 'Show'}
          </button>
        </div>
      </div>

      <div class="form-actions">
        <label class="remember-me">
          <input type="checkbox" bind:checked={rememberMe} />
          <span>Remember session</span>
        </label>
        <a href="#/forgot-password" class="forgot-link">Recover Access</a>
      </div>

      <button type="submit" class="submit-btn" disabled={loading}>
        {loading ? 'Authenticating...' : 'Secure Login'}
      </button>
    </form>
  </div>
</div>

<style>
  .login-container {
    width: 100%;
    max-width: 420px;
    padding: var(--spacing-xl, 2rem);
  }
  .login-card {
    background: var(--color-surface, #1e1e2e);
    border: 1px solid var(--color-border, #313244);
    border-radius: 8px;
    padding: 2.5rem;
    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
  }
  .header {
    text-align: center;
    margin-bottom: 2rem;
  }
  .brand-title {
    font-family: 'JetBrains Mono Variable', monospace;
    font-size: 2rem;
    color: var(--color-primary, #89b4fa);
    margin: 0 0 0.5rem 0;
    letter-spacing: 2px;
  }
  p {
    color: var(--color-text-muted, #a6adc8);
    font-size: 0.9rem;
  }
  .form-group {
    margin-bottom: 1.5rem;
  }
  label {
    display: block;
    margin-bottom: 0.5rem;
    color: var(--color-text, #cdd6f4);
    font-size: 0.9rem;
    font-weight: 500;
  }
  input[type="text"], input[type="password"] {
    width: 100%;
    padding: 0.75rem;
    background: var(--color-background-dark, #11111b);
    border: 1px solid var(--color-border, #313244);
    color: var(--color-text, #cdd6f4);
    border-radius: 4px;
    font-family: inherit;
    box-sizing: border-box;
  }
  input:focus {
    outline: none;
    border-color: var(--color-primary, #89b4fa);
  }
  .password-wrapper {
    position: relative;
  }
  .toggle-visibility {
    position: absolute;
    right: 0.5rem;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    color: var(--color-text-muted, #a6adc8);
    cursor: pointer;
  }
  .form-actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
    font-size: 0.85rem;
  }
  .forgot-link {
    color: var(--color-primary, #89b4fa);
    text-decoration: none;
  }
  .error-banner {
    background: rgba(243, 139, 168, 0.1);
    color: #f38ba8;
    padding: 0.75rem;
    border-radius: 4px;
    border: 1px solid rgba(243, 139, 168, 0.3);
    margin-bottom: 1.5rem;
    text-align: center;
  }
  .submit-btn {
    width: 100%;
    padding: 0.8rem;
    background: var(--color-primary, #89b4fa);
    color: #11111b;
    border: none;
    border-radius: 4px;
    font-weight: 600;
    cursor: pointer;
    text-transform: uppercase;
  }
  .submit-btn:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
</style>