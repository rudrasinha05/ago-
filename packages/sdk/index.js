import {apiVersion} from '@ago/shared';
export class AgoReadClient {
  constructor(baseUrl, fetcher = globalThis.fetch) {
    const url = new URL(baseUrl);
    if (url.username || url.password || url.search || url.hash || url.pathname !== '/') throw new Error('Use an origin without credentials or path');
    if (url.protocol !== 'https:' && !(url.protocol === 'http:' && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname))) throw new Error('HTTPS or loopback required');
    if (typeof fetcher !== 'function') throw new Error('A fetch implementation is required');
    this.origin = url.origin; this.fetcher = fetcher; this.apiVersion = apiVersion;
  }
  async health({timeoutMs = 3000} = {}) {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30000) throw new Error('Invalid timeout');
    const response = await this.fetcher(new URL('/health/live', this.origin), {redirect: 'error', credentials: 'omit', signal: AbortSignal.timeout(timeoutMs)});
    if (!response.ok) throw new Error(`AGO health failed (${response.status})`);
    const result = await response.json();
    if (!result || typeof result.status !== 'string') throw new Error('Invalid health response');
    return {status: result.status};
  }
}
